"""Retrieval evaluation application layer (D109 commitment 6, D110).

Gold-set authoring (D109):

- ``create_gold_set`` — aggregate root plus initial draft revision.
- ``append_entry_to_revision`` — append to current draft; opens a
  new draft lazily if the prior revision is finalized.
- ``finalize_revision`` — transitions draft to finalized; computes
  ``this_event_hash`` via the platform hash-chain primitive.
- ``list_gold_sets`` — paginated read with opaque cursor.
- ``get_gold_set`` — aggregate snapshot at the current finalized
  revision.

Runner orchestration (D110, S40):

- ``run_retrieval_evaluation`` — exercise every gold-set entry
  against every executing D66 strategy; persist per-query results
  and per-strategy aggregates; emit audit events at every write.
- ``get_evaluation_run`` — read run aggregate + per-query results +
  per-strategy aggregates.
- ``list_evaluation_runs`` — paginated read with opaque cursor.

Cursor codec at ``cursor.py`` mediates the HTTP boundary at S42 for
both read surfaces. Strategy-key projection at ``strategy_keys.py``
converts canonical identifiers (``vector_only``, ``graph_only``) to
the agent-level adapter's dispatch mapping per D110 commitment 6.
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
from contexts.retrieval_evaluation.application.get_evaluation_run import (
    get_evaluation_run,
)
from contexts.retrieval_evaluation.application.get_gold_set import get_gold_set
from contexts.retrieval_evaluation.application.list_evaluation_runs import (
    list_evaluation_runs,
)
from contexts.retrieval_evaluation.application.list_gold_sets import (
    list_gold_sets,
)
from contexts.retrieval_evaluation.application.run_retrieval_evaluation import (
    GoldSetMissingFinalizedRevisionError,
    RunRetrievalEvaluationResult,
    run_retrieval_evaluation,
)
from contexts.retrieval_evaluation.application.strategy_keys import (
    EXECUTING_STRATEGIES,
    GRAPH_ONLY,
    VECTOR_ONLY,
    to_adapter_dispatch,
)

__all__ = [
    "AppendEntryResult",
    "CreateGoldSetResult",
    "EXECUTING_STRATEGIES",
    "EmptyDraftError",
    "FinalizeRevisionResult",
    "GRAPH_ONLY",
    "GoldSetMissingFinalizedRevisionError",
    "GoldSetNotFoundError",
    "NoDraftToFinalizeError",
    "RunRetrievalEvaluationResult",
    "VECTOR_ONLY",
    "append_entry_to_revision",
    "create_gold_set",
    "finalize_revision",
    "get_evaluation_run",
    "get_gold_set",
    "list_evaluation_runs",
    "list_gold_sets",
    "run_retrieval_evaluation",
    "to_adapter_dispatch",
]
