"""SQLAlchemy Core table definitions for the email per-tenant tables (D151).

Three tables — ``email_connections`` (the tenant's Gmail connection plus
the dormant ``history_id`` anchor), ``emails`` (the message-id-keyed
cache), and ``email_chunks`` (the email-local body-chunk store). Named
with the ``email_`` prefix so they do not collide with calendar's
``connections``/``meetings`` on the same per-tenant database. Migration
``0027_email_substrate`` ships these and must stay in lockstep.

Email content (subject/body/addresses/snippet) and chunk text are
field-level encrypted via P3 envelope encryption (D21) into the ``enc_*``
columns; structural columns stay plaintext for querying. The per-chunk
``embedding vector(768)`` column is added by the migration in raw SQL
(SQLAlchemy Core needs the pgvector binding), mirroring calendar/ingestion;
it is read/written through dedicated adapter paths, so it is absent here.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

metadata = sa.MetaData()


email_connections = sa.Table(
    "email_connections",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("provider", sa.Text, nullable=False),
    sa.Column("provider_config_key", sa.Text, nullable=False),
    sa.Column("provider_connection_ref", sa.Text, nullable=False),
    # Dormant mailbox incremental anchor (getProfile historyId, D151).
    sa.Column("history_id", sa.Text, nullable=True),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint(
        "tenant_id", "provider", "provider_config_key",
        name="ux_email_connections_tenant_provider_config",
    ),
)


emails = sa.Table(
    "emails",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("message_id", sa.Text, nullable=False),
    sa.Column("thread_id", sa.Text, nullable=True),
    sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("labels", pg.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("history_id", sa.Text, nullable=True),
    # Digest of subject+body; NULL when tombstoned.
    sa.Column("content_hash", sa.Text, nullable=True),
    # P3 envelope-encrypted content (subject/body/addresses/snippet JSON).
    sa.Column("enc_wrapped_dek", sa.LargeBinary, nullable=True),
    sa.Column("enc_dek_wrap_nonce", sa.LargeBinary, nullable=True),
    sa.Column("enc_ciphertext", sa.LargeBinary, nullable=True),
    sa.Column("enc_nonce", sa.LargeBinary, nullable=True),
    sa.Column("enc_key_version", sa.Integer, nullable=True),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.UniqueConstraint("tenant_id", "message_id", name="ux_emails_tenant_message"),
    sa.Index("ix_emails_tenant_received", "tenant_id", "received_at"),
)


email_chunks = sa.Table(
    "email_chunks",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("email_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("message_id", sa.Text, nullable=False),
    sa.Column("chunk_index", sa.Integer, nullable=False),
    # Encrypted chunk text (D21).
    sa.Column("enc_wrapped_dek", sa.LargeBinary, nullable=False),
    sa.Column("enc_dek_wrap_nonce", sa.LargeBinary, nullable=False),
    sa.Column("enc_ciphertext", sa.LargeBinary, nullable=False),
    sa.Column("enc_nonce", sa.LargeBinary, nullable=False),
    sa.Column("enc_key_version", sa.Integer, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint(
        "tenant_id", "message_id", "chunk_index", name="ux_email_chunks_tenant_message_index"
    ),
    sa.Index("ix_email_chunks_tenant_message", "tenant_id", "message_id"),
)


__all__ = ["email_chunks", "email_connections", "emails", "metadata"]
