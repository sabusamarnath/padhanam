"""tasks substrate: task_connections + tasks

Revision ID: 0030_tasks_substrate
Revises: 0029_commitment_outcome
Create Date: 2026-06-08

The S65 task-ingestion data substrate per D167. Two per-tenant tables, prefixed
``task_`` so they do not collide with calendar's ``connections``/``meetings`` or
email's ``email_*`` on the same per-tenant database:

  1. ``task_connections`` — the Google Tasks connection (identity: provider plus
     the opaque provider references), UNIQUE on (tenant_id, provider,
     provider_config_key). No sync-token/history-id anchor — Google Tasks
     re-pulls fully each refresh.

  2. ``tasks`` — the google-task-id-keyed mutable cache (D155), UNIQUE on
     (tenant_id, google_task_id). Structural columns plaintext for querying;
     content (title + notes) P3 envelope-encrypted into the five ``enc_*``
     columns (D21). Soft-delete via ``deleted_at`` (set-diff tombstone). No
     embedding column — tasks need no semantic search at P17.

Per-tenant only per D32.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0030_tasks_substrate"
down_revision: Union[str, None] = "0029_commitment_outcome"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_connections",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_config_key", sa.Text(), nullable=False),
        sa.Column("provider_connection_ref", sa.Text(), nullable=False),
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

    op.create_table(
        "tasks",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("google_task_id", sa.Text(), nullable=False),
        sa.Column("tasklist_id", sa.Text(), nullable=False),
        sa.Column("tasklist_title", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("due_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("parent", sa.Text(), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_id", "google_task_id", name="ux_tasks_tenant_google_task"
        ),
    )
    op.create_index("ix_tasks_tenant_due", "tasks", ["tenant_id", "due_at"])


def downgrade() -> None:
    op.drop_index("ix_tasks_tenant_due", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("task_connections")
