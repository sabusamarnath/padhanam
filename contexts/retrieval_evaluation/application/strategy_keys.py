"""Canonical retrieval-strategy identifiers and adapter-dispatch projection (D110 commitment 6).

The runner stores per-result and per-aggregate retrieval-strategy
identifiers as canonical strings (``vector_only``, ``graph_only`` at
S40 close); the agent-level ``AgentRetrievalClientAdapter`` at
``apps/cli/_cross_context.py`` dispatches on a free-form
``Mapping[str, Any]`` keyed by ``primary`` (verified at S40 pre-write
reconciliation Finding 2). This module is the small projection
surface between the two vocabularies.

The projection rule lives at the runner's call site rather than at
the adapter per the operator's Finding 2 disposition: the adapter is
unchanged, the runner consumes it.

``parallel_rrf`` is D66-catalogued but unimplemented at the adapter;
deferred to a Phase 2 fusion-implementation session per
``charter/deferred-decisions.md``. It is therefore not in
``EXECUTING_STRATEGIES`` at S40 close.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from typing import Any, Mapping

VECTOR_ONLY: str = "vector_only"
GRAPH_ONLY: str = "graph_only"

# D110 commitment 6: every D66-registered strategy with an executing
# branch in AgentRetrievalClientAdapter at S40 close.
EXECUTING_STRATEGIES: tuple[str, ...] = (VECTOR_ONLY, GRAPH_ONLY)

_DISPATCH_TABLE: dict[str, Mapping[str, Any]] = {
    VECTOR_ONLY: {"primary": "vector"},
    GRAPH_ONLY: {"primary": "graph"},
}


def to_adapter_dispatch(strategy: str) -> Mapping[str, Any]:
    """Translate canonical identifier to the adapter's dispatch mapping.

    Raises ``ValueError`` on unknown or non-executing strategies; this
    is a defence-in-depth check above the AgentRetrievalClientAdapter's
    own unknown-strategy fall-through (which returns an empty
    RetrievalResult and would silently produce zero metrics).
    """
    try:
        return dict(_DISPATCH_TABLE[strategy])
    except KeyError as exc:
        raise ValueError(
            f"unknown or non-executing retrieval strategy {strategy!r}; "
            f"executing strategies at S40: {list(EXECUTING_STRATEGIES)}"
        ) from exc
