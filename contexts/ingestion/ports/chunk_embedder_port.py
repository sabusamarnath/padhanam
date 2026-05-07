"""ChunkEmbedderPort — the embedder-as-port shape (D62 / D65).

The ChunkEmbedder serves two access patterns: per-batch corpus
embedding for the ingestion worker (``embed`` over a Sequence of
Chunks) and single-string query embedding for the retrieval
adapter (``embed_query`` over a query string). Both methods take an
``EmbeddingTask`` so the adapter applies the model's task-specific
prefix (``search_document:`` for DOCUMENT, ``search_query:`` for
QUERY against nomic-embed-text v1.5) per D65 — the prefix logic
lives in the adapter; the task hint is the port-level commitment.

The two-method shape rather than one widened method follows D56's
interface-segregation posture established at S17b. Each method
serves its own access pattern: ``embed`` returns Sequence[Embedding]
keyed by chunk_id (the worker's idempotency contract); ``embed_query``
returns a Sequence[float] (the retrieval adapter does not need
chunk_id provenance because the query is not a stored chunk).
Collapsing to a single method that takes either a Sequence[Chunk]
or a string would force the worker to handle the query return
shape and the retrieval adapter to handle chunk-id provenance —
exactly the kind of paper genericity D56 rejected.

Each call carries a ``TenantContext`` so the adapter can attribute
the embedding span at the trace level per D41 / D49 / D50. Adapters
emit OTel spans with the ``tenant.*`` attributes the inference
adapter established at S15.

The port shape is the architectural commitment that lets future
embedding-model swaps land as adapter additions rather than
refactors of the worker. A second adapter (e.g. for a hosted
provider rather than Ollama-via-LiteLLM) implements the same
signatures with no caller changes.

Errors: adapters raise ``EmbedderError`` for retryable infra
failures (gateway down, connection refused, rate limit) and
``EmbedderConfigurationError`` for non-retryable ones (auth, bad
model, bad request). Both are translated by the ``embed_source``
worker use case into the ``embedding_failed`` source state; the
retrieval adapter surfaces them to the caller as-is so the agent
runtime can decide whether to fall back to graph-only retrieval
or to surface a service-degradation signal.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.embedding import Embedding
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from shared_kernel import TenantContext


class EmbedderError(Exception):
    """Retryable infrastructure failure during embedding (gateway
    unavailable, connection refused, rate limit). The worker writes
    ``embedding_failed`` and the operator can retry by manually
    transitioning back to ``parsed``."""


class EmbedderConfigurationError(Exception):
    """Non-retryable configuration failure (auth, bad model, bad
    request). Same handling as ``EmbedderError`` at S20 — separated
    here so future retry policy can branch on the distinction."""


class ChunkEmbedderPort(Protocol):
    async def embed(
        self,
        chunks: Sequence[Chunk],
        tenant_context: TenantContext,
        task: EmbeddingTask,
    ) -> Sequence[Embedding]:
        """Return one Embedding per input Chunk in input order.

        ``task`` selects the model-specific input prefix per D65:
        ``DOCUMENT`` for ingestion-time corpus embedding,
        ``QUERY`` for retrieval-time corpus embedding (rare; the
        worker passes DOCUMENT). Adapters ignore the task if the
        embedding model does not require per-task prefixes.

        Raises ``EmbedderError`` for retryable infra failures and
        ``EmbedderConfigurationError`` for non-retryable ones.
        """
        ...

    async def embed_query(
        self,
        query: str,
        tenant_context: TenantContext,
        task: EmbeddingTask,
    ) -> Sequence[float]:
        """Return the embedding vector for the query string.

        The retrieval adapter at S22 calls this with
        ``task=EmbeddingTask.QUERY`` so the nomic-embed-text v1.5
        ``search_query:`` prefix lands. Returns a single vector
        (Sequence[float]) rather than an Embedding record because
        the query is not a stored chunk and has no chunk_id
        provenance.

        Raises ``EmbedderError`` and ``EmbedderConfigurationError``
        symmetrically with ``embed``.
        """
        ...
