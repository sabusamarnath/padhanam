"""Query filter, cursor, and page value objects for the read surface (D102, S36).

``AuditEventListFilters`` carries seven filter dimensions matching
the column shape of ``tenant_audit`` per ``charter/schema.md``:

- ``timestamp_range``: inclusive lower, exclusive upper datetime
  tuple. Single time-window dimension because the audit schema
  has a single ``timestamp`` column (point-in-time events, no
  duration); this differs from run_history's two-time-bound
  filter where ``runs.started_at`` and ``runs.completed_at`` are
  distinct columns.
- ``actor``: single-value exact match against ``tenant_audit.actor``.
- ``action_verbs``: multi-value match (categorical, low cardinality).
- ``resource_type``: single-value exact match. Required when
  ``resource_id`` is set; the pairing constraint fires at
  construction time per D102.
- ``resource_id``: single-value exact match. Only valid when
  ``resource_type`` is also supplied.
- ``correlation_id``: single-value exact match (high cardinality,
  individual request lookup).
- ``jurisdiction``: multi-value match (categorical, low cardinality).

Empty tuples normalise to ``None`` in ``__post_init__`` so the
adapter consistently treats "no values" as "no filter" rather
than "match nothing." Mirror the run_history convention.

``AuditEventListCursor`` encodes ``(timestamp, id, page_size)``
for tuple-comparison pagination on the ``(timestamp DESC, id
DESC)`` sort order. ``page_size`` caps at ``PAGE_SIZE_CEILING``
(50, matching run_history). The encode/decode helpers live at
``contexts/audit/application/cursor.py``.

``AuditEventListPage`` is the read port's return type for
``list_audit_events_with_filters``: the events tuple, the
optional next cursor, and the page-level chain integrity
verification per D102.

``MalformedCursorError`` raises at decode time on base64, JSON,
schema, or type errors so the HTTP layer at S37 translates to
400 cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.audit.domain.audit_event_record import AuditEventRecord
from contexts.audit.domain.chain_integrity import ChainIntegrityVerification


PAGE_SIZE_CEILING: int = 50


class MalformedCursorError(Exception):
    """Raised when ``decode`` cannot reconstruct an ``AuditEventListCursor``.

    Covers base64 errors, malformed JSON, missing required
    fields, wrong field types, and out-of-range ``page_size``.
    The HTTP layer at S37 translates to 400; the port surface
    raises rather than returning a sentinel so the HTTP layer's
    exception handler is the single translation point. Mirror
    of ``contexts.run_history.domain.query_filters.MalformedCursorError``.
    """


@dataclass(frozen=True)
class AuditEventListFilters:
    """Optional filter dimensions for ``list_audit_events_with_filters`` (D102).

    Seven optional dimensions; empty tuples normalise to ``None``
    in ``__post_init__``. The pairing constraint between
    ``resource_type`` and ``resource_id`` fires at construction
    time so the adapter does not re-validate.
    """

    timestamp_range: tuple[datetime, datetime] | None = None
    actor: str | None = None
    action_verbs: tuple[str, ...] | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    correlation_id: str | None = None
    jurisdiction: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.action_verbs is not None and len(self.action_verbs) == 0:
            object.__setattr__(self, "action_verbs", None)
        if self.jurisdiction is not None and len(self.jurisdiction) == 0:
            object.__setattr__(self, "jurisdiction", None)

        if self.timestamp_range is not None:
            lower, upper = self.timestamp_range
            if lower >= upper:
                raise ValueError(
                    "timestamp_range lower bound must be strictly earlier "
                    f"than upper bound; got lower={lower.isoformat()} "
                    f"upper={upper.isoformat()}"
                )

        if self.resource_id is not None and self.resource_type is None:
            raise ValueError(
                "resource_id filter requires resource_type to also be set; "
                "resource_id without resource_type is ambiguous because "
                "the same id may appear under multiple resource types"
            )

        for single_field in ("actor", "resource_type", "resource_id", "correlation_id"):
            value = getattr(self, single_field)
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(
                    f"AuditEventListFilters.{single_field} must be a non-empty "
                    f"string when set; got {value!r}"
                )


@dataclass(frozen=True)
class AuditEventListCursor:
    """Pagination cursor on ``(timestamp, id, page_size)`` (D102).

    Tuple comparison against ``(timestamp, id)`` paginates stably
    against the ``timestamp DESC, id DESC`` sort order.
    ``page_size`` must be in ``[1, PAGE_SIZE_CEILING]``; out-of-
    range values raise at construction time so the adapter
    cannot send a malformed LIMIT.

    Opaque to consumers at the HTTP boundary; the base64 + JSON
    encoding via ``contexts.audit.application.cursor`` is the
    serialisation shape.
    """

    timestamp: datetime
    id: UUID
    page_size: int

    def __post_init__(self) -> None:
        if not (1 <= self.page_size <= PAGE_SIZE_CEILING):
            raise ValueError(
                f"page_size must be in [1, {PAGE_SIZE_CEILING}]; "
                f"got {self.page_size}"
            )


@dataclass(frozen=True)
class AuditEventListPage:
    """Return value of ``list_audit_events_with_filters`` (D102).

    Pairs the returned events with the optional next cursor and
    with the page-level ``ChainIntegrityVerification``. The
    chain-integrity status is mandatory on every page; the
    adapter computes it inline on the returned events before
    returning the page.
    """

    events: tuple[AuditEventRecord, ...]
    next_cursor: AuditEventListCursor | None
    chain_integrity: ChainIntegrityVerification


__all__ = [
    "AuditEventListCursor",
    "AuditEventListFilters",
    "AuditEventListPage",
    "MalformedCursorError",
    "PAGE_SIZE_CEILING",
]
