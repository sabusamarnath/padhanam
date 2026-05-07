"""Async ingest orchestration for the CLI (S19, S20, S21).

Two top-level coroutines:

  - ``run_ingest_run``: read the file from disk, validate the
    extension, derive the file_type, and call register_source.
    Returns the persisted source id.

  - ``run_ingest_worker``: long-running worker loop that drains
    the tenant's pipeline. Per iteration the worker first tries to
    claim a ``received`` row (parse stage) via
    ``claim_pending_for_parse``; if none, it tries to claim a
    ``parsed`` row (embed stage per D62) via
    ``claim_pending_for_embed``; if neither, it tries to claim an
    ``embedded`` row (extract stage per D64) via
    ``claim_pending_for_extract``; if none of the three, it sleeps
    for the poll interval. The three-stage shape is the worker-
    loop extension D64 commits to: a single worker process drains
    all three stages, transitioning sources received → parsing →
    parsed → embedding → embedded → extracting → indexed. Exits
    gracefully on SIGINT / SIGTERM via asyncio's signal-handler
    integration.

run_ingest_run flow:
  1. Resolve tenant + session factory via build_tenant_wiring.
  2. Construct the Postgres source repository.
  3. Read raw bytes from disk (async via anyio? — at S19 the CLI
     is one-shot and the file reads are local, so a sync open()
     inside an asyncio coroutine is honest about the workload's
     shape).
  4. Resolve the file_type from the file extension via
     parser_dispatch.file_type_for_extension.
  5. Call register_source. Surface UnsupportedFileTypeError as a
     clear validation error.

run_ingest_worker flow:
  1. Resolve tenant + session factory via build_tenant_wiring.
  2. Construct the Postgres source repository plus the parser
     resolver from the adapter registry.
  3. Loop:
       - claim_pending_for_parse(tenant_id) — atomic claim via
         SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1.
       - if no row claimed: sleep for poll_interval_seconds.
       - if a row claimed: parse_source(...) and continue.
     The loop exits cleanly when the shutdown event fires (set by
     the SIGINT/SIGTERM handler) — pending claims complete, then
     the loop returns.

The file-reading logic and tenant_context plumbing sit in this
module rather than the application layer because both are
composition concerns. The application use cases take raw bytes,
domain types, and ports; the CLI is responsible for reading and
resolving.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path
from uuid import UUID

from contexts.ingestion.adapters.outbound.embedding import (
    LiteLLMChunkEmbedder,
)
from contexts.ingestion.adapters.outbound.extraction import (
    LiteLLMEntityExtractor,
)
from contexts.ingestion.adapters.outbound.neo4j import (
    Neo4jGraphRepository,
    make_async_driver,
)
from contexts.ingestion.adapters.outbound.parsers import get_parser
from contexts.ingestion.adapters.outbound.postgres.source_repository import (
    PostgresSourceRepository,
)
from contexts.ingestion.adapters.outbound.retrieval import (
    Neo4jTraverse,
    PgVectorSearch,
)
from contexts.ingestion.application.embed_source import embed_source
from contexts.ingestion.application.extract_source import extract_source
from contexts.ingestion.application.parser_dispatch import (
    file_type_for_extension,
)
from contexts.ingestion.application.parse_source import parse_source
from contexts.ingestion.application.register_source import (
    UnsupportedFileTypeError,
    register_source,
)
from contexts.ingestion.domain.chunk_result import ChunkResult
from contexts.ingestion.domain.entity_result import EntityResult
from padhanam.config import Neo4jSettings
from padhanam.observability import init_tracing

from apps.cli._runtime import build_tenant_wiring


_DEFAULT_USER_ID = "cli-operator"
_DEFAULT_POLL_INTERVAL_SECONDS = 1.0

# S21: stage filter for the worker. The default is "all three stages
# enabled"; tests that want to exercise only the parse + embed
# pipeline (i.e. preserve S20 semantics) pass the subset explicitly.
STAGE_PARSE = "parse"
STAGE_EMBED = "embed"
STAGE_EXTRACT = "extract"
ALL_STAGES = frozenset({STAGE_PARSE, STAGE_EMBED, STAGE_EXTRACT})


_log = logging.getLogger("apps.cli.ingest")


class CLIIngestError(Exception):
    """Raised by the CLI's ingest orchestration for user-facing
    validation errors. The CLI surface catches this and emits the
    message via typer's BadParameter / Exit, distinguishing user-
    fixable input errors from infrastructure faults that should
    bubble as crashes the operator notices.
    """


async def run_ingest_run(
    *,
    tenant_id: str,
    file_path: Path,
    user_id: str = _DEFAULT_USER_ID,
) -> UUID:
    """Register a single source from disk; return its id."""
    if not file_path.exists():
        raise CLIIngestError(f"file not found: {file_path}")
    if not file_path.is_file():
        raise CLIIngestError(f"not a regular file: {file_path}")

    extension = file_path.suffix
    file_type = file_type_for_extension(extension)
    if file_type is None:
        raise CLIIngestError(
            f"unsupported file extension {extension!r} for {file_path.name!r}; "
            f"S19 parsers handle .md / .markdown / .txt / .text per D61. "
            f"PDF, DOCX, HTML defer to sessions with real consumers."
        )

    raw_content = file_path.read_bytes()

    wiring = build_tenant_wiring(tenant_id)
    repository = PostgresSourceRepository(wiring.session_factory)
    try:
        try:
            return await register_source(
                repository=repository,
                tenant_id=str(wiring.tenant_context.tenant_id),
                jurisdiction=wiring.tenant_context.jurisdiction,
                file_name=file_path.name,
                file_type=file_type,
                raw_content=raw_content,
                created_by_user_id=user_id,
            )
        except UnsupportedFileTypeError as exc:
            raise CLIIngestError(str(exc)) from exc
    finally:
        await wiring.engine.dispose()


async def run_ingest_worker(
    *,
    tenant_id: str,
    poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL_SECONDS,
    max_iterations: int | None = None,
    stages: frozenset[str] = ALL_STAGES,
) -> int:
    """Long-running worker that drains the tenant's pending sources.

    Returns the number of sources processed (parsed or failed).
    ``max_iterations`` is for tests only — production invocations
    leave it None and let the SIGINT/SIGTERM handler drive shutdown.
    ``stages`` filters which stages the worker drains; the default
    is all three (parse, embed, extract) per D64. Passing a subset
    is useful for tests that want to scope the worker to specific
    stages without exercising downstream LLM-heavy paths.
    """
    if not stages.issubset(ALL_STAGES):
        unknown = stages - ALL_STAGES
        raise ValueError(
            f"unknown stages: {sorted(unknown)}; valid: {sorted(ALL_STAGES)}"
        )
    # Wire OTel TracerProvider so worker-emitted spans (parse stage,
    # chunk-write stage, embed stage) flow to Langfuse. The worker
    # is the fourth caller of init_tracing per the S18 reflection's
    # promotion-threshold note; helper lives at
    # padhanam/observability/init_tracing.
    provider = init_tracing("padhanam-ingestion-worker")
    wiring = build_tenant_wiring(tenant_id)
    repository = PostgresSourceRepository(wiring.session_factory)
    embedder = LiteLLMChunkEmbedder()
    extractor = LiteLLMEntityExtractor()
    graph_repository = Neo4jGraphRepository.from_settings(Neo4jSettings())

    shutdown_event = asyncio.Event()

    def _on_signal(signum: int, _frame=None) -> None:
        _log.info("worker: received signal %s, draining and exiting", signum)
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    handlers_installed: list[int] = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal, sig)
            handlers_installed.append(sig)
        except NotImplementedError:
            # Windows / some test environments. Fall through; the
            # max_iterations escape valve handles those callers.
            pass

    tenant_id_str = str(wiring.tenant_context.tenant_id)
    processed = 0
    iteration = 0
    try:
        while not shutdown_event.is_set():
            if max_iterations is not None and iteration >= max_iterations:
                break
            iteration += 1

            # S21 / D64: drain stages in pipeline order — parse,
            # embed, extract — so a single worker process keeps the
            # earlier stages from starving downstream stages. Each
            # iteration tries to claim from the earliest enabled
            # stage first; the per-stage gate respects the `stages`
            # filter so callers can scope which stages to drain.
            parse_claimed = (
                await repository.claim_pending_for_parse(tenant_id_str)
                if STAGE_PARSE in stages
                else None
            )
            if parse_claimed is not None:
                _log.info(
                    "worker: claimed source %s for parse (file_name=%s, "
                    "file_type=%s)",
                    parse_claimed.id,
                    parse_claimed.file_name,
                    parse_claimed.file_type,
                )
                parse_result = await parse_source(
                    source=parse_claimed,
                    repository=repository,
                    parser_resolver=get_parser,
                )
                processed += 1
                if parse_result.final_state.value == "failed":
                    _log.warning(
                        "worker: source %s parse failed: %s",
                        parse_result.source_id,
                        parse_result.parsing_error_text,
                    )
                else:
                    _log.info(
                        "worker: source %s parsed (%d chunks)",
                        parse_result.source_id,
                        parse_result.chunks_written,
                    )
                continue

            embed_claimed = (
                await repository.claim_pending_for_embed(tenant_id_str)
                if STAGE_EMBED in stages
                else None
            )
            if embed_claimed is not None:
                _log.info(
                    "worker: claimed source %s for embed (file_name=%s)",
                    embed_claimed.id,
                    embed_claimed.file_name,
                )
                embed_result = await embed_source(
                    source=embed_claimed,
                    repository=repository,
                    embedder=embedder,
                    tenant_context=wiring.tenant_context,
                )
                processed += 1
                if embed_result.final_state.value == "embedding_failed":
                    _log.warning(
                        "worker: source %s embed failed: %s",
                        embed_result.source_id,
                        embed_result.embedding_error_text,
                    )
                else:
                    _log.info(
                        "worker: source %s embedded (%d embeddings)",
                        embed_result.source_id,
                        embed_result.embeddings_written,
                    )
                continue

            extract_claimed = (
                await repository.claim_pending_for_extract(tenant_id_str)
                if STAGE_EXTRACT in stages
                else None
            )
            if extract_claimed is not None:
                _log.info(
                    "worker: claimed source %s for extract (file_name=%s)",
                    extract_claimed.id,
                    extract_claimed.file_name,
                )
                extract_result = await extract_source(
                    source=extract_claimed,
                    repository=repository,
                    extractor=extractor,
                    graph_repository=graph_repository,
                    tenant_context=wiring.tenant_context,
                )
                processed += 1
                if extract_result.final_state.value == "extraction_failed":
                    _log.warning(
                        "worker: source %s extract failed: %s",
                        extract_result.source_id,
                        extract_result.extraction_error_text,
                    )
                else:
                    _log.info(
                        "worker: source %s indexed (%d entities, %d relationships)",
                        extract_result.source_id,
                        extract_result.entities_written,
                        extract_result.relationships_written,
                    )
                continue

            # No claimable rows in any stage.
            if max_iterations is not None:
                # In bounded test runs, no rows means we're done.
                break
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass
    finally:
        for sig in handlers_installed:
            try:
                loop.remove_signal_handler(sig)
            except NotImplementedError:
                pass
        # Flush pending spans before the process exits — the
        # BatchSpanProcessor batches and a short-lived worker run
        # otherwise loses the tail.
        provider.force_flush(timeout_millis=5_000)
        await graph_repository.close()
        await wiring.engine.dispose()

    return processed


async def run_ingest_search(
    *,
    tenant_id: str,
    query: str,
    limit: int,
) -> list[ChunkResult]:
    """Vector retrieval against the tenant's chunks (S22 / D65).

    Embeds the query with EmbeddingTask.QUERY (via the LiteLLM
    embedder) and runs cosine-distance search against the HNSW
    index, scoped to chunks whose source has reached the indexed
    state. Returns the top-``limit`` ChunkResults ranked by
    similarity. The OTel TracerProvider is initialised so the
    embedding span flows to Langfuse with the tenant.* attributes.
    """
    provider = init_tracing("padhanam-ingestion-search")
    wiring = build_tenant_wiring(tenant_id)
    embedder = LiteLLMChunkEmbedder()
    adapter = PgVectorSearch(
        session_factory=wiring.session_factory,
        embedder=embedder,
    )
    try:
        results = await adapter.search_vector(
            query=query, scope=wiring.tenant_context, limit=limit
        )
    finally:
        provider.force_flush(timeout_millis=5_000)
        await wiring.engine.dispose()
    return list(results)


async def run_ingest_traverse(
    *,
    tenant_id: str,
    seed: str,
    depth: int,
) -> list[EntityResult]:
    """Graph traversal from a seed entity (S22 / D65).

    Reads the set of indexed chunk_ids from the tenant's Postgres,
    then traverses the shared Neo4j instance from the named seed
    via the TenantScopedNeo4jSession wrapper. Returns one
    EntityResult per reachable entity within ``depth`` hops, each
    carrying the relationship-type sequence along the shortest
    path from the seed. The seed itself surfaces with an empty
    path when its source chunks meet the readiness predicate.
    """
    provider = init_tracing("padhanam-ingestion-traverse")
    wiring = build_tenant_wiring(tenant_id)
    driver = make_async_driver(Neo4jSettings())
    adapter = Neo4jTraverse(
        driver=driver,
        pg_session_factory=wiring.session_factory,
    )
    try:
        results = await adapter.traverse_graph(
            seed=seed, scope=wiring.tenant_context, depth=depth
        )
    finally:
        provider.force_flush(timeout_millis=5_000)
        await driver.close()
        await wiring.engine.dispose()
    return list(results)
