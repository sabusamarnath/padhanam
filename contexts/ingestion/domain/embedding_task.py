"""EmbeddingTask — task-hint enum for the ChunkEmbedder port (D65).

The ``ChunkEmbedder.embed`` method takes a ``task`` parameter so
the adapter can apply model-specific prefixes (or any other
task-conditioned logic) without leaking the model's specifics into
the port surface or the call site. Two values at S22:

  - ``DOCUMENT``: ingestion-time corpus embedding. The S20 worker
    passes this for each chunk of a parsed source.
  - ``QUERY``: retrieval-time query embedding. The S22 vector
    adapter passes this when embedding a search query.

Per D65 the LiteLLM adapter applies the nomic-embed-text v1.5
prefixes (``search_document:`` for DOCUMENT, ``search_query:`` for
QUERY) based on this task. If the embedding model is later swapped
to one that does not require prefixes, the adapter ignores the task
without breaking callers.
"""

from __future__ import annotations

from enum import StrEnum


class EmbeddingTask(StrEnum):
    DOCUMENT = "document"
    QUERY = "query"
