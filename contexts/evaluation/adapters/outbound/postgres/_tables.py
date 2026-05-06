"""SQLAlchemy Core table definitions for the evaluation schema.

Mirrors the per-tenant Alembic revision ``0003_create_evaluation_tables``.
Defined once here and imported by the repository adapters so the
``Table`` objects are referentially equal across reads and writes.
Core (Table + select/insert) shape over the ORM is consistent with
the tenancy registry adapter (D34): frozen-dataclass-plus-Core keeps
the domain pure and the adapter responsible for the impedance
mismatch.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


_metadata = sa.MetaData()


scoring_sheets = sa.Table(
    "scoring_sheets",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
)

scoring_sheet_revisions = sa.Table(
    "scoring_sheet_revisions",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("scoring_sheet_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
)

scoring_sheet_criteria = sa.Table(
    "scoring_sheet_criteria",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "scoring_sheet_revision_id", pg.UUID(as_uuid=False), nullable=False
    ),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("levels", pg.JSONB, nullable=False),
    sa.Column("ordering", sa.Integer, nullable=False),
)

appliers = sa.Table(
    "appliers",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "scoring_sheet_revision_id", pg.UUID(as_uuid=False), nullable=False
    ),
    sa.Column("criterion_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("applier_type", sa.Text, nullable=False),
    sa.Column("deterministic_function_name", sa.Text, nullable=True),
    sa.Column("prompt_template", sa.Text, nullable=True),
    sa.Column("judge_model", sa.Text, nullable=True),
)

interaction_sets = sa.Table(
    "interaction_sets",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
)

interactions = sa.Table(
    "interactions",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("interaction_set_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("input", pg.JSONB, nullable=False),
    sa.Column("expected_output", pg.JSONB, nullable=True),
    sa.Column("ordering", sa.Integer, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
)

rubric_applications = sa.Table(
    "rubric_applications",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "scoring_sheet_revision_id", pg.UUID(as_uuid=False), nullable=False
    ),
    sa.Column("criterion_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("interaction_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("applier_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("automated_score", sa.Text, nullable=True),
    sa.Column("human_score", sa.Text, nullable=True),
    sa.Column("reviewed_by_user_id", sa.Text, nullable=True),
    sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("trace_id", sa.Text, nullable=True),
)
