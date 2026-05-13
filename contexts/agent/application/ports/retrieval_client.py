"""AgentRetrievalClient Protocol port + RetrievedChunk DTO + RetrievalResult envelope (D88, D96).

The agent runtime's retrieval surface is consumer-shaped per D88: the
agent context defines what it needs from retrieval (a unified
``retrieve`` call taking the role's effective retrieval constraints
and returning chunks plus citation candidates), and the wiring
adapter at ``apps/cli/_cross_context.py`` translates against the
ingestion context's split ``search_vector`` / ``traverse_graph``
methods per D5 / D65's explicit decision that hybrid composition is
an agent-layer concern.

This pattern mirrors ``MethodologyLookup`` and ``RoleLookup`` from
D79 and S26a-2: the agent context stays independent of the ingestion
context's domain shape; the api-facade-via-callable pattern from D17
keeps cross-context coupling at the wiring layer.

Phase 1 (S27b) calls AgentRetrievalClient as the agent runtime's only
tool callable per D88's retrieval-as-only-callable framing; S28b's
tool registry generalises to multiple tools without changing the
retrieval port's shape.

D96 / S32 grows the return shape from ``tuple[RetrievedChunk, ...]``
to a ``RetrievalResult`` envelope carrying both ``chunks`` (the
LLM-facing projection) and ``citation_candidates`` (the citation
surface). The same adapter produces both from the same ingestion-side
``ChunkResult`` and ``EntityResult`` in a single pass; downstream
consumers route ``chunks`` to the LLM message stream and
``citation_candidates`` to ``ToolCallCompleted`` and the
``RunHistoryWriter``.

The port's structural type allows any callable matching the keyword-
argument shape; the apps/cli adapter at S27b is one implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Protocol
from uuid import UUID

from contexts.agent.domain.citation_candidates import CitationCandidate
from shared_kernel import TenantContext


@dataclass(frozen=True)
class RetrievedChunk:
    """A single chunk surfaced by the agent retrieval client (D88).

    Consumer-shaped DTO independent of the ingestion context's
    ``ChunkResult``. The producer-side aggregate carries embedder-
    specific metadata (model, vector dimensionality, ingest timestamp)
    the agent runtime does not consume; the adapter at
    ``apps/cli/_cross_context.py`` projects to this narrower shape at
    retrieval time.

    ``score`` is a float in ``[0, 1]`` for vector-retrieval similarity;
    graph-retrieval results map to a score derived from hop distance
    per the adapter's strategy translation.
    """

    text: str
    source_id: UUID
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    """Envelope returned by the agent retrieval client (D96).

    Carries both the LLM-facing ``chunks`` projection (the formatted-
    text source for ``_format_chunks_as_tool_result``) and the
    citation surface (``citation_candidates``) that ``ToolCallCompleted``
    rides on. The wiring adapter produces both in a single pass from
    the same ingestion-side ``ChunkResult`` / ``EntityResult``;
    downstream the executor reads ``chunks`` for LLM formatting and
    ``citation_candidates`` for event population.

    Both fields default to empty tuples so callers can construct a
    no-results envelope without knowing the citation surface; the
    LLM-facing formatter handles the empty case via the
    ``"(no chunks matched the query)"`` marker.
    """

    chunks: tuple[RetrievedChunk, ...] = ()
    citation_candidates: tuple[CitationCandidate, ...] = ()


class AgentRetrievalClient(Protocol):
    """Callable port for the agent runtime's retrieval surface (D88, D96).

    The Protocol is structurally typed: any callable accepting the
    named keyword arguments and returning a ``RetrievalResult``
    satisfies it. The apps/cli adapter at S27b implements this by
    composing the ingestion context's ``search_vector`` and
    ``traverse_graph`` methods per the role's
    ``retrieval_strategy`` selection.

    Strategy translation lives at the adapter, not in the agent
    context: the wiring layer reads ``retrieval_strategy`` (an opaque
    ``Mapping[str, Any]`` from the role aggregate) and dispatches to
    one or both ingestion methods accordingly. Phase 1 strategies are
    named at the data-retrieval design session's three-strategy
    starter catalogue per D66.

    Lookup failure (an ingestion-side error) propagates as the
    underlying exception type; the consumer's caller renders.
    """

    async def __call__(
        self,
        *,
        query: str,
        tenant_context: TenantContext,
        retrieval_strategy: Mapping[str, Any],
        filter_tree: Mapping[str, Any],
        top_k: int,
        min_score: Decimal,
    ) -> RetrievalResult: ...
