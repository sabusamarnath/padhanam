"""create messages (D129)

Revision ID: 0019_messaging_substrate
Revises: 0018_intake_id_columns
Create Date: 2026-05-22

Per-tenant substrate for the messaging context per D129. One table
on each tenant's dedicated Postgres data plane per D32:

- ``messages``: the Message aggregate root. CHECK constraints pin
  ``direction``, ``channel`` (the single Phase 2-A value WHATSAPP),
  and ``status``. ``intake_id`` is a nullable foreign key to
  ``intakes(id)`` ON DELETE RESTRICT — populated on inbound
  messages per D128, null on outbound. Messages are immutable —
  no update path.

Every table carries ``tenant_id`` and ``jurisdiction`` per D12.
CHECK-constraint naming follows the ``0017_intake_substrate``
pattern. The revision string stays under the 32-char alembic
ceiling per the captures-documented migration name-length
convention.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0019_messaging_substrate"
down_revision: Union[str, None] = "0018_intake_id_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DIRECTIONS = ("INBOUND", "OUTBOUND")
_CHANNELS = ("WHATSAPP",)
_STATUSES = ("QUEUED", "SENT", "DELIVERED", "FAILED", "RECEIVED")


def _in_clause(column: str, values: tuple[str, ...]) -> str:
    return column + " IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("from_address", sa.Text(), nullable=False),
        sa.Column("to_address", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("intake_id", pg.UUID(as_uuid=False), nullable=True),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["intake_id"],
            ["intakes.id"],
            name="fk_messages_intake_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_check_constraint(
        "messages_jurisdiction_nonempty_check",
        "messages",
        "jurisdiction <> ''",
    )
    op.create_check_constraint(
        "messages_body_nonempty_check", "messages", "body <> ''"
    )
    op.create_check_constraint(
        "messages_from_address_nonempty_check",
        "messages",
        "from_address <> ''",
    )
    op.create_check_constraint(
        "messages_to_address_nonempty_check",
        "messages",
        "to_address <> ''",
    )
    op.create_check_constraint(
        "messages_actor_id_nonempty_check", "messages", "actor_id <> ''"
    )
    op.create_check_constraint(
        "messages_direction_check",
        "messages",
        _in_clause("direction", _DIRECTIONS),
    )
    op.create_check_constraint(
        "messages_channel_check",
        "messages",
        _in_clause("channel", _CHANNELS),
    )
    op.create_check_constraint(
        "messages_status_check", "messages", _in_clause("status", _STATUSES)
    )
    op.create_index(
        "ix_messages_tenant_created_at",
        "messages",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_messages_tenant_direction_channel",
        "messages",
        ["tenant_id", "direction", "channel"],
    )


def downgrade() -> None:
    op.drop_table("messages")
