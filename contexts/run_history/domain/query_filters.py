"""Query filter and cursor value objects for the read surface (D97, S33).

Three frozen dataclasses and one domain exception together shape the
read port's inputs at ``contexts/run_history/ports/reader.py``.

``RunListFilters`` carries four optional filter dimensions:

- ``agent_template_ids``: multi-value match against ``runs.agent_template_id``.
- ``agent_template_versions``: multi-value match against
  ``runs.agent_template_version``; applied alongside
  ``agent_template_ids`` per D97.
- ``started_at_range``: inclusive lower, exclusive upper datetime
  tuple; the lower bound must be strictly earlier than the upper.
- ``termination_reasons``: multi-value match against the D95 six-
  value CHECK set on ``runs.termination_reason``.

Empty tuples normalise to ``None`` in ``__post_init__`` so the
adapter consistently treats "no values" as "no filter" rather than
"match nothing." Allowing both representations at the public
boundary would force every consumer to encode the same normalisation
rule; collapsing at construction time is the structural-honest
shape.

``RunListCursor`` encodes ``(started_at, id, page_size)``. The
encoded form is base64-encoded JSON per D97 so cursor strings survive
the HTTP boundary at S34/S35. ``page_size`` caps at the page-size
ceiling settled at D97 (50); the construction-time validation
rejects out-of-range values. The encode/decode helpers live at
``contexts/run_history/application/cursor.py``.

``MalformedCursorError`` raises at decode time on base64, JSON,
schema, or type errors so the HTTP layer at S34/S35 translates to
400 cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.run_history.domain.run_record import TERMINATION_REASONS


PAGE_SIZE_CEILING: int = 50


class MalformedCursorError(Exception):
    """Raised when ``decode`` cannot reconstruct a ``RunListCursor``.

    Covers base64 errors, malformed JSON, missing required fields,
    wrong field types, and out-of-range ``page_size``. The HTTP
    layer at S34/S35 translates to 400; the port surface raises
    rather than returning a sentinel so the HTTP layer's exception
    handler is the single translation point.
    """


@dataclass(frozen=True)
class RunListFilters:
    """Optional filter dimensions for ``list_runs_with_filters`` (D97).

    Empty tuples normalise to ``None`` in ``__post_init__``. The
    invariants enforce per-field constraints at construction time
    so the adapter does not re-validate.
    """

    agent_template_ids: tuple[UUID, ...] | None = None
    agent_template_versions: tuple[int, ...] | None = None
    started_at_range: tuple[datetime, datetime] | None = None
    termination_reasons: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.agent_template_ids is not None and len(self.agent_template_ids) == 0:
            object.__setattr__(self, "agent_template_ids", None)
        if self.agent_template_versions is not None and len(self.agent_template_versions) == 0:
            object.__setattr__(self, "agent_template_versions", None)
        if self.termination_reasons is not None and len(self.termination_reasons) == 0:
            object.__setattr__(self, "termination_reasons", None)

        if self.started_at_range is not None:
            lower, upper = self.started_at_range
            if lower >= upper:
                raise ValueError(
                    "started_at_range lower bound must be strictly earlier "
                    f"than upper bound; got lower={lower.isoformat()} "
                    f"upper={upper.isoformat()}"
                )

        if self.termination_reasons is not None:
            for reason in self.termination_reasons:
                if reason not in TERMINATION_REASONS:
                    raise ValueError(
                        "termination_reasons values must be members of the "
                        f"D95 six-value CHECK set {sorted(TERMINATION_REASONS)}; "
                        f"got {reason!r}"
                    )


@dataclass(frozen=True)
class RunListCursor:
    """Pagination cursor on ``(started_at, id, page_size)`` (D97).

    Tuple comparison against ``(started_at, id)`` paginates stably
    against the ``started_at DESC, id DESC`` sort order. ``page_size``
    must be in ``[1, PAGE_SIZE_CEILING]``; out-of-range values raise
    at construction time so the adapter cannot send a malformed
    LIMIT.

    The cursor is opaque to consumers at the HTTP boundary; the
    base64 + JSON encoding via ``contexts.run_history.application.cursor``
    is the serialisation shape.
    """

    started_at: datetime
    id: UUID
    page_size: int

    def __post_init__(self) -> None:
        if not (1 <= self.page_size <= PAGE_SIZE_CEILING):
            raise ValueError(
                f"page_size must be in [1, {PAGE_SIZE_CEILING}]; "
                f"got {self.page_size}"
            )


__all__ = [
    "MalformedCursorError",
    "PAGE_SIZE_CEILING",
    "RunListCursor",
    "RunListFilters",
]
