"""add per-tenant tenant_audit sentinel CHECK

Revision ID: 0002_audit_sentinel_check
Revises: 0001_create_tenant_audit
Create Date: 2026-04-30

D37's defense-in-depth around audit destination routing: per-tenant
rows must carry a non-empty ``tenant_id``. The empty-string sentinel
is reserved for the control-plane audit table per D35; routing
the empty-string sentinel to a per-tenant table is a schema-layer
constraint violation rather than silent corruption of the per-tenant
chain.

Mirrors the symmetric ``tenant_id = ''`` CHECK on the control-plane
``tenant_audit`` table (revision 0002 on the control-plane track).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0002_audit_sentinel_check"
down_revision: Union[str, None] = "0001_create_tenant_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "tenant_audit_non_empty_tenant_id_check",
        "tenant_audit",
        "tenant_id <> ''",
    )


def downgrade() -> None:
    op.drop_constraint(
        "tenant_audit_non_empty_tenant_id_check",
        "tenant_audit",
        type_="check",
    )
