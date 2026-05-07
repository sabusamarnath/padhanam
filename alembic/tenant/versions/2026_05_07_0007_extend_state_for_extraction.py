"""extend sources_state_check for extraction stage; add extraction_error_text

Revision ID: 0007_extend_state_for_extraction
Revises: 0006_add_chunk_embedding
Create Date: 2026-05-07

The S21 extraction stage lands its schema surface here per D64. Two
changes:

  1. Extend the ``sources_state_check`` CHECK constraint to admit
     the three new SourceState values (``extracting``, ``indexed``,
     ``extraction_failed``) the extraction worker stage transitions
     through per D64.

  2. Add the ``extraction_error_text`` text column on ``sources``
     (nullable, populated when state = extraction_failed) so the
     operator can see why extraction failed without trawling logs —
     mirrors the ``parsing_error_text`` (S19) and
     ``embedding_error_text`` (S20) shapes.

Per-tenant-only per D32. The graph store landed at S21 is the
shared Neo4j instance per D63; no Postgres-side graph-storage
changes land here.

Adapter consumer at S21:
``contexts/ingestion/adapters/outbound/extraction/litellm_extractor.py``
plus ``contexts/ingestion/adapters/outbound/neo4j/graph_repository.py``.
Worker consumer:
``contexts/ingestion/application/extract_source.py`` invoked by
``apps/cli/_ingest.py``'s extended worker loop.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_extend_state_for_extraction"
down_revision: Union[str, None] = "0006_add_chunk_embedding"
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
    "extracting",
    "indexed",
    "extraction_failed",
)


def upgrade() -> None:
    # 1. Extend the sources_state_check CHECK constraint to admit
    #    the three new SourceState values for the extraction stage.
    #    Drop-and-recreate is the migration-friendly shape per the
    #    same reasoning recorded in revision 0006.
    op.drop_constraint("sources_state_check", "sources", type_="check")
    op.create_check_constraint(
        "sources_state_check",
        "sources",
        "state IN ("
        + ", ".join(f"'{v}'" for v in _EXTENDED_STATE_VALUES)
        + ")",
    )

    # 2. Add extraction_error_text on sources, mirroring the S19
    #    parsing_error_text and S20 embedding_error_text shapes.
    op.add_column(
        "sources",
        sa.Column("extraction_error_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sources", "extraction_error_text")
    op.drop_constraint("sources_state_check", "sources", type_="check")
    op.create_check_constraint(
        "sources_state_check",
        "sources",
        "state IN ('received', 'parsing', 'parsed', 'failed', "
        "'embedding', 'embedded', 'embedding_failed')",
    )
