"""matcher_policies: the neutral matcher-policy seam (D186/S91b)

Revision ID: 0035_matcher_policies
Revises: 0034_matcher_quality_runs
Create Date: 2026-06-12

D186/S91b. One row per tenant — the active matcher policy an approved
recommendation writes on apply and the matcher reads on every correlate run. A
single ``suppress_single_signal`` boolean (the first rule) and a timestamp;
**no content**. ``tenant_id`` is the primary key (a tenant has exactly one
policy; apply upserts it). The flag ships **false** — suppressing the live corpus
is a flag flip on the operator's ground-truth verdict (S91a's gate), not this
migration.

Per-tenant only per D32.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0035_matcher_policies"
down_revision: Union[str, None] = "0034_matcher_quality_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "matcher_policies",
        sa.Column("tenant_id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "suppress_single_signal",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("matcher_policies")
