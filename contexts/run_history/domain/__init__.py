"""Run-history domain layer (D17, D95, D96, D97).

Domain value objects:

- ``RunRecord`` at ``run_record.py`` carries the 15-column ``runs``
  table shape per D95 plus the citation tuples per D96.
- ``ChunkCitationRecord`` and ``EntityCitationRecord`` at
  ``citation_records.py`` mirror the agent-context citation
  candidates one-for-one per the D54 mirror-types pattern; the
  wiring adapter translates at the producer-side boundary.
- ``RunListFilters`` and ``RunListCursor`` at ``query_filters.py``
  carry the read-port filter dimensions and pagination cursor
  shape per D97; ``MalformedCursorError`` raises at decode time
  on cursor reconstruction failure.

All value objects enforce invariants in ``__post_init__`` so the
writer adapter cannot persist a row, and the reader adapter cannot
issue a query, that fails the domain rules.
"""

from contexts.run_history.domain.citation_records import (
    ChunkCitationRecord,
    EntityCitationRecord,
)
from contexts.run_history.domain.query_filters import (
    PAGE_SIZE_CEILING,
    MalformedCursorError,
    RunListCursor,
    RunListFilters,
)
from contexts.run_history.domain.run_record import RunRecord

__all__ = [
    "ChunkCitationRecord",
    "EntityCitationRecord",
    "MalformedCursorError",
    "PAGE_SIZE_CEILING",
    "RunListCursor",
    "RunListFilters",
    "RunRecord",
]
