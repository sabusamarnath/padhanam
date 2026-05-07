"""create sources and chunks tables

Revision ID: 0005_create_sources_and_chunks
Revises: 0004_add_rubric_apps_trace_id
Create Date: 2026-05-07

The source-ingestion data model lands here per D60 / D61. Two
tables on the per-tenant track: ``sources`` (the upload primitive
plus pipeline-state column that drives D60's worker reentrancy
seam) and ``chunks`` (the parsed-content rows that pgvector
embeddings will reference at S20).

Per-tenant-only per D32. Storage on tenant data planes, never on
the control plane; the per-tenant topology for Neo4j defers to
the session that first writes to Neo4j per the
``deferred-decisions.md`` entry. The tenant-isolation contract
test at ``tests/contract/tenant_isolation/test_ingestion_isolation.py``
asserts the tables exist on tenant_a and tenant_b and not on the
control-plane DB.

The ``sources.state`` CHECK constraint pins the type-tag space to
the four S19 values (``received``, ``parsing``, ``parsed``,
``failed``); S20 and S21 extend the CHECK as their pipeline stages
land. The ``sources.file_type`` CHECK pins to the two parsers
shipping at S19 (``markdown``, ``text``) per D61; PDF, DOCX, HTML
are recorded in D61 as forward-affordance and extend the CHECK
when their parsers ship.

The UNIQUE(source_id, chunk_index) constraint on ``chunks`` is
the structural backstop for D60's worker idempotency contract:
re-running the parser against an already-parsed source produces an
integrity violation rather than duplicate rows. The worker's
parse-source use case treats this as the failure-mode signal that
either the row was already parsed (no-op) or that idempotency was
violated upstream.

Adapter consumer at S19:
``contexts/ingestion/adapters/outbound/postgres/source_repository.py``.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0005_create_sources_and_chunks"
down_revision: Union[str, None] = "0004_add_rubric_apps_trace_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SOURCE_STATE_VALUES = ("received", "parsing", "parsed", "failed")
_FILE_TYPE_VALUES = ("markdown", "text")


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("raw_content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'received'"),
        ),
        sa.Column("parsing_error_text", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "sources_tenant_id_nonempty_check",
        "sources",
        "tenant_id <> ''",
    )
    op.create_check_constraint(
        "sources_file_type_check",
        "sources",
        "file_type IN ("
        + ", ".join(f"'{v}'" for v in _FILE_TYPE_VALUES)
        + ")",
    )
    op.create_check_constraint(
        "sources_state_check",
        "sources",
        "state IN ("
        + ", ".join(f"'{v}'" for v in _SOURCE_STATE_VALUES)
        + ")",
    )
    op.create_index(
        "ix_sources_tenant_state",
        "sources",
        ["tenant_id", "state"],
    )

    op.create_table(
        "chunks",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "structural_metadata",
            pg.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "chunks_tenant_id_nonempty_check",
        "chunks",
        "tenant_id <> ''",
    )
    op.create_index(
        "ix_chunks_source_id",
        "chunks",
        ["source_id"],
    )
    op.create_unique_constraint(
        "chunks_source_chunk_index_unique",
        "chunks",
        ["source_id", "chunk_index"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "chunks_source_chunk_index_unique", "chunks", type_="unique"
    )
    op.drop_index("ix_chunks_source_id", table_name="chunks")
    op.drop_constraint(
        "chunks_tenant_id_nonempty_check", "chunks", type_="check"
    )
    op.drop_table("chunks")
    op.drop_index("ix_sources_tenant_state", table_name="sources")
    op.drop_constraint("sources_state_check", "sources", type_="check")
    op.drop_constraint("sources_file_type_check", "sources", type_="check")
    op.drop_constraint(
        "sources_tenant_id_nonempty_check", "sources", type_="check"
    )
    op.drop_table("sources")
