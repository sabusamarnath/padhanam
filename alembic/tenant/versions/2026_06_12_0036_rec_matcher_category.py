"""recommendations: allow the matcher_suppression category in the check constraint

Revision ID: 0036_rec_matcher_category
Revises: 0035_matcher_policies
Create Date: 2026-06-12

D185/D186 fix. The ``recommendations_category_check`` constraint (migration 0015)
allowed only the four inference categories; S91a added the ``matcher_suppression``
category to the domain enum + the citation union, but the unit tests used
in-memory fake repositories, so the live Postgres constraint was never exercised
— ``optimization run`` failed to persist the matcher recommendation
(CheckViolationError) and the generate→apply path could not produce an id to
apply. This widens the constraint to include ``matcher_suppression``.

Per-tenant only per D32.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0036_rec_matcher_category"
down_revision: Union[str, None] = "0035_matcher_policies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = (
    "category IN ('retrieval_strategy', 'model_choice', "
    "'prompt_revision', 'cost_optimization')"
)
_NEW = (
    "category IN ('retrieval_strategy', 'model_choice', "
    "'prompt_revision', 'cost_optimization', 'matcher_suppression')"
)


def upgrade() -> None:
    op.drop_constraint(
        "recommendations_category_check", "recommendations", type_="check"
    )
    op.create_check_constraint(
        "recommendations_category_check", "recommendations", _NEW
    )


def downgrade() -> None:
    op.drop_constraint(
        "recommendations_category_check", "recommendations", type_="check"
    )
    op.create_check_constraint(
        "recommendations_category_check", "recommendations", _OLD
    )
