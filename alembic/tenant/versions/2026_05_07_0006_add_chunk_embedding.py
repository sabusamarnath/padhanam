"""add chunk embedding column, HNSW index, and embedding-stage state values

Revision ID: 0006_add_chunk_embedding
Revises: 0005_create_sources_and_chunks
Create Date: 2026-05-07

The S20 embedding stage lands its schema surface here per D62. Three
changes:

  1. Enable the pgvector extension on the tenant database. The
     pgvector Docker image makes the extension available; the
     extension itself still needs explicit CREATE per database.
     Idempotent (IF NOT EXISTS) so re-running the migration is a
     no-op.

  2. Add the ``embedding vector(768)`` column to ``chunks``. Nullable
     so a chunk row can exist before the embedding lands and so the
     embedded vs not-yet-embedded shape is observable on the row.
     Dimension matches ``nomic-embed-text:v1.5`` native output per
     D62.

  3. Add the HNSW index ``chunks_embedding_hnsw_idx`` over
     ``(embedding vector_cosine_ops)`` with pgvector defaults
     ``(m=16, ef_construction=64)`` per D62. Cosine matches the
     distance metric ``nomic-embed-text:v1.5`` recommends. At Phase 1
     corpus size (<100k rows) the defaults are appropriate per the
     pgvector README.

  4. Extend the ``sources_state_check`` CHECK constraint to admit the
     three new SourceState values (``embedding``, ``embedded``,
     ``embedding_failed``) the embedding worker stage transitions
     through per D62.

  5. Add the ``embedding_error_text`` text column on ``sources``
     (nullable, populated when state = embedding_failed) so the
     operator can see why embedding failed without trawling logs —
     mirrors the parsing_error_text shape from S19.

Per-tenant-only per D32. The pgvector extension is created on each
tenant's data plane; the control-plane database does not need it
(the registry has no embedding columns).

Adapter consumer at S20:
``contexts/ingestion/adapters/outbound/embedding/litellm_embedder.py``.
Worker consumer:
``contexts/ingestion/application/embed_source.py`` invoked by
``apps/cli/_ingest.py``'s extended worker loop.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_add_chunk_embedding"
down_revision: Union[str, None] = "0005_create_sources_and_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_EXTENDED_STATE_VALUES = (
    "received",
    "parsing",
    "parsed",
    "failed",
    "embedding",
    "embedded",
    "embedding_failed",
)


def upgrade() -> None:
    # 1. Enable the pgvector extension. Idempotent.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Add the embedding column. Raw SQL because SQLAlchemy core
    #    needs the pgvector Python binding to know about the Vector
    #    type at the migration layer; the migration runs against the
    #    DB directly and the type signature lands in the column DDL.
    op.execute("ALTER TABLE chunks ADD COLUMN embedding vector(768)")

    # 3. Add the HNSW index over cosine distance. pgvector defaults
    #    (m=16, ef_construction=64) are appropriate at Phase 1
    #    corpus sizes per the README's recommendation.
    op.execute(
        "CREATE INDEX chunks_embedding_hnsw_idx "
        "ON chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # 4. Extend the sources_state_check CHECK constraint to admit
    #    the three new SourceState values for the embedding stage.
    #    Drop-and-recreate is the migration-friendly shape per D49's
    #    text-plus-CHECK reasoning (over Postgres CREATE TYPE which
    #    has subtle ALTER TYPE ADD VALUE transaction restrictions).
    op.drop_constraint("sources_state_check", "sources", type_="check")
    op.create_check_constraint(
        "sources_state_check",
        "sources",
        "state IN ("
        + ", ".join(f"'{v}'" for v in _EXTENDED_STATE_VALUES)
        + ")",
    )

    # 5. Add embedding_error_text on sources, mirroring the S19
    #    parsing_error_text shape.
    op.add_column(
        "sources",
        sa.Column("embedding_error_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sources", "embedding_error_text")
    op.drop_constraint("sources_state_check", "sources", type_="check")
    op.create_check_constraint(
        "sources_state_check",
        "sources",
        "state IN ('received', 'parsing', 'parsed', 'failed')",
    )
    op.execute("DROP INDEX IF EXISTS chunks_embedding_hnsw_idx")
    op.execute("ALTER TABLE chunks DROP COLUMN embedding")
    # Leave the vector extension in place; other schemas may use it
    # and DROP EXTENSION cascades to vector-typed columns elsewhere.
