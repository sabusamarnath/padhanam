"""email substrate: email_connections + emails + email_chunks (pgvector)

Revision ID: 0027_email_substrate
Revises: 0026_calendar_substrate
Create Date: 2026-06-03

The S56a email data substrate per D151. Three per-tenant tables, prefixed
``email_`` so they do not collide with calendar's ``connections``/
``meetings`` on the same per-tenant database:

  1. ``email_connections`` — the Gmail connection (identity: provider plus
     the opaque provider references) plus the dormant ``history_id``
     anchor (from getProfile; no incremental built this phase), UNIQUE on
     (tenant_id, provider, provider_config_key).

  2. ``emails`` — the message-id-keyed cache, UNIQUE on
     (tenant_id, message_id). Structural columns plaintext for querying;
     content (subject/body/addresses/snippet) P3 envelope-encrypted into
     the five ``enc_*`` columns (D21). Soft-delete via ``deleted_at``
     (set-diff tombstone).

  3. ``email_chunks`` — the email-local body-chunk store; encrypted chunk
     text plus a per-chunk ``embedding vector(768)`` (raw SQL + HNSW cosine
     index, mirroring calendar/ingestion).

Per-tenant only per D32. pgvector created idempotently.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0027_email_substrate"
down_revision: Union[str, None] = "0026_calendar_substrate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_connections",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_config_key", sa.Text(), nullable=False),
        sa.Column("provider_connection_ref", sa.Text(), nullable=False),
        sa.Column("history_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tenant_id", "provider", "provider_config_key",
            name="ux_email_connections_tenant_provider_config",
        ),
    )

    op.create_table(
        "emails",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=True),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("labels", pg.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("history_id", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("enc_wrapped_dek", sa.LargeBinary(), nullable=True),
        sa.Column("enc_dek_wrap_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("enc_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("enc_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("enc_key_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "message_id", name="ux_emails_tenant_message"),
    )
    op.create_index("ix_emails_tenant_received", "emails", ["tenant_id", "received_at"])

    op.create_table(
        "email_chunks",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("email_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("enc_wrapped_dek", sa.LargeBinary(), nullable=False),
        sa.Column("enc_dek_wrap_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("enc_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("enc_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("enc_key_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tenant_id", "message_id", "chunk_index", name="ux_email_chunks_tenant_message_index"
        ),
    )
    op.create_index("ix_email_chunks_tenant_message", "email_chunks", ["tenant_id", "message_id"])

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE email_chunks ADD COLUMN embedding vector(768)")
    op.execute(
        "CREATE INDEX email_chunks_embedding_hnsw_idx "
        "ON email_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS email_chunks_embedding_hnsw_idx")
    op.drop_index("ix_email_chunks_tenant_message", table_name="email_chunks")
    op.drop_table("email_chunks")
    op.drop_index("ix_emails_tenant_received", table_name="emails")
    op.drop_table("emails")
    op.drop_table("email_connections")
    # Leave the vector extension; other schemas use it.
