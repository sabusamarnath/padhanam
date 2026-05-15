"""Retrieval evaluation CLI orchestration (S39 / D109, S40 / D110).

Two typer sub-apps:

- ``gold-set`` (S39): authoring lifecycle for gold sets — create,
  append-entry (interactive discovery mode), list, get, finalize.
- ``evaluation-run`` (S40): runner orchestration — start (kicks off a
  run against the current finalized revision; blocks until completion
  or failure), get (snapshot of the run plus results plus aggregates),
  list (paginated index).

The ``evaluation-run start`` subcommand wires the runner against the
agent-level ``AgentRetrievalClientAdapter`` per D110 commitment 5; the
adapter is the single dispatch site for strategy translation, so what
production paths exercise is what evaluation exercises.

Tenant context resolution uses ``build_tenant_wiring`` per the dev-
only label-or-UUID convention; production tenant resolution lands at
Phase 2 per the existing carryover at charter/deferred-decisions.md.
"""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Mapping, Optional, Sequence
from uuid import UUID

import typer

from contexts.agent.application.ports.retrieval_client import (
    RetrievalResult,
)
from contexts.agent.domain.citation_candidates import ChunkCitationCandidate
from contexts.audit.adapters.outbound.postgres.audit import PostgresAuditAdapter
from contexts.audit.domain.events import AuditEvent
from contexts.ingestion.adapters.outbound.embedding import LiteLLMChunkEmbedder
from contexts.ingestion.adapters.outbound.retrieval import PgVectorSearch
from contexts.ingestion.domain.chunk_result import ChunkResult
from contexts.ingestion.domain.entity_result import EntityResult
from contexts.retrieval_evaluation.adapters.outbound.postgres.evaluation_run_reader import (
    PostgresEvaluationRunReader,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.evaluation_run_repository import (
    PostgresEvaluationRunRepository,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.reader import (
    PostgresGoldSetReader,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.repository import (
    PostgresGoldSetRepository,
)
from contexts.retrieval_evaluation.application import (
    EXECUTING_STRATEGIES,
    EmptyDraftError,
    GoldSetMissingFinalizedRevisionError,
    GoldSetNotFoundError,
    NoDraftToFinalizeError,
    append_entry_to_revision,
    create_gold_set,
    finalize_revision,
    get_evaluation_run,
    get_gold_set,
    list_evaluation_runs,
    list_gold_sets,
    run_retrieval_evaluation,
)
from contexts.retrieval_evaluation.ports.retrieval_runner import RankedChunks
from padhanam.config import ControlPlaneSettings
from shared_kernel import TenantContext, TenantId

from apps.cli._cross_context import AgentRetrievalClientAdapter
from apps.cli._runtime import build_tenant_wiring


retrieval_evaluation_app = typer.Typer(
    name="gold-set",
    help="Retrieval evaluation gold-set authoring (S39 / D109).",
    no_args_is_help=True,
)

evaluation_run_app = typer.Typer(
    name="evaluation-run",
    help="Retrieval evaluation runner orchestration (S40 / D110).",
    no_args_is_help=True,
)


def _build_repository_and_reader(
    wiring,
) -> tuple[PostgresGoldSetRepository, PostgresGoldSetReader]:
    bound_tenant_id = TenantId(str(wiring.tenant_context.tenant_id))

    async def _resolver(_tid):
        return wiring.session_factory

    repo = PostgresGoldSetRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    reader = PostgresGoldSetReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    return repo, reader


@retrieval_evaluation_app.command("create")
def cmd_create(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    name: Annotated[str, typer.Option("--name", help="Gold-set name.")],
    created_by: Annotated[
        str, typer.Option("--created-by", help="Author user id for the audit trail.")
    ] = "cli-operator",
) -> None:
    """Create a gold set with an initial draft revision."""
    wiring = build_tenant_wiring(tenant_id)
    repo, _ = _build_repository_and_reader(wiring)

    async def _go() -> None:
        try:
            result = await create_gold_set(
                tenant_context=wiring.tenant_context,
                name=name,
                created_by_user_id=created_by,
                repository=repo,
            )
            typer.echo(f"gold_set_id={result.gold_set.id}")
            typer.echo(f"initial_revision_id={result.initial_revision.id}")
            typer.echo("status=draft revision_number=1")
        finally:
            await wiring.engine.dispose()

    asyncio.run(_go())


@retrieval_evaluation_app.command("append-entry")
def cmd_append_entry(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    gold_set_id: Annotated[
        UUID, typer.Option("--gold-set-id", help="Target gold set.")
    ],
    query: Annotated[
        str,
        typer.Option(
            "--query",
            help="Discovery-mode query against the tenant's corpus.",
        ),
    ],
    top_k: Annotated[
        int, typer.Option("--top-k", help="Number of retrieval candidates to surface.")
    ] = 10,
    correct_indices: Annotated[
        Optional[str],
        typer.Option(
            "--correct-indices",
            help=(
                "Comma-separated 1-based indices of correct chunks in ranked "
                "order (e.g. '3,1,5'). If omitted, the CLI prompts interactively."
            ),
        ),
    ] = None,
    created_by: Annotated[
        str, typer.Option("--created-by", help="Author user id for the audit trail.")
    ] = "cli-operator",
) -> None:
    """Append one entry via discovery mode (retrieve top-K, mark correct)."""
    wiring = build_tenant_wiring(tenant_id)
    repo, reader = _build_repository_and_reader(wiring)
    embedder = LiteLLMChunkEmbedder()
    search = PgVectorSearch(
        session_factory=wiring.session_factory, embedder=embedder
    )

    async def _go() -> None:
        try:
            candidates = await search.search_vector(
                query=query, scope=wiring.tenant_context, limit=top_k
            )
            if not candidates:
                typer.echo(
                    "no retrieval candidates for the query; "
                    "no entry appended."
                )
                raise typer.Exit(code=1)

            typer.echo(f"retrieved {len(candidates)} candidates:")
            for i, c in enumerate(candidates, start=1):
                excerpt = c.content[:120].replace("\n", " ")
                typer.echo(
                    f"  [{i}] chunk_id={c.chunk_id} "
                    f"score={c.similarity_score:.3f} excerpt={excerpt!r}"
                )

            if correct_indices is None:
                indices_input = typer.prompt(
                    "correct indices (1-based, comma-separated, ranked order)"
                )
            else:
                indices_input = correct_indices

            try:
                indices = [
                    int(s.strip()) for s in indices_input.split(",") if s.strip()
                ]
            except ValueError as exc:
                raise typer.BadParameter(
                    f"could not parse indices {indices_input!r}: {exc}"
                ) from exc
            if not indices:
                raise typer.BadParameter("no correct indices provided")
            if any(i < 1 or i > len(candidates) for i in indices):
                raise typer.BadParameter(
                    f"indices out of range; valid range is 1..{len(candidates)}"
                )

            expected_chunk_ids = tuple(
                candidates[i - 1].chunk_id for i in indices
            )

            result = await append_entry_to_revision(
                tenant_context=wiring.tenant_context,
                gold_set_id=gold_set_id,
                query=query,
                expected_chunk_ids=expected_chunk_ids,
                created_by_user_id=created_by,
                reader=reader,
                repository=repo,
            )
            typer.echo(f"entry_id={result.entry.id}")
            typer.echo(f"entry_index={result.entry.entry_index}")
            typer.echo(f"revision_id={result.revision.id}")
            typer.echo(
                f"opened_new_draft={result.opened_new_draft}"
            )
        except GoldSetNotFoundError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=2)
        finally:
            await wiring.engine.dispose()

    asyncio.run(_go())


@retrieval_evaluation_app.command("list")
def cmd_list(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    page_size: Annotated[
        int, typer.Option("--page-size", help="Rows per page (max 50).")
    ] = 20,
    cursor: Annotated[
        Optional[str], typer.Option("--cursor", help="Opaque pagination cursor.")
    ] = None,
) -> None:
    """List gold sets for the tenant (paginated)."""
    wiring = build_tenant_wiring(tenant_id)
    _, reader = _build_repository_and_reader(wiring)

    async def _go() -> None:
        try:
            page, next_cursor = await list_gold_sets(
                tenant_context=wiring.tenant_context,
                reader=reader,
                encoded_cursor=cursor,
                page_size=page_size,
            )
            if not page.gold_sets:
                typer.echo("(no gold sets)")
                return
            for gs in page.gold_sets:
                typer.echo(
                    f"{gs.id}  name={gs.name!r}  "
                    f"created_at={gs.created_at.isoformat()}  "
                    f"current_revision_id={gs.current_revision_id or '(none)'}"
                )
            if next_cursor is not None:
                typer.echo(f"next_cursor={next_cursor}")
        finally:
            await wiring.engine.dispose()

    asyncio.run(_go())


@retrieval_evaluation_app.command("get")
def cmd_get(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    gold_set_id: Annotated[
        UUID, typer.Option("--gold-set-id", help="Gold set to read.")
    ],
) -> None:
    """Show aggregate plus current finalized revision plus its entries."""
    wiring = build_tenant_wiring(tenant_id)
    _, reader = _build_repository_and_reader(wiring)

    async def _go() -> None:
        try:
            snapshot = await get_gold_set(
                tenant_context=wiring.tenant_context,
                gold_set_id=gold_set_id,
                reader=reader,
            )
            if snapshot is None:
                typer.echo("gold set not found", err=True)
                raise typer.Exit(code=2)
            gs = snapshot.gold_set
            typer.echo(f"id={gs.id}")
            typer.echo(f"name={gs.name!r}")
            typer.echo(f"jurisdiction={gs.jurisdiction}")
            typer.echo(f"created_at={gs.created_at.isoformat()}")
            typer.echo(
                f"current_revision_id={gs.current_revision_id or '(none — no finalized revision yet)'}"
            )
            if snapshot.current_revision is not None:
                rev = snapshot.current_revision
                typer.echo(
                    f"current revision: number={rev.revision_number} "
                    f"status={rev.status.value} "
                    f"finalized_at={rev.finalized_at.isoformat() if rev.finalized_at else '(none)'}"
                )
                typer.echo(f"this_event_hash={rev.this_event_hash}")
                typer.echo(f"previous_event_hash={rev.previous_event_hash}")
                typer.echo(f"entries ({len(snapshot.entries)}):")
                for entry in snapshot.entries:
                    chunks = ", ".join(str(c) for c in entry.expected_chunk_ids)
                    typer.echo(
                        f"  [{entry.entry_index}] query={entry.query!r}\n"
                        f"      expected_chunk_ids=[{chunks}]"
                    )
        finally:
            await wiring.engine.dispose()

    asyncio.run(_go())


@retrieval_evaluation_app.command("finalize")
def cmd_finalize(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    gold_set_id: Annotated[
        UUID, typer.Option("--gold-set-id", help="Gold set whose draft to finalize.")
    ],
) -> None:
    """Finalize the current draft revision (computes hash-chain)."""
    wiring = build_tenant_wiring(tenant_id)
    repo, reader = _build_repository_and_reader(wiring)

    async def _go() -> None:
        try:
            result = await finalize_revision(
                tenant_context=wiring.tenant_context,
                gold_set_id=gold_set_id,
                reader=reader,
                repository=repo,
            )
            typer.echo(f"revision_id={result.revision.id}")
            typer.echo(f"revision_number={result.revision.revision_number}")
            typer.echo(f"status={result.revision.status.value}")
            typer.echo(f"this_event_hash={result.this_event_hash}")
            typer.echo(f"previous_event_hash={result.previous_event_hash}")
            typer.echo(
                f"finalized_at={result.revision.finalized_at.isoformat()}"
            )
        except NoDraftToFinalizeError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=2)
        except EmptyDraftError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=3)
        finally:
            await wiring.engine.dispose()

    asyncio.run(_go())


# ----------------------------------------------------------------------
# Runner helpers (S40 / D110)
# ----------------------------------------------------------------------


class _CliCompositeRetrievalClient:
    """RetrievalClient surface composed of PgVectorSearch (S40 graph leg
    deferred per the adapter's Phase-1 best-effort comment at
    apps/cli/_cross_context.py:411-422; the runner's graph strategy
    branch returns empty on this CLI path until per-tenant Neo4j wiring
    lands here too).

    Production wiring at ``TenantRoutingRetrievalClient`` in
    apps/api/_agent_runtime_wiring.py composes both retrieval methods
    over the per-tenant routing layer; the CLI variant binds to one
    tenant per ``build_tenant_wiring`` invocation, so we wire the
    vector leg here and leave a typed empty-sequence stub for the graph
    leg. Evaluation results on graph_only at this CLI invocation will
    surface empty chunk lists with zero metrics; the live-stack smoke
    flags this honestly per Finding 5 latency / Finding 6 audit
    emission verification.
    """

    def __init__(self, *, vector_search: PgVectorSearch) -> None:
        self._vector_search = vector_search

    async def search_vector(
        self, query: str, scope: TenantContext, limit: int
    ) -> Sequence[ChunkResult]:
        return await self._vector_search.search_vector(
            query=query, scope=scope, limit=limit
        )

    async def traverse_graph(
        self, seed: str, scope: TenantContext, depth: int
    ) -> Sequence[EntityResult]:
        # Per the docstring: graph leg empty at the CLI runner path.
        # The adapter still receives a well-formed sequence so the
        # downstream metric computation produces honest zero-metrics
        # rather than a runtime error.
        return ()


class _CliRetrievalRunnerPort:
    """Wraps ``AgentRetrievalClientAdapter`` as a ``RetrievalRunnerPort``.

    Captures wall-clock latency from invocation-start to result-return
    per D110 commitment 3, supplies evaluation-appropriate defaults
    for ``min_score`` (zero — surface every result to the metric
    computation) and ``filter_tree`` (empty — no scope filter), and
    extracts ranked chunk IDs from ``RetrievalResult.citation_candidates``
    (the source of truth for chunk-level provenance per D96; only
    ``ChunkCitationCandidate`` entries carry chunk_id, so the
    extraction is type-narrowed).
    """

    def __init__(self, *, adapter: AgentRetrievalClientAdapter) -> None:
        self._adapter = adapter

    async def __call__(
        self,
        *,
        query: str,
        tenant_context: TenantContext,
        strategy_dispatch: Mapping[str, Any],
        top_k: int,
    ) -> RankedChunks:
        start = time.monotonic()
        result: RetrievalResult = await self._adapter(
            query=query,
            tenant_context=tenant_context,
            retrieval_strategy=strategy_dispatch,
            filter_tree={},
            top_k=top_k,
            min_score=Decimal(0),
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        chunk_ids: tuple[UUID, ...] = tuple(
            c.chunk_id
            for c in result.citation_candidates
            if isinstance(c, ChunkCitationCandidate)
        )
        return RankedChunks(chunk_ids=chunk_ids, latency_ms=latency_ms)


def _build_runner_dependencies(
    wiring,
) -> tuple[
    PostgresEvaluationRunRepository,
    PostgresEvaluationRunReader,
    PostgresGoldSetReader,
    _CliRetrievalRunnerPort,
    PostgresAuditAdapter,
]:
    """Build every dependency the runner orchestrator needs."""
    bound_tenant_id = TenantId(str(wiring.tenant_context.tenant_id))

    async def _resolver(_tid):
        return wiring.session_factory

    run_repo = PostgresEvaluationRunRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    run_reader = PostgresEvaluationRunReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    gold_set_reader = PostgresGoldSetReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )

    embedder = LiteLLMChunkEmbedder()
    vector_search = PgVectorSearch(
        session_factory=wiring.session_factory, embedder=embedder
    )
    retrieval_client = _CliCompositeRetrievalClient(vector_search=vector_search)
    agent_adapter = AgentRetrievalClientAdapter(retrieval_client=retrieval_client)
    runner_port = _CliRetrievalRunnerPort(adapter=agent_adapter)

    # PostgresAuditAdapter.from_settings constructs the control-plane
    # engine via the audit module's _control_plane_url helper, avoiding
    # a non-existent attribute on ControlPlaneSettings (runtime fix at
    # S40 smoke per the operator's flagged-CLI-audit-connection-risk
    # disposition: fix inline, capture as methodology finding). The
    # control-plane connection is required at adapter init but unused
    # for the runner's emissions (all events carry non-empty tenant_id
    # and route to the per-tenant audit table).
    audit_adapter = PostgresAuditAdapter.from_settings(
        control_plane_settings=ControlPlaneSettings(),
        per_tenant_sessionmaker_resolver=_resolver,
    )
    return run_repo, run_reader, gold_set_reader, runner_port, audit_adapter


@evaluation_run_app.command("start")
def cmd_evaluation_run_start(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    gold_set_id: Annotated[
        UUID, typer.Option("--gold-set-id", help="Gold set to exercise.")
    ],
    invoked_by: Annotated[
        str,
        typer.Option(
            "--invoked-by",
            help="Invocation actor for the audit trail.",
        ),
    ] = "cli-operator",
) -> None:
    """Start an evaluation run; block until completion or failure."""
    wiring = build_tenant_wiring(tenant_id)
    (
        run_repo,
        _run_reader,
        gold_set_reader,
        runner_port,
        audit_adapter,
    ) = _build_runner_dependencies(wiring)

    async def _go() -> None:
        try:
            result = await run_retrieval_evaluation(
                tenant_context=wiring.tenant_context,
                gold_set_id=gold_set_id,
                invoked_by_user_id=invoked_by,
                reader=gold_set_reader,
                repository=run_repo,
                retrieval_runner=runner_port,
                audit_port=audit_adapter,
            )
            typer.echo(f"evaluation_run_id={result.run.id}")
            typer.echo(f"status={result.run.status.value}")
            typer.echo(
                f"completed_at={result.run.completed_at.isoformat() if result.run.completed_at else '(none)'}"
            )
            typer.echo(f"per_query_results={len(result.results)}")
            typer.echo(f"per_strategy_aggregates={len(result.aggregates)}")
            for aggregate in result.aggregates:
                typer.echo(
                    f"  strategy={aggregate.retrieval_strategy} "
                    f"recall_mean={aggregate.recall_at_k_mean} "
                    f"precision_mean={aggregate.precision_at_k_mean} "
                    f"mrr_mean={aggregate.mrr_mean} "
                    f"latency_p50={aggregate.latency_ms_p50}ms "
                    f"latency_p95={aggregate.latency_ms_p95}ms"
                )
        except GoldSetNotFoundError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=2)
        except GoldSetMissingFinalizedRevisionError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=3)
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@evaluation_run_app.command("get")
def cmd_evaluation_run_get(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    run_id: Annotated[
        UUID, typer.Option("--run-id", help="Evaluation run to display.")
    ],
) -> None:
    """Show run aggregate plus per-query results plus per-strategy aggregates."""
    wiring = build_tenant_wiring(tenant_id)
    (
        _run_repo,
        run_reader,
        _gold_set_reader,
        _runner_port,
        audit_adapter,
    ) = _build_runner_dependencies(wiring)

    async def _go() -> None:
        try:
            snapshot = await get_evaluation_run(
                tenant_context=wiring.tenant_context,
                run_id=run_id,
                reader=run_reader,
            )
            if snapshot is None:
                typer.echo("evaluation run not found", err=True)
                raise typer.Exit(code=2)
            run = snapshot.run
            typer.echo(f"id={run.id}")
            typer.echo(f"status={run.status.value}")
            typer.echo(f"gold_set_id={run.gold_set_id}")
            typer.echo(f"gold_set_revision_id={run.gold_set_revision_id}")
            typer.echo(f"invoked_at={run.invoked_at.isoformat()}")
            if run.completed_at is not None:
                typer.echo(f"completed_at={run.completed_at.isoformat()}")
            typer.echo(f"per-query results ({len(snapshot.results)}):")
            for r in snapshot.results:
                typer.echo(
                    f"  entry={r.gold_set_entry_id} strategy={r.retrieval_strategy} "
                    f"mrr={r.mrr} latency={r.latency_ms}ms "
                    f"returned={len(r.returned_chunk_ids)} chunks"
                )
            typer.echo(f"per-strategy aggregates ({len(snapshot.aggregates)}):")
            for a in snapshot.aggregates:
                typer.echo(
                    f"  strategy={a.retrieval_strategy}\n"
                    f"      recall_mean={a.recall_at_k_mean}\n"
                    f"      precision_mean={a.precision_at_k_mean}\n"
                    f"      mrr_mean={a.mrr_mean}\n"
                    f"      latency_ms_p50={a.latency_ms_p50} "
                    f"p95={a.latency_ms_p95} mean={a.latency_ms_mean}"
                )
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@evaluation_run_app.command("list")
def cmd_evaluation_run_list(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    page_size: Annotated[
        int, typer.Option("--page-size", help="Rows per page (max 50).")
    ] = 20,
    cursor: Annotated[
        Optional[str],
        typer.Option("--cursor", help="Opaque pagination cursor."),
    ] = None,
) -> None:
    """List evaluation runs for the tenant (paginated)."""
    wiring = build_tenant_wiring(tenant_id)
    (
        _run_repo,
        run_reader,
        _gold_set_reader,
        _runner_port,
        audit_adapter,
    ) = _build_runner_dependencies(wiring)

    async def _go() -> None:
        try:
            page, next_cursor = await list_evaluation_runs(
                tenant_context=wiring.tenant_context,
                reader=run_reader,
                encoded_cursor=cursor,
                page_size=page_size,
            )
            if not page.runs:
                typer.echo("(no evaluation runs)")
                return
            for run in page.runs:
                typer.echo(
                    f"{run.id}  status={run.status.value}  "
                    f"invoked_at={run.invoked_at.isoformat()}  "
                    f"gold_set_id={run.gold_set_id}"
                )
            if next_cursor is not None:
                typer.echo(f"next_cursor={next_cursor}")
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


__all__ = ["evaluation_run_app", "retrieval_evaluation_app"]
