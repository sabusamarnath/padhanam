"""S100 — meeting residual shape-read (finding-#3 method, the depth/discovery half).

The confirmed-meeting band is degenerate (496 Health-dose meetings → one goal),
so per finding-#3 we do NOT derive a threshold from it. Instead read the SHAPE
of the 518 unlinked meetings' max-similarity-to-the-8-goals distribution (if the
mass sits low, missed-link is robustly small at any plausible cutoff), against
the confirmed meetings' distribution as a reference, and gauge the latent-goal
class by how much the unlinked meetings CLUSTER (coherent unseeded goals) vs
scatter (orphan noise). Reuses the stored meeting vectors (1013); embeds only the
8 goals fresh (QUERY). Counts/stats only — no titles, no content (D21).

Run in the api container; read-only; not imported anywhere.
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import sys
from uuid import uuid4

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"
log = logging.getLogger("ops.s100_meetings_shape")


def _cos(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _pcts(xs):
    xs = sorted(xs)
    if not xs:
        return "n=0"

    def p(q):
        return xs[min(len(xs) - 1, int(q * len(xs)))]

    return (
        f"p10={p(0.10):.3f} p50={statistics.median(xs):.3f} "
        f"p90={p(0.90):.3f} >=.50={sum(1 for x in xs if x>=.5)} "
        f">=.60={sum(1 for x in xs if x>=.6)}"
    )


async def _run() -> None:
    import sqlalchemy as sa

    from apps.api._daily_driver_wiring import GoalGraphAdapter, UnitGraphAdapter
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.domain.work_unit import FacetType
    from contexts.ingestion.adapters.outbound.embedding.litellm_embedder import (
        LiteLLMChunkEmbedder,
    )
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from contexts.ingestion.domain.chunk import Chunk
    from contexts.ingestion.domain.embedding_task import EmbeddingTask
    from padhanam.config import InferenceSettings, Neo4jSettings
    from shared_kernel import TenantContext

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc: TenantContext = wiring.tenant_context
    sf = wiring.session_factory
    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    unit_graph = UnitGraphAdapter(unit_graph=graph)

    records = await unit_graph.list_units(tenant_context=tc)
    edges = await unit_graph.list_goal_edges(tenant_context=tc)
    served = {e.unit_id for e in edges}

    unlinked_mtg, confirmed_mtg = [], []
    for rec in records:
        for f in rec.facets:
            if f.facet_type is FacetType.MEETING:
                (confirmed_mtg if rec.unit_id in served else unlinked_mtg).append(
                    str(f.facet_id)
                )

    goals = await GoalGraphAdapter(outcome_graph=graph).list_goals(tenant_context=tc)
    goal_text = {g.name: (g.name + " " + " ".join(g.aliases)).strip() for g in goals}
    embedder = LiteLLMChunkEmbedder(InferenceSettings())
    gvecs = [
        e.vector
        for e in await embedder.embed(
            [
                Chunk(
                    id=uuid4(), source_id=uuid4(), tenant_id=str(tc.tenant_id),
                    jurisdiction=tc.jurisdiction, chunk_index=0, content=t,
                )
                for t in goal_text.values()
            ],
            tenant_context=tc, task=EmbeddingTask.QUERY,
        )
    ]

    # Pull stored meeting vectors.
    want = set(unlinked_mtg) | set(confirmed_mtg)
    vec_by_id: dict[str, list] = {}
    async with sf() as session:
        rows = (await session.execute(
            sa.text(
                "SELECT id, embedding FROM meetings "
                "WHERE tenant_id = :t AND embedding IS NOT NULL"
            ),
            {"t": str(tc.tenant_id)},
        )).all()
        for mid, emb in rows:
            if str(mid) in want:
                vec_by_id[str(mid)] = [
                    float(x) for x in str(emb).strip("[]").split(",")
                ]

    def _maxsim(mid):
        v = vec_by_id.get(mid)
        return max(_cos(v, g) for g in gvecs) if v else None

    unl = [s for s in (_maxsim(m) for m in set(unlinked_mtg)) if s is not None]
    conf = [s for s in (_maxsim(m) for m in set(confirmed_mtg)) if s is not None]

    # Clustering tendency among unlinked: each meeting's nearest-OTHER-unlinked
    # similarity (high mass => coherent latent clusters; low => scattered orphan).
    uids = [m for m in set(unlinked_mtg) if m in vec_by_id]
    uvs = [vec_by_id[m] for m in uids]
    nn = []
    for i, vi in enumerate(uvs):
        best = 0.0
        for j, vj in enumerate(uvs):
            if i != j:
                best = max(best, _cos(vi, vj))
        nn.append(best)

    print("S100 meeting shape-read (counts/stats only):")
    print(f"  unlinked meetings (embedded): {len(unl)} of {len(set(unlinked_mtg))}")
    print(f"  confirmed meetings (reference): {len(conf)} of {len(set(confirmed_mtg))}")
    print(f"  UNLINKED max-sim-to-goal:  {_pcts(unl)}")
    print(f"  CONFIRMED max-sim-to-goal: {_pcts(conf)}")
    print(f"  UNLINKED nearest-other-unlinked (clustering): {_pcts(nn)}")
    print(
        "  read: unlinked mass low vs confirmed -> missed-link small (orphan); "
        "high NN-sim mass -> coherent latent clusters (goal discovery)."
    )


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
