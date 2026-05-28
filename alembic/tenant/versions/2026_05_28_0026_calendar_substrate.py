"""calendar substrate: connections + meetings tables with pgvector embedding

Revision ID: 0026_calendar_substrate
Revises: 0025_fired_triggers
Create Date: 2026-05-28

The S55a calendar data substrate per D148. Two per-tenant tables:

  1. ``connections`` — the tenant's calendar provider connection
     (identity: provider plus the opaque provider references) plus its
     per-connection ``sync_token`` state, UNIQUE on
     (tenant_id, provider, provider_config_key).

  2. ``meetings`` — the event-id-keyed mutable search cache, UNIQUE on
     (tenant_id, google_event_id). Structural columns stay plaintext for
     querying; content (title/description/location/attendees/organizer)
     is P3 envelope-encrypted into the five ``enc_*`` columns (D21). The
     ``embedding vector(768)`` column is added in raw SQL with an HNSW
     cosine index, mirroring ingestion's ``chunks`` table (SQLAlchemy
     Core needs the pgvector binding to know the type).

Per-tenant only per D32; the control plane has no calendar tables. The
pgvector extension is created idempotently (0006 already enables it on
ingestion-bearing tenants; the IF NOT EXISTS keeps 0026 self-contained).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0026_calendar_substrate"
down_revision: Union[str, None] = "0025_fired_triggers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MEETING_STATUSES = ("confirmed", "tentative", "cancelled")


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_config_key", sa.Text(), nullable=False),
        sa.Column("provider_connection_ref", sa.Text(), nullable=False),
        sa.Column("sync_token", sa.Text(), nullable=True),
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
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "provider_config_key",
            name="ux_connections_tenant_provider_config",
        ),
    )

    op.create_table(
        "meetings",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("google_event_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("start_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("end_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("start_raw", sa.Text(), nullable=True),
        sa.Column("end_raw", sa.Text(), nullable=True),
        sa.Column(
            "source_updated_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("recurring_event_id", sa.Text(), nullable=True),
        sa.Column("html_link", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("enc_wrapped_dek", sa.LargeBinary(), nullable=True),
        sa.Column("enc_dek_wrap_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("enc_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("enc_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("enc_key_version", sa.Integer(), nullable=True),
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
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_id", "google_event_id", name="ux_meetings_tenant_event"
        ),
    )
    op.create_check_constraint(
        "meetings_status_check",
        "meetings",
        "status IN ("
        + ", ".join(f"'{v}'" for v in _MEETING_STATUSES)
        + ")",
    )
    op.create_index(
        "ix_meetings_tenant_start", "meetings", ["tenant_id", "start_at"]
    )

    # pgvector embedding column + HNSW cosine index, mirroring chunks
    # (0006). Raw SQL because Core needs the pgvector binding for the type.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE meetings ADD COLUMN embedding vector(768)")
    op.execute(
        "CREATE INDEX meetings_embedding_hnsw_idx "
        "ON meetings USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS meetings_embedding_hnsw_idx")
    op.drop_index("ix_meetings_tenant_start", table_name="meetings")
    op.drop_constraint("meetings_status_check", "meetings", type_="check")
    op.drop_table("meetings")
    op.drop_table("connections")
    # Leave the vector extension in place; other schemas (chunks) use it.
