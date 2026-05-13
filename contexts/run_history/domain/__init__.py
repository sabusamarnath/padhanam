"""Run-history domain layer (D17, D95, D96).

Three domain value objects:

- ``RunRecord`` at ``run_record.py`` carries the 15-column ``runs``
  table shape per D95 plus the citation tuples per D96.
- ``ChunkCitationRecord`` and ``EntityCitationRecord`` at
  ``citation_records.py`` mirror the agent-context citation
  candidates one-for-one per the D54 mirror-types pattern; the
  wiring adapter translates at the producer-side boundary.

All three enforce invariants in ``__post_init__`` so the writer
adapter cannot persist a row that fails the domain rules.
"""

from contexts.run_history.domain.citation_records import (
    ChunkCitationRecord,
    EntityCitationRecord,
)
from contexts.run_history.domain.run_record import RunRecord

__all__ = [
    "ChunkCitationRecord",
    "EntityCitationRecord",
    "RunRecord",
]
