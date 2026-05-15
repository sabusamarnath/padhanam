"""SQLAlchemy Core table definitions for the retrieval_evaluation per-tenant tables.

Three tables per D109 commitment 1-3 plus the schema additions in
charter/schema.md: ``gold_sets``, ``gold_set_revisions``,
``gold_set_entries``. Shared between the repository (writer) and
reader adapters; both consume the same Table objects to keep the
row-shape contract single-sourced. The Alembic migration at
``alembic/tenant/versions/0013_retrieval_evaluation_substrate.py``
(commit 6) creates the tables matching these definitions.

SQLAlchemy 2.0 Core — no DeclarativeBase, no ORM, per the
run_history precedent at S31.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


metadata = sa.MetaData()


gold_sets = sa.Table(
    "gold_sets",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column("current_revision_id", pg.UUID(as_uuid=False), nullable=True),
    sa.UniqueConstraint(
        "tenant_id", "name", name="gold_sets_tenant_name_unique"
    ),
)


gold_set_revisions = sa.Table(
    "gold_set_revisions",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "gold_set_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("gold_sets.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("revision_number", sa.Integer, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column("finalized_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("this_event_hash", sa.Text, nullable=True),
    sa.Column("previous_event_hash", sa.Text, nullable=True),
    sa.UniqueConstraint(
        "gold_set_id",
        "revision_number",
        name="gold_set_revisions_gold_set_revision_unique",
    ),
    sa.CheckConstraint(
        "status IN ('draft', 'finalized')",
        name="gold_set_revisions_status_check",
    ),
)


gold_set_entries = sa.Table(
    "gold_set_entries",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "gold_set_revision_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("gold_set_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("entry_index", sa.Integer, nullable=False),
    sa.Column("query", sa.Text, nullable=False),
    sa.Column(
        "expected_chunk_ids",
        pg.ARRAY(pg.UUID(as_uuid=False)),
        nullable=False,
    ),
    sa.UniqueConstraint(
        "gold_set_revision_id",
        "entry_index",
        name="gold_set_entries_revision_entry_unique",
    ),
)


__all__ = [
    "gold_set_entries",
    "gold_set_revisions",
    "gold_sets",
    "metadata",
]
