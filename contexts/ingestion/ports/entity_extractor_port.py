"""EntityExtractorPort — the extractor-as-port shape (D64).

The EntityExtractor maps a sequence of Chunks to an
``ExtractionResult`` carrying the entities and relationships the
extractor surfaces from the chunks' content. Per-batch shape so
multi-chunk extraction runs as a single port call; the adapter
chooses between per-chunk model calls (preserving chunk-level
provenance), batched calls (one model invocation across the whole
sequence), or a hybrid based on prompt-context-window cost.

Each call carries a ``TenantContext`` so the adapter can attribute
the extraction span at the trace level per D41 / D49 / D50. The
returned Entities and Relationships carry ``tenant_id`` matching
the ``TenantContext.tenant_id``, and ``source_chunk_ids`` /
``source_chunk_id`` populated with the chunks the extraction
surfaced from — provenance the GraphRepository preserves on the
node/edge properties.

The port shape commits the structural seam at S21; the LiteLLM
adapter is the first implementation but specialised extraction
models (GLiNER, REBEL, smaller fine-tuned LMs) implement the same
``extract`` signature with no caller changes.

Errors: adapters raise ``ExtractorError`` for retryable infra
failures (gateway down, connection refused, rate limit) and
``ExtractorConfigurationError`` for non-retryable ones (auth, bad
model, malformed schema response, unparseable JSON). Both are
translated by the ``extract_source`` worker use case into the
``extraction_failed`` source state with ``extraction_error_text``
populated; the operator's retry surface is manual transition back
to ``embedded``.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.extraction_result import ExtractionResult
from shared_kernel import TenantContext


class ExtractorError(Exception):
    """Retryable infrastructure failure during extraction (gateway
    unavailable, connection refused, rate limit). The worker writes
    ``extraction_failed`` and the operator can retry by manually
    transitioning back to ``embedded``."""


class ExtractorConfigurationError(Exception):
    """Non-retryable failure (auth, bad model, malformed JSON
    response). Same handling as ``ExtractorError`` at S21 —
    separated here so future retry policy can branch on the
    distinction."""


class EntityExtractorPort(Protocol):
    async def extract(
        self,
        chunks: Sequence[Chunk],
        tenant_context: TenantContext,
    ) -> ExtractionResult:
        """Return the ExtractionResult carrying entities and
        relationships surfaced from the given chunks. Empty input
        returns an empty result; the adapter does not raise on
        empty input.

        Raises ``ExtractorError`` for retryable infra failures and
        ``ExtractorConfigurationError`` for non-retryable ones.
        """
        ...
