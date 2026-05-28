"""SQLAlchemy Core table definitions for the calendar per-tenant tables (D148).

Two tables — ``connections`` (the tenant's provider connection plus its
sync-token state) and ``meetings`` (the event-id-keyed mutable search
cache). Migration ``0026_calendar_substrate`` ships these on every
per-tenant database and must stay in lockstep with the definitions here.

Meeting content (title, description, location, attendees, organizer) is
field-level encrypted via P3 envelope encryption (D21) and stored in the
five ``enc_*`` columns; the structural columns (event id, status, times,
content hash) stay plaintext for querying. The ``embedding vector(768)``
column is added by the migration in raw SQL (SQLAlchemy Core needs the
pgvector binding to know the type), mirroring ingestion's ``chunks``
table; it is written and read through dedicated adapter paths, not the
Core insert, so it is intentionally absent from this MetaData.

SQLAlchemy 2.0 Core — no ORM — mirroring the portfolio precedent.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

metadata = sa.MetaData()


connections = sa.Table(
    "connections",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("provider", sa.Text, nullable=False),
    sa.Column("provider_config_key", sa.Text, nullable=False),
    sa.Column("provider_connection_ref", sa.Text, nullable=False),
    # Per-connection incremental-sync state. Cleared (NULL) on full
    # resync (the 410 path).
    sa.Column("sync_token", sa.Text, nullable=True),
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


meetings = sa.Table(
    "meetings",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("google_event_id", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("start_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("end_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("start_raw", sa.Text, nullable=True),
    sa.Column("end_raw", sa.Text, nullable=True),
    sa.Column("source_updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("recurring_event_id", sa.Text, nullable=True),
    sa.Column("html_link", sa.Text, nullable=True),
    # Digest of the synthesised content text; NULL when tombstoned.
    sa.Column("content_hash", sa.Text, nullable=True),
    # P3 envelope-encrypted content payload (title/description/location/
    # attendees/organizer serialized to JSON). All NULL when tombstoned.
    sa.Column("enc_wrapped_dek", sa.LargeBinary, nullable=True),
    sa.Column("enc_dek_wrap_nonce", sa.LargeBinary, nullable=True),
    sa.Column("enc_ciphertext", sa.LargeBinary, nullable=True),
    sa.Column("enc_nonce", sa.LargeBinary, nullable=True),
    sa.Column("enc_key_version", sa.Integer, nullable=True),
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
    sa.Index("ix_meetings_tenant_start", "tenant_id", "start_at"),
)


__all__ = ["connections", "meetings", "metadata"]
