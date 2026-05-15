"""create gold_sets, gold_set_revisions, gold_set_entries (D109)

Revision ID: 0013_retrieval_evaluation_substrate
Revises: 0012_revise_citation_snapshots
Create Date: 2026-05-15

Per-tenant substrate for ``contexts/retrieval_evaluation/`` per D109.
Three tables on each tenant's dedicated Postgres data plane per D32:

- ``gold_sets``: aggregate root. ``UNIQUE(tenant_id, name)`` per
  D109 commitment 1; ``current_revision_id`` is a deferred FK to
  ``gold_set_revisions.id`` so the create-gold-set use case can
  insert aggregate + initial draft revision in a single transaction
  with the FK check fired at commit time.

- ``gold_set_revisions``: append-only revision rows with
  ``UNIQUE(gold_set_id, revision_number)`` per D109 commitment 2.
  ``status`` CHECK pins {'draft', 'finalized'}; finalize-time hash
  fields are nullable on draft rows and populated on finalize.

- ``gold_set_entries``: ordered entries (query plus expected chunk
  ID array) with ``UNIQUE(gold_set_revision_id, entry_index)`` per
  D109 commitment 3.

No foreign key from ``gold_set_entries.expected_chunk_ids`` to
``chunks.id`` per D109 commitment 3 reasoning: chunk lifecycle is
independent of gold-set authoring; missing-chunk cases land at
metric-computation time at S40.

CHECK-constraint naming follows the ``0011_create_run_history``
pattern (``<table>_<column>_<description>_check``).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0013_retrieval_evaluation_substrate"
down_revision: Union[str, None] = "0012_revise_citation_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_STATUSES = ("draft", "finalized")


def upgrade() -> None:
    # --- gold_sets ---
    op.create_table(
        "gold_sets",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "current_revision_id", pg.UUID(as_uuid=False), nullable=True
        ),
    )
    op.create_check_constraint(
        "gold_sets_jurisdiction_nonempty_check",
        "gold_sets",
        "jurisdiction <> ''",
    )
    op.create_check_constraint(
        "gold_sets_name_nonempty_check",
        "gold_sets",
        "name <> ''",
    )
    op.create_unique_constraint(
        "gold_sets_tenant_name_unique",
        "gold_sets",
        ["tenant_id", "name"],
    )

    # --- gold_set_revisions ---
    op.create_table(
        "gold_set_revisions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "gold_set_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("gold_sets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "finalized_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("this_event_hash", sa.Text(), nullable=True),
        sa.Column("previous_event_hash", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "gold_set_revisions_revision_number_positive_check",
        "gold_set_revisions",
        "revision_number >= 1",
    )
    op.create_check_constraint(
        "gold_set_revisions_status_check",
        "gold_set_revisions",
        "status IN (" + ", ".join(f"'{v}'" for v in _STATUSES) + ")",
    )
    # Pairing CHECK: finalized rows carry all three finalization
    # fields; draft rows carry none. The application-layer use case
    # invariants per D109 commitment 2 enforce the same shape; this
    # is defence-in-depth at the schema layer.
    op.create_check_constraint(
        "gold_set_revisions_finalized_pairing_check",
        "gold_set_revisions",
        (
            "(status = 'draft' AND finalized_at IS NULL "
            "AND this_event_hash IS NULL AND previous_event_hash IS NULL) "
            "OR (status = 'finalized' AND finalized_at IS NOT NULL "
            "AND this_event_hash IS NOT NULL "
            "AND previous_event_hash IS NOT NULL)"
        ),
    )
    op.create_check_constraint(
        "gold_set_revisions_this_event_hash_length_check",
        "gold_set_revisions",
        "this_event_hash IS NULL OR length(this_event_hash) = 64",
    )
    op.create_check_constraint(
        "gold_set_revisions_previous_event_hash_length_check",
        "gold_set_revisions",
        "previous_event_hash IS NULL OR length(previous_event_hash) = 64",
    )
    op.create_unique_constraint(
        "gold_set_revisions_gold_set_revision_unique",
        "gold_set_revisions",
        ["gold_set_id", "revision_number"],
    )
    op.create_index(
        "ix_gold_set_revisions_gold_set_id_status",
        "gold_set_revisions",
        ["gold_set_id", "status"],
    )

    # --- gold_sets.current_revision_id deferred FK ---
    # Now that gold_set_revisions exists, add the deferred FK from
    # gold_sets.current_revision_id → gold_set_revisions.id. Deferred
    # so the create-gold-set use case inserts both rows in one
    # transaction with the check at commit time.
    op.create_foreign_key(
        "gold_sets_current_revision_id_fkey",
        "gold_sets",
        "gold_set_revisions",
        ["current_revision_id"],
        ["id"],
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )

    # --- gold_set_entries ---
    op.create_table(
        "gold_set_entries",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "gold_set_revision_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("gold_set_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("entry_index", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column(
            "expected_chunk_ids",
            pg.ARRAY(pg.UUID(as_uuid=False)),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "gold_set_entries_entry_index_nonnegative_check",
        "gold_set_entries",
        "entry_index >= 0",
    )
    op.create_check_constraint(
        "gold_set_entries_query_nonempty_check",
        "gold_set_entries",
        "query <> ''",
    )
    op.create_check_constraint(
        "gold_set_entries_expected_chunk_ids_nonempty_check",
        "gold_set_entries",
        "array_length(expected_chunk_ids, 1) >= 1",
    )
    op.create_unique_constraint(
        "gold_set_entries_revision_entry_unique",
        "gold_set_entries",
        ["gold_set_revision_id", "entry_index"],
    )


def downgrade() -> None:
    # Forward-only per project discipline; downgrade left as a stub
    # so the alembic CLI does not error when invoked, but production
    # operation never exercises this path.
    op.drop_table("gold_set_entries")
    op.drop_constraint(
        "gold_sets_current_revision_id_fkey", "gold_sets", type_="foreignkey"
    )
    op.drop_table("gold_set_revisions")
    op.drop_table("gold_sets")
