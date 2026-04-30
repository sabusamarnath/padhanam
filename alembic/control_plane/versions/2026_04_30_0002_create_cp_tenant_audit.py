"""create control-plane tenant_audit

Revision ID: 0002_create_cp_tenant_audit
Revises: 0001_create_tenant_registry
Create Date: 2026-04-30

The control-plane audit table holds operator-context audit events
(registry mutations, control-plane state changes) routed to the
control-plane database per D35's empty-string sentinel for
``tenant_id``. The schema mirrors the per-tenant ``tenant_audit`` table
from S11 column-for-column so the hash-chain helpers in
``contexts/audit/domain/events.py`` operate identically against either
destination.

The CHECK constraint on ``tenant_id`` differs from the per-tenant
table: control-plane rows must carry the empty-string sentinel.
Accidental cross-destination writes (an event with a real tenant id
landing here, or a control-plane event landing on a per-tenant table)
fail at the schema layer rather than silently corrupting the chain
on the wrong destination (D37).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0002_create_cp_tenant_audit"
down_revision: Union[str, None] = "0001_create_tenant_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_audit",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Empty-string sentinel for control-plane scope (D35).
        # The schema-level CHECK below makes the sentinel a hard
        # invariant; the routing if-statement in the audit adapter
        # is the application-layer counterpart.
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("action_verb", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column("before_state", pg.JSONB(), nullable=False),
        sa.Column("after_state", pg.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("previous_event_hash", sa.Text(), nullable=False),
        sa.Column("this_event_hash", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "tenant_id = ''",
            name="control_plane_tenant_audit_sentinel_check",
        ),
    )
    op.create_index(
        "ix_control_plane_tenant_audit_timestamp",
        "tenant_audit",
        ["timestamp"],
    )
    op.create_index(
        "ix_control_plane_tenant_audit_correlation_id",
        "tenant_audit",
        ["correlation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_control_plane_tenant_audit_correlation_id",
        table_name="tenant_audit",
    )
    op.drop_index(
        "ix_control_plane_tenant_audit_timestamp",
        table_name="tenant_audit",
    )
    op.drop_table("tenant_audit")
