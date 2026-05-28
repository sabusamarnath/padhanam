"""create fired_triggers (D147)

Revision ID: 0025_fired_triggers
Revises: 0024_message_cell_payload
Create Date: 2026-05-28

D147's race-safe idempotency substrate for platform-initiated
broadcasts. One row per `(tenant_id, user_id, trigger_type,
idempotency_key)` tuple per the UNIQUE constraint; the HTTP trigger
endpoint use case (FireTrigger) consults the table via INSERT with
ON CONFLICT DO NOTHING before BROADCAST_INITIATED audit emission.

CHECK constraint on ``trigger_type`` pins to the five Phase 2-A
values from ``BroadcastTriggerType`` (DAILY_SCHEDULED,
THRESHOLD_CROSSED, CALENDAR_EVENT, EMAIL_RECEIVED, MANUAL). The
``idempotency_key`` column is nullable per D147 — MANUAL triggers
generally carry no idempotency key, and Postgres UNIQUE constraints
accept multiple null values per construction.

Every table carries ``tenant_id`` per D12. The revision string stays
under the 32-char alembic ceiling per the captures-documented
migration name-length convention (``0025_fired_triggers`` is 19
chars). Index ``ix_fired_triggers_tenant_user_type`` supports
diagnostic lookups for the last firing per user per trigger type.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0025_fired_triggers"
down_revision: Union[str, None] = "0024_message_cell_payload"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TRIGGER_TYPES = (
    "daily_scheduled",
    "threshold_crossed",
    "calendar_event",
    "email_received",
    "manual",
)


def upgrade() -> None:
    op.create_table(
        "fired_triggers",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column(
            "fired_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            "trigger_type",
            "idempotency_key",
            name="ux_fired_triggers_tenant_user_type_key",
        ),
    )
    op.create_check_constraint(
        "fired_triggers_user_id_nonempty_check",
        "fired_triggers",
        "user_id <> ''",
    )
    op.create_check_constraint(
        "fired_triggers_trigger_type_check",
        "fired_triggers",
        "trigger_type IN ("
        + ", ".join(f"'{v}'" for v in _TRIGGER_TYPES)
        + ")",
    )
    op.create_index(
        "ix_fired_triggers_tenant_user_type",
        "fired_triggers",
        ["tenant_id", "user_id", "trigger_type"],
    )


def downgrade() -> None:
    op.drop_table("fired_triggers")
