"""Retrieval evaluation application layer (D109 commitment 6).

Five use cases covering the gold-set authoring path:

- ``create_gold_set`` — aggregate root plus initial draft revision.
- ``append_entry_to_revision`` — append to current draft; opens a
  new draft lazily if the prior revision is finalized.
- ``finalize_revision`` — transitions draft to finalized; computes
  ``this_event_hash`` via the platform hash-chain primitive.
- ``list_gold_sets`` — paginated read with opaque cursor.
- ``get_gold_set`` — aggregate snapshot at the current finalized
  revision.

Cursor codec at ``cursor.py`` mediates the HTTP boundary at S42.
"""

from contexts.retrieval_evaluation.application.append_entry_to_revision import (
    AppendEntryResult,
    GoldSetNotFoundError,
    append_entry_to_revision,
)
from contexts.retrieval_evaluation.application.create_gold_set import (
    CreateGoldSetResult,
    create_gold_set,
)
from contexts.retrieval_evaluation.application.finalize_revision import (
    EmptyDraftError,
    FinalizeRevisionResult,
    NoDraftToFinalizeError,
    finalize_revision,
)
from contexts.retrieval_evaluation.application.get_gold_set import get_gold_set
from contexts.retrieval_evaluation.application.list_gold_sets import (
    list_gold_sets,
)

__all__ = [
    "AppendEntryResult",
    "CreateGoldSetResult",
    "EmptyDraftError",
    "FinalizeRevisionResult",
    "GoldSetNotFoundError",
    "NoDraftToFinalizeError",
    "append_entry_to_revision",
    "create_gold_set",
    "finalize_revision",
    "get_gold_set",
    "list_gold_sets",
]
