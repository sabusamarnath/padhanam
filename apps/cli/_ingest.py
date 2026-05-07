"""Async ingest orchestration for the CLI (S19).

Two top-level coroutines:

  - ``run_ingest_run``: read the file from disk, validate the
    extension, derive the file_type, and call register_source.
    Returns the persisted source id.

  - ``run_ingest_worker``: long-running worker loop that polls the
    tenant's pending-source queue via SourceRepositoryPort.
    claim_pending_for_parse, dispatches to the right parser via
    the adapter registry, writes chunks atomically with the state
    transition. Exits gracefully on SIGINT / SIGTERM via
    asyncio's signal-handler integration.

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

from contexts.ingestion.adapters.outbound.parsers import get_parser
from contexts.ingestion.adapters.outbound.postgres.source_repository import (
    PostgresSourceRepository,
)
from contexts.ingestion.application.parser_dispatch import (
    file_type_for_extension,
)
from contexts.ingestion.application.parse_source import parse_source
from contexts.ingestion.application.register_source import (
    UnsupportedFileTypeError,
    register_source,
)
from padhanam.observability import init_tracing

from apps.cli._runtime import build_tenant_wiring


_DEFAULT_USER_ID = "cli-operator"
_DEFAULT_POLL_INTERVAL_SECONDS = 1.0


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
) -> int:
    """Long-running worker that drains the tenant's pending sources.

    Returns the number of sources processed (parsed or failed).
    ``max_iterations`` is for tests only — production invocations
    leave it None and let the SIGINT/SIGTERM handler drive shutdown.
    """
    # Wire OTel TracerProvider so worker-emitted spans (parse stage,
    # chunk-write stage) flow to Langfuse. The worker is the fourth
    # caller of init_tracing per the S18 reflection's promotion-
    # threshold note; helper lives at padhanam/observability/init_tracing.
    provider = init_tracing("padhanam-ingestion-worker")
    wiring = build_tenant_wiring(tenant_id)
    repository = PostgresSourceRepository(wiring.session_factory)

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

    processed = 0
    iteration = 0
    try:
        while not shutdown_event.is_set():
            if max_iterations is not None and iteration >= max_iterations:
                break
            iteration += 1

            claimed = await repository.claim_pending_for_parse(
                str(wiring.tenant_context.tenant_id)
            )
            if claimed is None:
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
                continue

            _log.info(
                "worker: claimed source %s (file_name=%s, file_type=%s)",
                claimed.id,
                claimed.file_name,
                claimed.file_type,
            )
            result = await parse_source(
                source=claimed,
                repository=repository,
                parser_resolver=get_parser,
            )
            processed += 1
            if result.final_state.value == "failed":
                _log.warning(
                    "worker: source %s parse failed: %s",
                    result.source_id,
                    result.parsing_error_text,
                )
            else:
                _log.info(
                    "worker: source %s parsed (%d chunks)",
                    result.source_id,
                    result.chunks_written,
                )
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
        await wiring.engine.dispose()

    return processed
