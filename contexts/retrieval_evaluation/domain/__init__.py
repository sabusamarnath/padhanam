"""Retrieval evaluation domain layer (D109, D110).

Gold-set substrate (D109):

- ``GoldSet`` at ``gold_set.py`` — aggregate root with tenant identity,
  name uniqueness per tenant, and current_revision_id pointer to the
  most recent finalized revision.
- ``GoldSetRevision`` and ``GoldSetRevisionStatus`` at
  ``gold_set_revision.py`` — append-only revision with status
  lifecycle (draft → finalized) and hash-chain audit per D26.
- ``GoldSetEntry`` at ``gold_set_entry.py`` — one (query,
  ordered expected_chunk_ids) pair per gold-set revision.
- Hash-chain wrapper at ``hash_chain.py`` exposing
  ``compute_revision_hash``, ``revision_canonical_payload``, and
  re-exporting ``GENESIS_REVISION_HASH`` from
  ``padhanam.security.hash_chain``.

Runner substrate (D110, S40):

- ``EvaluationRun`` and ``EvaluationRunStatus`` at
  ``evaluation_run.py`` — aggregate root with the running/completed/
  failed status lifecycle.
- ``EvaluationResult`` and ``SUPPORTED_K_VALUES`` at
  ``evaluation_result.py`` — per-query-per-strategy result row.
- ``EvaluationAggregate`` at ``evaluation_aggregate.py`` — per-strategy
  summary row computed at run completion.
- ``metrics.py`` — recall@k, precision@k, MRR primitives plus
  aggregation helpers (mean, percentile).

All value objects enforce invariants in ``__post_init__`` so the
repository adapter cannot persist a row, and the reader adapter
cannot materialise a domain object, that fails the domain rules.
"""

from contexts.retrieval_evaluation.domain.evaluation_aggregate import (
    EvaluationAggregate,
)
from contexts.retrieval_evaluation.domain.evaluation_result import (
    SUPPORTED_K_VALUES,
    EvaluationResult,
)
from contexts.retrieval_evaluation.domain.evaluation_run import (
    EvaluationRun,
    EvaluationRunStatus,
)
from contexts.retrieval_evaluation.domain.gold_set import GoldSet
from contexts.retrieval_evaluation.domain.gold_set_entry import GoldSetEntry
from contexts.retrieval_evaluation.domain.gold_set_revision import (
    GoldSetRevision,
    GoldSetRevisionStatus,
)
from contexts.retrieval_evaluation.domain.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
    revision_canonical_payload,
)

__all__ = [
    "GENESIS_REVISION_HASH",
    "SUPPORTED_K_VALUES",
    "EvaluationAggregate",
    "EvaluationResult",
    "EvaluationRun",
    "EvaluationRunStatus",
    "GoldSet",
    "GoldSetEntry",
    "GoldSetRevision",
    "GoldSetRevisionStatus",
    "compute_revision_hash",
    "revision_canonical_payload",
]
