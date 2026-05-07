"""Source pipeline state (D60 / D61 / D62 / D64).

The per-stage status field that drives D60's worker reentrancy
seam. S19 covered the parsing stage; S20 extended with the
embedding stage per D62; S21 extends with the extraction stage
per D64; the str-enum shape stays stable as new values land.

A source row's lifecycle at S21:

    received  -- the upload-side use case writes this on register;
                  workers claim rows in this state for parsing.
        |
        v
    parsing   -- the worker transitions to this on claim, before
                  invoking the parser. Surfaces "in-flight" to
                  observers and disambiguates from received-but-
                  not-yet-claimed.
        |
        +--> parsed  -- worker transitions on parser success after
        |          |   writing chunks atomically. The embedding
        |          |   stage claims rows from this state.
        |          v
        |     embedding  -- the embedding worker transitions on
        |          |       claim, before invoking the embedder.
        |          |
        |          +--> embedded  -- worker transitions on embedder
        |          |              success after writing per-chunk
        |          |              embedding vectors via UPSERT on
        |          |              chunks.id (idempotent re-embed
        |          |              per D62).
        |          |
        |          +--> embedding_failed  -- worker transitions on
        |          |                       embedder exception;
        |          |                       embedding_error_text on
        |          |                       the row carries the
        |          |                       reason. Operator surface
        |          |                       for retry at S20 is
        |          |                       manual transition back
        |          |                       to parsed.
        |          |
        |          +--> embedded  (continued)
        |                  |
        |                  v
        |              extracting  -- the extraction worker
        |                  |       transitions on claim, before
        |                  |       invoking the EntityExtractor.
        |                  |
        |                  +--> indexed  -- worker transitions on
        |                  |              extraction success after
        |                  |              writing entities and
        |                  |              relationships into Neo4j
        |                  |              via Cypher MERGE per D64.
        |                  |              `indexed` is the terminal-
        |                  |              success state for P6 close.
        |                  |
        |                  +--> extraction_failed  -- worker
        |                                          transitions on
        |                                          extractor or
        |                                          graph-repository
        |                                          exception;
        |                                          extraction_error_text
        |                                          carries the reason.
        |
        +--> failed  -- worker transitions on parser exception;
                        parsing_error_text on the row carries the
                        reason. Operator manually flips back to
                        received for retry at S19; richer retry
                        semantics defer to production-deployment
                        context.

Domain code is framework-free per D16 — stdlib StrEnum, no
Pydantic, no SQLAlchemy.
"""

from __future__ import annotations

from enum import StrEnum


class SourceState(StrEnum):
    RECEIVED = "received"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"
    # S20 / D62: embedding-stage values.
    EMBEDDING = "embedding"
    EMBEDDED = "embedded"
    EMBEDDING_FAILED = "embedding_failed"
    # S21 / D64: extraction-stage values. ``indexed`` is the
    # terminal-success state for P6 close.
    EXTRACTING = "extracting"
    INDEXED = "indexed"
    EXTRACTION_FAILED = "extraction_failed"
