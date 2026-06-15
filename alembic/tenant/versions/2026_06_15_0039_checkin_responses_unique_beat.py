"""commitment_checkin_responses: unique (tenant, commitment, beat_date)

Revision ID: 0039_checkin_responses_unique_beat
Revises: 0038_target_cell_checkin
Create Date: 2026-06-15

S97b's check-in write must be idempotent on (tenant, commitment, beat day)
(D192 Delta-4): a re-confirm or duplicate reply must not write a second
reported_didnt row. The write path guards with a use-case exists-check, and
this unique index is the **by-construction backstop** (race-safe via
``ON CONFLICT DO NOTHING``) on the negative store.

Scoped to ``commitment_checkin_responses`` only. There is deliberately **no**
global unique on ``commitment_completions`` — that table is also written by the
Today "mark done" path, which may legitimately log a multi-dose commitment more
than once a day, and the store carries no origin column to scope a constraint
to check-in-written rows. Completion-side idempotency stays in the check-in
write use case (an exists-by-beat-day guard), not at the DB.

Per-tenant only per D32.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0039_checkin_responses_unique_beat"
down_revision: Union[str, None] = "0038_target_cell_checkin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ux_checkin_responses_tenant_commitment_beat"


def upgrade() -> None:
    op.create_index(
        _INDEX,
        "commitment_checkin_responses",
        ["tenant_id", "commitment_id", "beat_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="commitment_checkin_responses")
