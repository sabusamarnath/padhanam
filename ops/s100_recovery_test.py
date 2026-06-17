"""S100 — sample-embedding recovery test, split by tag (the empirical D174 half).

The operator tagged the missed-link emails Md (direct) / Mi (intermediated) / Mu
(unsure) — a structural hypothesis. This tests it directly: would a flat semantic
(tier-three) matcher recover each email→goal link, split by tag, so the decisive
question is answered rather than inferred from a lumped rate — do the Md rows
recover near the confirmed-link rate while the Mi rows recover near the floor?

Embeds each email DOCUMENT-side and the 8 goals QUERY-side via the app embedder
(nomic-embed-text:v1.5). Two instruments: subject-only (proxy, when email_chunks
is empty) or the stored subject+body chunk vectors (clean, after index_email),
selected with --clean (reads email_chunks.embedding, mean per email). Counts and
stats only; no subjects, no content leaves the process (D21).

Reads /tmp/s100_ml_ids.tsv (email_id<TAB>goal<TAB>tag). Run in the api container.
Not imported by anything; read-only.
"""

from __future__ import annotations

import asyncio
import logging
import statistics
import sys
from uuid import uuid4

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"
_ID_PATH = "/tmp/s100_ml_ids.tsv"

log = logging.getLogger("ops.s100_recovery_test")


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


async def _run(clean: bool) -> None:
    import sqlalchemy as sa

    from apps.api._daily_driver_wiring import GoalGraphAdapter
    from apps.cli._runtime import build_tenant_wiring
    from contexts.email.adapters.outbound.postgres.email_store import (
        PostgresEmailStore,
    )
    from contexts.ingestion.adapters.outbound.embedding.litellm_embedder import (
        LiteLLMChunkEmbedder,
    )
    from contexts.ingestion.domain.chunk import Chunk
    from contexts.ingestion.domain.embedding_task import EmbeddingTask
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import InferenceSettings, Neo4jSettings
    from shared_kernel import TenantContext, TenantId

    id_goal_tag: list[tuple[str, str, str]] = []
    with open(_ID_PATH, encoding="utf-8") as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if p and p[0]:
                id_goal_tag.append(
                    (p[0], p[1] if len(p) > 1 else "", p[2] if len(p) > 2 else "?")
                )
    want = {eid for eid, _, _ in id_goal_tag}
    goal_by_id = {eid: g for eid, g, _ in id_goal_tag}
    tag_by_id = {eid: t for eid, _, t in id_goal_tag}

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc: TenantContext = wiring.tenant_context
    session_factory = wiring.session_factory

    async def _resolver(_tid: TenantId):
        return session_factory

    store = PostgresEmailStore(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=TenantId(str(tc.tenant_id)),
    )
    emails = [
        e for e in await store.list_emails(tenant_context=tc) if str(e.id) in want
    ]
    subj_by_id = {str(e.id): (e.subject or "") for e in emails}
    msgid_by_id = {str(e.id): e.message_id for e in emails}

    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    goals = await GoalGraphAdapter(outcome_graph=graph).list_goals(tenant_context=tc)
    goal_text = {g.name: (g.name + " " + " ".join(g.aliases)).strip() for g in goals}
    goal_names = list(goal_text)
    embedder = LiteLLMChunkEmbedder(InferenceSettings())

    def _chunk(text: str) -> "Chunk":
        return Chunk(
            id=uuid4(), source_id=uuid4(), tenant_id=str(tc.tenant_id),
            jurisdiction=tc.jurisdiction, chunk_index=0, content=text or "(empty)",
        )

    goal_vecs = {
        n: e.vector
        for n, e in zip(
            goal_names,
            await embedder.embed(
                [_chunk(goal_text[n]) for n in goal_names],
                tenant_context=tc, task=EmbeddingTask.QUERY,
            ),
        )
    }

    sample_ids = [eid for eid, _, _ in id_goal_tag if eid in subj_by_id]
    vec_by_id: dict[str, list] = {}
    if clean:
        async with session_factory() as session:
            for eid in sample_ids:
                rows = (await session.execute(
                    sa.text(
                        "SELECT embedding FROM email_chunks "
                        "WHERE tenant_id = :t AND message_id = :m "
                        "AND embedding IS NOT NULL"
                    ),
                    {"t": str(tc.tenant_id), "m": msgid_by_id[eid]},
                )).all()
                vecs = [
                    [float(x) for x in str(r[0]).strip("[]").split(",")]
                    for r in rows
                ]
                if vecs:
                    dim = len(vecs[0])
                    vec_by_id[eid] = [
                        sum(v[i] for v in vecs) / len(vecs) for i in range(dim)
                    ]
    else:
        embs = await embedder.embed(
            [_chunk(subj_by_id[eid]) for eid in sample_ids],
            tenant_context=tc, task=EmbeddingTask.DOCUMENT,
        )
        vec_by_id = {eid: e.vector for eid, e in zip(sample_ids, embs)}

    def _tagged_goal(raw: str) -> str | None:
        for n in goal_names:
            if n.split(" (")[0] in raw or raw.startswith(n[:8]):
                return n
        return None

    by_tag: dict[str, dict] = {}
    for eid in sample_ids:
        if eid not in vec_by_id:
            continue
        sims = {n: _cosine(vec_by_id[eid], v) for n, v in goal_vecs.items()}
        nearest = max(sims, key=sims.get)
        tg = _tagged_goal(goal_by_id.get(eid, "")) or "Get a job"
        tag = tag_by_id.get(eid, "?")
        d = by_tag.setdefault(tag, {"n": 0, "near_ok": 0, "sims": [], "rec50": 0})
        d["n"] += 1
        d["sims"].append(sims[tg])
        if nearest == tg:
            d["near_ok"] += 1
            if sims[tg] >= 0.50:
                d["rec50"] += 1

    label = "CLEAN chunks" if clean else "PROXY subjects"
    print(f"S100 recovery test [{label}] (counts only):")
    for tag in ("Md", "Mi", "Mu"):
        d = by_tag.get(tag)
        if not d or d["n"] == 0:
            print(f"  {tag}: n=0")
            continue
        s = d["sims"]
        print(
            f"  {tag}: n={d['n']}  nearest==goal={d['near_ok']}/{d['n']}  "
            f"recovered@0.50={d['rec50']}/{d['n']}  "
            f"sim(min/med/max)={min(s):.3f}/{statistics.median(s):.3f}/{max(s):.3f}"
        )
    print(
        "  read: Md should recover near the confirmed rate; Mi near the floor "
        "if intermediation is real (else tier-three over-read as Mi)."
    )


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_run("--clean" in sys.argv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
