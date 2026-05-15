"""Consumer-defined retrieval-runner port (D110 commitment 5, S40).

The runner orchestration use case needs a uniform-shape retrieval
surface that takes a query, a strategy dispatch mapping, and a
top_k limit, and returns a ranked list of chunk IDs plus the
wall-clock latency of the underlying retrieval call.

Per S40 pre-write reconciliation Finding 3 the runner invokes via
the agent-level ``AgentRetrievalClient`` adapter callable (not via
the agent loop, and not by bypassing the adapter to call
ingestion-level methods directly). The wiring adapter at
``apps/cli/_cross_context.py`` translates between this consumer-
defined port and ``AgentRetrievalClient``: it (i) projects each
strategy's canonical identifier to the adapter's dispatch mapping
via ``application/strategy_keys.py``, (ii) supplies evaluation-
appropriate defaults for ``min_score`` (zero — let the runner see
every result and compute metrics) and ``filter_tree`` (empty), and
(iii) extracts ranked chunk IDs from ``RetrievalResult``'s citation
candidates (the source of truth for chunk-level provenance per D96).

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg, no
cross-context substrate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from uuid import UUID

from shared_kernel.tenant_context import TenantContext


@dataclass(frozen=True)
class RankedChunks:
    """Uniform retrieval-result shape across strategies (D110 commitment 5).

    ``chunk_ids`` carries the strategy's ranked output in retrieval
    order (rank-1 first); ``latency_ms`` captures wall-clock from
    the runner's invocation-start to the result-return per D110
    commitment 3.
    """

    chunk_ids: tuple[UUID, ...]
    latency_ms: int


class RetrievalRunnerPort(Protocol):
    """Consumer-defined retrieval-runner port (D110 commitment 5).

    The runner orchestrator invokes this callable once per
    (gold-set-entry × executing strategy) pairing.
    """

    async def __call__(
        self,
        *,
        query: str,
        tenant_context: TenantContext,
        strategy_dispatch: Mapping[str, Any],
        top_k: int,
    ) -> RankedChunks:
        ...
