"""add `created_by_user_id` column to tenant_registry for D101 actor provenance

Revision ID: 0011_tenant_actor_provenance
Revises: 0010_role_tool_allowlist_pin
Create Date: 2026-05-14

D101 commits actor provenance at the tenant_registry table so the
canonical wipe-guard pattern `created_by_user_id NOT LIKE 'migration:%'`
applies symmetrically with methodology_templates, methodology_revisions,
role_templates, role_revisions, tools, and tool_revisions. The S30b/S31/
S35 wipe class (test fixtures clearing migration-seeded tenant rows)
becomes structurally preventable rather than per-fixture vigilance.

Backfill strategy: server-side default `'migration:0001'` populates
existing rows transparently at column-add time, then the default is
dropped so subsequent inserts must supply the value explicitly via
`PostgresTenantRegistry.register_tenant` deriving it from
`principal.subject`.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_tenant_actor_provenance"
down_revision: Union[str, None] = "0010_role_tool_allowlist_pin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenant_registry",
        sa.Column(
            "created_by_user_id",
            sa.Text(),
            nullable=False,
            server_default="migration:0001",
        ),
    )
    # Drop the server-side default: production writes pass the value
    # explicitly via PostgresTenantRegistry.register_tenant per D101.
    op.alter_column(
        "tenant_registry",
        "created_by_user_id",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("tenant_registry", "created_by_user_id")
