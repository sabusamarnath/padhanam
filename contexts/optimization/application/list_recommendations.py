"""list_recommendations read use case (D111 commitments 3, 4).

Paginated, filtered read. The codec at ``cursors.py`` mediates the
opaque base64 cursor at the future HTTP boundary; the use case
accepts a string cursor and decodes on entry, returning a string
cursor on the next page for the caller to round-trip back.
"""

from __future__ import annotations

from contexts.optimization.application.cursors import (
    decode_recommendation_cursor,
    encode_recommendation_cursor,
)
from contexts.optimization.domain.query_filters import (
    PAGE_SIZE_CEILING,
    RecommendationListFilters,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationListPage,
    RecommendationReader,
)
from shared_kernel.tenant_context import TenantContext


async def list_recommendations(
    *,
    tenant_context: TenantContext,
    reader: RecommendationReader,
    filters: RecommendationListFilters,
    encoded_cursor: str | None,
    page_size: int,
) -> tuple[RecommendationListPage, str | None]:
    """List recommendations with category/status filtering.

    Returns the page plus the optional next-cursor encoded string.
    The page-size ceiling is checked here; out-of-range values raise
    ``ValueError``.
    """
    if not (1 <= page_size <= PAGE_SIZE_CEILING):
        raise ValueError(
            f"page_size must be in [1, {PAGE_SIZE_CEILING}]; got {page_size}"
        )
    cursor = (
        decode_recommendation_cursor(encoded_cursor)
        if encoded_cursor
        else None
    )
    page = await reader.list_recommendations(
        tenant_context=tenant_context,
        filters=filters,
        cursor=cursor,
        page_size=page_size,
    )
    next_encoded = (
        encode_recommendation_cursor(page.next_cursor)
        if page.next_cursor is not None
        else None
    )
    return page, next_encoded


__all__ = ["list_recommendations"]
