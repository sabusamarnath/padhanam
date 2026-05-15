"""list_evaluation_runs use case (D110 cursor-paginated read surface)."""

from __future__ import annotations

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.application.cursor import (
    decode_run_cursor,
    encode_run_cursor,
)
from contexts.retrieval_evaluation.domain.query_filters import (
    PAGE_SIZE_CEILING,
    EvaluationRunListCursor,
)
from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunListPage,
    EvaluationRunReader,
)


_DEFAULT_PAGE_SIZE: int = 20


async def list_evaluation_runs(
    *,
    tenant_context: TenantContext,
    reader: EvaluationRunReader,
    encoded_cursor: str | None,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> tuple[EvaluationRunListPage, str | None]:
    """Return one page of evaluation runs plus an encoded next-cursor."""
    if page_size < 1 or page_size > PAGE_SIZE_CEILING:
        raise ValueError(
            f"page_size must be in 1..{PAGE_SIZE_CEILING}, got {page_size}"
        )
    cursor: EvaluationRunListCursor | None = None
    if encoded_cursor is not None:
        cursor = decode_run_cursor(encoded_cursor)
    page = await reader.list_runs(
        tenant_context=tenant_context,
        cursor=cursor,
        page_size=page_size,
    )
    next_encoded = (
        encode_run_cursor(page.next_cursor) if page.next_cursor is not None else None
    )
    return page, next_encoded


__all__ = ["list_evaluation_runs"]
