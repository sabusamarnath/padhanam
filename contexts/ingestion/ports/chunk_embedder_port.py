"""ChunkEmbedderPort — the embedder-as-port shape (D62).

The ChunkEmbedder maps a sequence of Chunks to a sequence of
Embeddings. Per-batch shape because the LiteLLM ``/v1/embeddings``
API natively accepts a list of inputs and returns a list of
vectors in the same order, and round-tripping each chunk
individually multiplies the network cost for the same work. The
port preserves chunk identity by returning ``Embedding`` value
objects each carrying the source ``chunk_id``; the caller does not
need to assume positional alignment.

Each call carries a ``TenantContext`` so the adapter can attribute
the embedding span at the trace level per D41 / D49 / D50. Adapters
emit OTel spans with the ``tenant.*`` attributes the inference
adapter established at S15.

The port shape is the architectural commitment that lets future
embedding-model swaps land as adapter additions rather than
refactors of the worker. A second adapter (e.g. for a hosted
provider rather than Ollama-via-LiteLLM) implements the same
``embed`` signature with no caller changes.

Errors: adapters raise ``EmbedderError`` for retryable infra
failures (gateway down, connection refused, rate limit) and
``EmbedderConfigurationError`` for non-retryable ones (auth, bad
model, bad request). Both are translated by the ``embed_source``
worker use case into the ``embedding_failed`` source state with
``embedding_error_text`` populated; the operator's retry surface is
manual transition back to ``parsed``.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.embedding import Embedding
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
    ) -> Sequence[Embedding]:
        """Return one Embedding per input Chunk in input order.

        Raises ``EmbedderError`` for retryable infra failures and
        ``EmbedderConfigurationError`` for non-retryable ones.
        """
        ...
