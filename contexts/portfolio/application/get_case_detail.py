"""get_case_detail read use case (D124).

Composes the reader's case lookup and per-case DataPoint listing
into a single ``CaseDetail`` result — the Case plus its DataPoints,
each carrying its full revision history. Returns ``None`` when the
case does not exist for the tenant.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contexts.portfolio.domain import Case, DataPoint
from contexts.portfolio.ports import PortfolioReader
from shared_kernel import TenantContext


@dataclass(frozen=True)
class CaseDetail:
    """A Case plus its DataPoints, each carrying its revision history."""

    case: Case
    data_points: tuple[DataPoint, ...]


async def get_case_detail(
    *,
    tenant_context: TenantContext,
    reader: PortfolioReader,
    case_id: UUID,
) -> CaseDetail | None:
    """Return the Case plus its DataPoints, or None when absent."""
    case = await reader.get_case(
        tenant_context=tenant_context, case_id=case_id
    )
    if case is None:
        return None
    data_points = await reader.list_data_points(
        tenant_context=tenant_context, case_id=case_id
    )
    return CaseDetail(case=case, data_points=data_points)


__all__ = ["CaseDetail", "get_case_detail"]
