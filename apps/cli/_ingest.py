"""Async ingest orchestration for the CLI (S19).

Two top-level coroutines:

  - ``run_ingest_run``: read the file from disk, validate the
    extension, derive the file_type, and call register_source.
    Returns the persisted source id.

  - ``run_ingest_worker``: long-running worker loop that polls the
    tenant's pending-source queue via SourceRepositoryPort.
    claim_pending_for_parse, dispatches to the right parser via
    the adapter registry, writes chunks atomically with the state
    transition. Lands at S19 commit 6.

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

The file-reading logic and tenant_context plumbing sit in this
module rather than the application layer because both are
composition concerns. The application use case takes raw bytes
and a tenant_id; the CLI is responsible for reading and resolving.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from contexts.ingestion.adapters.outbound.postgres.source_repository import (
    PostgresSourceRepository,
)
from contexts.ingestion.application.parser_dispatch import (
    file_type_for_extension,
)
from contexts.ingestion.application.register_source import (
    UnsupportedFileTypeError,
    register_source,
)

from apps.cli._runtime import build_tenant_wiring


_DEFAULT_USER_ID = "cli-operator"


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
