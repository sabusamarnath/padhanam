"""register_source — upload-side use case (D60).

The CLI / HTTP-API caller hands in raw bytes plus file metadata
(name, declared file_type, the actor's user id), and the use case:

  1. Validates the file_type is supported per D61 (rejects PDF /
     DOCX / HTML at the upload-time gate before they ever reach
     the worker).
  2. Constructs a Source aggregate in RECEIVED state.
  3. Persists it through SourceRepositoryPort.save_source.
  4. Returns the persisted source id.

The use case is pure orchestration — no IO logic beyond the port
call. The composition layer (the CLI's _ingest module) is
responsible for reading the file from disk and constructing the
TenantContext.

UnsupportedFileTypeError is raised when the file_type is not in
SUPPORTED_FILE_TYPES; the CLI surface catches it and emits a
clear validation message before the worker pulls the source per
the brief's acceptance criterion 7.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.ingestion.application.parser_dispatch import (
    SUPPORTED_FILE_TYPES,
    is_supported_file_type,
)
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState
from contexts.ingestion.ports.source_repository_port import SourceRepositoryPort


class UnsupportedFileTypeError(ValueError):
    """Raised by register_source when the declared file_type is not
    one of the parser-supported types per D61. The CLI catches this
    and emits a clear validation error before the worker pulls
    the source.
    """


async def register_source(
    *,
    repository: SourceRepositoryPort,
    tenant_id: str,
    jurisdiction: str,
    file_name: str,
    file_type: str,
    raw_content: bytes,
    created_by_user_id: str,
) -> UUID:
    """Persist a new Source row in RECEIVED state.

    Returns the source id. Raises UnsupportedFileTypeError when
    the file_type is not supported per D61.
    """
    if not is_supported_file_type(file_type):
        raise UnsupportedFileTypeError(
            f"file_type {file_type!r} is not supported at S19; "
            f"D61 ships parsers for {sorted(SUPPORTED_FILE_TYPES)}. "
            f"PDF, DOCX, HTML defer to sessions with real consumers."
        )
    now = datetime.now(timezone.utc)
    source = Source(
        id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        file_name=file_name,
        file_type=file_type,
        file_size_bytes=len(raw_content),
        raw_content=raw_content,
        state=SourceState.RECEIVED,
        parsing_error_text=None,
        created_by_user_id=created_by_user_id,
        created_at=now,
        updated_at=now,
    )
    return await repository.save_source(source)
