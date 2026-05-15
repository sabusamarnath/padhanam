"""list_gold_sets use case (D109 commitment 6).

Thin pass-through to ``GoldSetReader.list_gold_sets`` with the
opaque-cursor codec at ``contexts/retrieval_evaluation/application/cursor.py``
mediating the HTTP boundary. The use case validates the page-size
ceiling at the cursor's __post_init__ and raises MalformedCursorError
on decode failure.
"""

from __future__ import annotations

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.application.cursor import decode, encode
from contexts.retrieval_evaluation.domain.query_filters import (
    GoldSetListCursor,
    PAGE_SIZE_CEILING,
)
from contexts.retrieval_evaluation.ports.reader import (
    GoldSetListPage,
    GoldSetReader,
)


async def list_gold_sets(
    *,
    tenant_context: TenantContext,
    reader: GoldSetReader,
    encoded_cursor: str | None = None,
    page_size: int = PAGE_SIZE_CEILING,
) -> tuple[GoldSetListPage, str | None]:
    """List gold sets for a tenant, returning the page plus next-cursor (encoded).

    ``encoded_cursor`` is None on the first page; subsequent pages
    pass the prior page's encoded next-cursor verbatim.
    """
    cursor: GoldSetListCursor | None = (
        decode(encoded_cursor) if encoded_cursor else None
    )
    effective_page_size = cursor.page_size if cursor else page_size

    page = await reader.list_gold_sets(
        tenant_context=tenant_context,
        cursor=cursor,
        page_size=effective_page_size,
    )
    next_encoded = encode(page.next_cursor) if page.next_cursor else None
    return page, next_encoded
