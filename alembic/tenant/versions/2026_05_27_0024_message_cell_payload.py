"""add cell_payload to messages (D141, S52)

Revision ID: 0024_message_cell_payload
Revises: 0023_pending_clar_target_cell
Create Date: 2026-05-27

D141's ConversationFlow cell-payload persistence: a JSONB column on
the messages table where each ConversationFlow implementer's response
value object's implementer-specific state extends beyond the
CitedResponse Protocol fields. Mirror-conversation's
``current_focus_artefact`` (carrying the drill-down navigation anchor)
is the first user.

No CHECK constraint on shape. The column is opaque JSONB at the
persistence layer; each ConversationFlow implementer validates the
shape on read per D141. Mismatched or absent payload routes through
D139 to D134 clarification per the implementer's cell-flow
commitment.

Existing rows have ``cell_payload`` null; the column's nullability
handles the backfill cleanly without an explicit data migration.
Audit-conversation and manual_entry do not populate the column;
mirror-conversation at S52 is the only implementer with a non-null
payload shape at P14 close.

The domain-level pairing rule (INBOUND messages must not carry
cell_payload) is enforced at the Message dataclass's __post_init__,
not at the database CHECK level — D141's "implementer-side
validation" discipline keeps the persistence layer opaque.

Per Finding 1 at S52 pre-write reconciliation: the brief's framing-time
number 0023 was bumped to 0024 following the D140 / Alembic 0023
renumber (operator approval 2026-05-27).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0024_message_cell_payload"
down_revision: Union[str, None] = "0023_pending_clar_target_cell"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("cell_payload", pg.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "cell_payload")
