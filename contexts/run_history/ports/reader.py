"""RunHistoryReader query port + RunListPage envelope (D17, D97, S33).

The producer-side query port shaped to the eventual HTTP API at
S34/S35. Two methods per D97:

- ``get_run(tenant_context, run_id) -> RunRecord | None`` returns
  the run as an aggregate with chunk and entity citations attached
  (per S32's D96 extension of ``RunRecord``). Returns ``None`` when
  the run-id is not present on the routed tenant; the HTTP layer
  translates to 404 cleanly.

- ``list_runs_with_filters(tenant_context, filters, cursor) ->
  RunListPage`` returns a page of runs (no citations attached at
  list-view altitude; the ``RunRecord`` instances are constructed
  with empty citation tuples) plus the optional next-page cursor.

Read-DTO symmetry with the write side: the same ``RunRecord`` type
that the writer adapter persists travels back through the reader
adapter. The drafted ``RunWithCitations`` wrapper from the S33
brief was rejected at session-open reconciliation per D97
alternative (k); ``RunRecord`` already aggregates the citation
tuples from S32's D96 extension, so a read-side wrapper would
duplicate fields without value.

Port location at the producer context per the S22 ``RetrievalClient``
precedent. The consumer at S34/S35 is the HTTP API (a composition
surface), not a bounded context; the HTTP layer dependency-injects
the reader through this port. No cross-context wiring adapter is
needed because the consumer is not a context.

``RunListPage`` lives alongside the port because it is the port's
output envelope binding the query result shape; the consumer
projects render shape per the storage-versus-render discipline at
the port boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from contexts.run_history.domain.query_filters import (
    RunListCursor,
    RunListFilters,
)
from contexts.run_history.domain.run_record import RunRecord
from shared_kernel import TenantContext


@dataclass(frozen=True)
class RunListPage:
    """Query-result envelope for ``list_runs_with_filters`` (D97).

    ``runs`` carries the page of ``RunRecord`` instances constructed
    with empty citation tuples (the list-view altitude does not
    fetch citations per D97). ``next_cursor`` is ``None`` when no
    further pages exist; the adapter detects this by selecting
    ``LIMIT page_size + 1`` and dropping the overflow row when
    constructing the next-cursor from the last in-page row.
    """

    runs: tuple[RunRecord, ...]
    next_cursor: RunListCursor | None


class RunHistoryReader(Protocol):
    """Read-side query port for the run-history context (D97).

    Tenant scoping flows through the ``TenantContext`` parameter
    plus the bound-tenant-id defence-in-depth check the adapter
    enforces against the routed session. The port surface is
    unaware of session resolution; the implementation owns the
    routing-plus-validation step before any query lands.

    Auth is not enforced at the port surface: the HTTP layer at
    S34/S35 performs authentication and authorisation before the
    dependency-injected reader is invoked. The pattern mirrors
    the S22 ``RetrievalClient`` precedent where the port takes
    ``TenantContext`` rather than ``Principal``.
    """

    async def get_run(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
    ) -> RunRecord | None:
        """Return the run as an aggregate (run + citations) or None.

        The returned ``RunRecord`` carries ``chunk_citations`` and
        ``entity_citations`` tuples populated from the joined
        per-tenant tables; citations are sorted by ``id ASC`` for
        stable rendering per D97 alternative (l). The consumer
        renders citation excerpts and entity displays at Phase 2
        UX time per the storage-versus-render discipline.
        """
        ...

    async def list_runs_with_filters(
        self,
        *,
        tenant_context: TenantContext,
        filters: RunListFilters,
        cursor: RunListCursor | None,
    ) -> RunListPage:
        """Return a page of runs plus optional next-page cursor.

        Initial-page invocations pass ``cursor=None``; the adapter
        treats this as "newest run, page-size-many results" using
        the page-size default (the brief settled at 50 per D97).
        Subsequent-page invocations pass the previous page's
        ``next_cursor``; the adapter uses tuple comparison on
        ``(started_at, id)`` so equal-timestamp runs paginate
        stably under concurrent insert pressure.

        Sort order is fixed at ``started_at DESC, id DESC`` per
        D97. The ``RunRecord`` instances returned carry empty
        citation tuples; the list-view altitude does not fetch
        citations per D97's bounded-cardinality argument.
        """
        ...


__all__ = [
    "RunHistoryReader",
    "RunListPage",
]
