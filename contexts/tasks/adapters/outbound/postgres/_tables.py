"""SQLAlchemy Core table definitions for the tasks per-tenant tables (D167).

Two tables, prefixed ``task_`` so they do not collide with calendar's
``connections``/``meetings`` or email's ``email_*`` on the same per-tenant
database (the email-prefix precedent):

  1. ``task_connections`` — the tenant's task provider connection (identity:
     provider plus the opaque provider references), UNIQUE on
     (tenant_id, provider, provider_config_key). No sync-token/history-id
     anchor — Google Tasks re-pulls fully each refresh (the simplest D155 model).

  2. ``tasks`` — the google-task-id-keyed mutable cache (D155), UNIQUE on
     (tenant_id, google_task_id). Structural columns (status, due, completed,
     tasklist, position) plaintext for querying; content (title + notes) P3
     envelope-encrypted into the five ``enc_*`` columns (D21). Soft-delete via
     ``deleted_at`` (set-diff tombstone). No embedding column — tasks need no
     semantic search at P17 (unlike calendar/email).

Migration ``0030_tasks_substrate`` ships these on every per-tenant database and
must stay in lockstep with these definitions. SQLAlchemy 2.0 Core, no ORM.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

metadata = sa.MetaData()


task_connections = sa.Table(
    "task_connections",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("provider", sa.Text, nullable=False),
    sa.Column("provider_config_key", sa.Text, nullable=False),
    sa.Column("provider_connection_ref", sa.Text, nullable=False),
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
        name="ux_task_connections_tenant_provider_config",
    ),
)


tasks = sa.Table(
    "tasks",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("google_task_id", sa.Text, nullable=False),
    sa.Column("tasklist_id", sa.Text, nullable=False),
    sa.Column("tasklist_title", sa.Text, nullable=True),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("due_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("parent", sa.Text, nullable=True),
    sa.Column("position", sa.Text, nullable=True),
    sa.Column("source_updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    # Digest of the synthesised content text; NULL when tombstoned.
    sa.Column("content_hash", sa.Text, nullable=True),
    # P3 envelope-encrypted content payload (title + notes). All NULL when
    # tombstoned.
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
    sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.UniqueConstraint(
        "tenant_id", "google_task_id", name="ux_tasks_tenant_google_task"
    ),
    sa.Index("ix_tasks_tenant_due", "tenant_id", "due_at"),
)


__all__ = ["metadata", "task_connections", "tasks"]
