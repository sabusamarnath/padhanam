"""commitment_checkin_responses — the check-in negative sibling store (D192, S97a)

The first-class negative that makes Padhanam's daily completion three-state.
``commitment_checkin_responses`` records a per-commitment, per-beat-date check-in
outcome. Under the Option-B did-source (D192), dids keep flowing to
``commitment_completions`` (the single authoritative did-source the cadence read
consults via ``MAX(completed_at)``); this table carries the ``reported_didnt``
negatives the cadence read consults for ``last_reported_didnt``. Silence writes
no row. ``beat_date`` is the day the outcome refers to (backfillable — a past
date is accepted). The ``outcome`` CHECK admits both values for S97b's
write-path flexibility, but S97a reads dids only from completions.

Append-only, per-tenant (database-per-tenant, D32), tenant_id + jurisdiction per
D12. FK to commitments ON DELETE CASCADE, mirroring commitment_completions.

The revision string ``0037_checkin_responses`` is 22 chars, under the alembic
ceiling per the captures-documented migration name-length convention.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision: str = "0037_checkin_responses"
down_revision: Union[str, None] = "0036_rec_matcher_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commitment_checkin_responses",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "commitment_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("commitments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("beat_date", sa.Date(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "outcome IN ('did', 'reported_didnt')",
            name="commitment_checkin_responses_outcome_check",
        ),
    )
    op.create_index(
        "ix_commitment_checkin_responses_commitment_id",
        "commitment_checkin_responses",
        ["commitment_id"],
    )
    op.create_index(
        "ix_commitment_checkin_responses_tenant_id",
        "commitment_checkin_responses",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_table("commitment_checkin_responses")
