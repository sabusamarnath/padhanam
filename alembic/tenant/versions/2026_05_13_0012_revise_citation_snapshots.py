"""revise citation snapshot columns per D96

Revision ID: 0012_revise_citation_snapshots
Revises: 0011_create_run_history
Create Date: 2026-05-13

Per D96, the citation snapshot columns revise to keep render shape
(Harvard, footnote, hover card, et al.) as a Phase 2 read-time
concern over structured input snapshots rather than baked-in
display text.

On ``run_chunk_citations``:
- Drop ``source_citation text NOT NULL`` (the pre-rendered display
  text from S31's tentative shape).
- Add ``source_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb`` (the
  structured snapshot of source-level metadata available at
  retrieval time; Phase 1 carries ``file_name`` and ``file_type``;
  richer ingestion enrichment fills more without schema change).

On ``run_entity_citations``:
- Drop ``entity_display_label text NOT NULL`` (display label
  synthesised at render time from ``entity_name`` plus
  ``entity_type``).
- Add ``source_chunk_ids text[] NOT NULL DEFAULT '{}'::text[]``
  (snapshot of the Neo4j entity's source_chunk_ids array preserving
  provenance back to per-tenant Postgres chunks per D96).

S31 reconciliation finding (re-verified at S32 session-open): the
citation tables are empty across both tenants at S32 session-open
so the migration is structural-only — no row-level backfill is
required for the column transitions.

Downgrade reverses both column changes: add the dropped columns
back with their original constraints; drop the new columns.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0012_revise_citation_snapshots"
down_revision: Union[str, None] = "0011_create_run_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- run_chunk_citations: source_citation text → source_snapshot jsonb ---
    op.drop_column("run_chunk_citations", "source_citation")
    op.add_column(
        "run_chunk_citations",
        sa.Column(
            "source_snapshot",
            pg.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # --- run_entity_citations: entity_display_label text → source_chunk_ids text[] ---
    op.drop_column("run_entity_citations", "entity_display_label")
    op.add_column(
        "run_entity_citations",
        sa.Column(
            "source_chunk_ids",
            pg.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )


def downgrade() -> None:
    op.drop_column("run_entity_citations", "source_chunk_ids")
    op.add_column(
        "run_entity_citations",
        sa.Column(
            "entity_display_label",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )

    op.drop_column("run_chunk_citations", "source_snapshot")
    op.add_column(
        "run_chunk_citations",
        sa.Column(
            "source_citation",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
