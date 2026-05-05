"""add cost-attribution and cost-ceiling columns to tenant_registry

Revision ID: 0003_add_cost_columns
Revises: 0002_create_cp_tenant_audit
Create Date: 2026-05-05

D41 commits per-tenant cost attribution as a Phase 1 architectural
commitment. The column lands here as a retrofit relative to the
preference for landing it at P3 open; D41's reasoning section is
explicit about the cost. The cost-ceiling configuration columns
land alongside as forward-affordance per the P4-open framing decision
recorded in charter/packages/p4-epic.md (Kano: must-have, same logic
D41 used for the cost-attribution column itself — avoidable retrofit
is a learning failure given the case study's audit posture).

Forward-affordance discipline:
- ``cost_attribution_id`` is read by the inference adapter (S15) and
  by future cost-rollup queries (P9 onward).
- ``cost_ceiling_usd_monthly`` and ``cost_ceiling_action`` are
  declared at this revision as forward-affordance only. The columns
  are not read by any code path until Phase 2 enforcement
  architecture lands. Migration comments here mark the columns as
  not-yet-read; if the comment-level rule needs structural
  enforcement (the structural-promotion threshold convention from
  S11/S12), an AST test asserting no live consumer of either column
  is the candidate.

The CHECK constraint on ``cost_ceiling_action`` lists four values
covering the action space a future enforcement surface might take:
``block`` (refuse calls), ``throttle`` (slow but allow), ``notify``
(allow but raise an alert), and ``audit_only`` (record but no
behavioural change). The values are honest forward-affordance — no
caller reads them at S14 — but constrain the column at the schema
layer so unknown values cannot accidentally land.

Tenant isolation: this migration applies only to the control-plane
track. Per-tenant DBs have no ``tenant_registry`` table at all per
D32's instance independence; per-tenant Alembic track is unchanged
at this revision.

Backfill strategy: existing rows populate ``cost_attribution_id``
with the textual form of ``tenant_id`` (1:1 mapping at inception).
Future tenants may share an attribution id (e.g., subsidiaries of
one parent organisation sharing billing); the column is intentionally
text rather than uuid to allow non-tenant-shaped values when that
shape stabilises.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_cost_columns"
down_revision: Union[str, None] = "0002_create_cp_tenant_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COST_CEILING_ACTION_VALUES = ("block", "throttle", "notify", "audit_only")


def upgrade() -> None:
    # cost_attribution_id: nullable for the add, backfilled to
    # tenant_id, then NOT NULL set. This avoids needing a default at
    # the schema layer (the column is honestly per-tenant data, not
    # a default-shaped column).
    op.add_column(
        "tenant_registry",
        sa.Column("cost_attribution_id", sa.Text(), nullable=True),
    )
    op.execute(
        "UPDATE tenant_registry SET cost_attribution_id = tenant_id::text "
        "WHERE cost_attribution_id IS NULL"
    )
    op.alter_column(
        "tenant_registry", "cost_attribution_id", nullable=False
    )

    # Forward-affordance per D41. Not read by any code path at S14;
    # enforcement architecture lands in Phase 2.
    op.add_column(
        "tenant_registry",
        sa.Column("cost_ceiling_usd_monthly", sa.Numeric(), nullable=True),
    )

    # Forward-affordance per D41. CHECK pins the action space at the
    # schema layer so unknown values cannot land before enforcement
    # consumes them.
    op.add_column(
        "tenant_registry",
        sa.Column(
            "cost_ceiling_action",
            sa.Text(),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "tenant_registry_cost_ceiling_action_check",
        "tenant_registry",
        "cost_ceiling_action IS NULL OR cost_ceiling_action IN ("
        + ", ".join(f"'{v}'" for v in _COST_CEILING_ACTION_VALUES)
        + ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "tenant_registry_cost_ceiling_action_check",
        "tenant_registry",
        type_="check",
    )
    op.drop_column("tenant_registry", "cost_ceiling_action")
    op.drop_column("tenant_registry", "cost_ceiling_usd_monthly")
    op.drop_column("tenant_registry", "cost_attribution_id")
