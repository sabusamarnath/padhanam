"""create tenant_audit

Revision ID: 0001_create_tenant_audit
Revises:
Create Date: 2026-04-30

The per-tenant audit table holds tenant-scoped audit events written by
the audit context's Postgres adapter (S12). Schema mirrors D22's
specification: actor, tenant_id, jurisdiction, timestamp, action_verb,
resource_type, resource_id, before/after state, correlation_id, and the
two hashes that link this event to its predecessor.

Per D36, the schema is identical across tenants in S11. Tenant-specific
configuration (classification policy, retention) is data in
tenant-configuration tables, not schema variation; those tables land in
later sessions when the use cases that need them arrive.

The table lives on each tenant's data plane (D32) — never on the
control plane. The chain it forms is per-tenant per D35 (per-destination
hash chains; cross-database coordination is rejected by D32's instance
independence).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0001_create_tenant_audit"
down_revision: Union[str, None] = None
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
        # tenant_id is denormalised onto the table even though the
        # table sits on the routed tenant's database — every row
        # belongs to one tenant by construction. Storing the column
        # keeps the row self-describing for the hash-chain helpers
        # (D22, D35) and for any operator-context cross-database
        # forensic query that lands later.
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column("action_verb", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column("before_state", pg.JSONB(), nullable=False),
        sa.Column("after_state", pg.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("previous_event_hash", sa.Text(), nullable=False),
        sa.Column("this_event_hash", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_tenant_audit_timestamp",
        "tenant_audit",
        ["timestamp"],
    )
    op.create_index(
        "ix_tenant_audit_correlation_id",
        "tenant_audit",
        ["correlation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_audit_correlation_id", table_name="tenant_audit")
    op.drop_index("ix_tenant_audit_timestamp", table_name="tenant_audit")
    op.drop_table("tenant_audit")
