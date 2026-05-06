"""create evaluation tables

Revision ID: 0003_create_evaluation_tables
Revises: 0002_audit_sentinel_check
Create Date: 2026-05-06

The evaluation harness data model lands here per D53. Seven tables
land together on the per-tenant track: ``scoring_sheets``,
``scoring_sheet_revisions``, ``scoring_sheet_criteria``, ``appliers``,
``interaction_sets``, ``interactions``, ``rubric_applications``.

Per-tenant-only per D32. Storage on tenant data planes, never on the
control plane; the platform-baseline scoring sheet library is deferred
per D53. The tenant-isolation contract test at
``tests/contract/tenant_isolation/test_evaluation_isolation.py``
asserts the tables exist on tenant_a and tenant_b and not on the
control-plane DB.

Cross-column NULL invariants on ``appliers`` (e.g.
``deterministic_function_name`` non-null iff
``applier_type='deterministic'``) are enforced at the domain layer
rather than via schema CHECKs per S16 framing — STI vs CTI is a
watch-item if S17's prompt-applier addition or future applier types
strain the type-tag-plus-nullable shape. The CHECK on
``applier_type`` itself pins the type-tag space to the three known
values so unknown applier_types cannot land.

Score columns (``automated_score``, ``human_score``) are TEXT per D55.
Score interpretation is criterion-level: each criterion's ``levels``
jsonb encodes the level definitions; downstream consumers
(cost-per-successful-task at S17, regression report at S18,
recommendation surface at P11) read those to determine pass/fail or
threshold breaches. Direct ``AVG(automated_score)`` is foreclosed and
is not the intended access pattern.

Adapter consumers per the S14 schema-tightening convention: the
rubric-application repository adapter at
``contexts/evaluation/adapters/outbound/postgres/rubric_application_repository.py``
lands in commit 4 and is the only consumer of these tables at S16.
The S16 integration test under ``tests/integration/evaluation/``
exercises the full read/write surface end-to-end.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0003_create_evaluation_tables"
down_revision: Union[str, None] = "0002_audit_sentinel_check"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_APPLIER_TYPE_VALUES = ("deterministic", "prompt", "human")


def upgrade() -> None:
    op.create_table(
        "scoring_sheets",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "scoring_sheet_revisions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scoring_sheet_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("scoring_sheets.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "scoring_sheet_id",
            "version",
            name="scoring_sheet_revisions_sheet_version_unique",
        ),
    )

    op.create_table(
        "scoring_sheet_criteria",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scoring_sheet_revision_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("scoring_sheet_revisions.id"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("levels", pg.JSONB(), nullable=False),
        sa.Column("ordering", sa.Integer(), nullable=False),
    )

    op.create_table(
        "appliers",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scoring_sheet_revision_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("scoring_sheet_revisions.id"),
            nullable=False,
        ),
        sa.Column(
            "criterion_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("scoring_sheet_criteria.id"),
            nullable=False,
        ),
        sa.Column("applier_type", sa.Text(), nullable=False),
        sa.Column("deterministic_function_name", sa.Text(), nullable=True),
        sa.Column("prompt_template", sa.Text(), nullable=True),
        sa.Column("judge_model", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "appliers_applier_type_check",
        "appliers",
        "applier_type IN ("
        + ", ".join(f"'{v}'" for v in _APPLIER_TYPE_VALUES)
        + ")",
    )

    op.create_table(
        "interaction_sets",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "interactions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "interaction_set_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("interaction_sets.id"),
            nullable=False,
        ),
        sa.Column("input", pg.JSONB(), nullable=False),
        sa.Column("expected_output", pg.JSONB(), nullable=True),
        sa.Column("ordering", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "rubric_applications",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scoring_sheet_revision_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("scoring_sheet_revisions.id"),
            nullable=False,
        ),
        sa.Column(
            "criterion_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("scoring_sheet_criteria.id"),
            nullable=False,
        ),
        sa.Column(
            "interaction_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("interactions.id"),
            nullable=False,
        ),
        sa.Column(
            "applier_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("appliers.id"),
            nullable=False,
        ),
        sa.Column("automated_score", sa.Text(), nullable=True),
        sa.Column("human_score", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("rubric_applications")
    op.drop_table("interactions")
    op.drop_table("interaction_sets")
    op.drop_constraint(
        "appliers_applier_type_check", "appliers", type_="check"
    )
    op.drop_table("appliers")
    op.drop_table("scoring_sheet_criteria")
    op.drop_table("scoring_sheet_revisions")
    op.drop_table("scoring_sheets")
