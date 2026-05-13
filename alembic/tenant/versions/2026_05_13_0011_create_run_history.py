"""create runs, run_chunk_citations, run_entity_citations (D95)

Revision ID: 0011_create_run_history
Revises: 0010_agent_tool_allowlist_pin
Create Date: 2026-05-13

Per-tenant run-history substrate per D94 / D95. Three tables on
each tenant's dedicated Postgres data plane per D32:

- ``runs``: 15-column structured run record. The rendering
  projection over the canonical audit chain (S29b) per D94 /
  D95's write-timing commitment (shape B). Phase 2 UX consumes
  via the read-side query port at S33; ops drills down via the
  ``trace_id`` join key to the trace store per D27.

- ``run_chunk_citations``: 8-column run-to-chunk linkage with FK
  to ``chunks.id`` (ON DELETE SET NULL so the snapshot survives
  source removal per D94's audit-evidence claim) and rendering-
  grade snapshot columns. Citation rows themselves do not get
  written at S31 — only the table shape lands; population
  semantics settle at S32 per the p9-epic open question.

- ``run_entity_citations``: 8-column run-to-Neo4j-entity linkage
  via the ``(entity_tenant_id, entity_name, entity_type)``
  composite per D64's uniqueness commitment. No Postgres foreign
  key to Neo4j is possible; the snapshot columns carry the
  rendering payload that survives entity merge or removal per
  D94's audit-evidence claim. Population at S32.

CHECK-constraint naming follows the ``0005_create_sources_and_chunks``
pattern (``<table>_<column>_<description>_check``). The
audit-chain partial-state shape (audit_end_hash NULL only when
termination_reason='failed') is enforced by paired CHECKs per
D95's reconciliation finding against the executor's three-shape
``InvocationFailed.partial_audit_chain_state`` (0, 1, or 2
hashes).

``pg.JSONB()`` and ``sa.text("gen_random_uuid()")`` idioms match
``0008_agent_tables`` and ``0005_create_sources_and_chunks``.

Tenant-isolation contract harness extension at
``tests/contract/tenant_isolation/test_run_history_isolation.py``
asserts cross-tenant red-team scenarios per D24 (S31 commit 7).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0011_create_run_history"
down_revision: Union[str, None] = "0010_agent_tool_allowlist_pin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TERMINATION_REASONS = (
    "content",
    "max_iterations",
    "tool_not_registered",
    "error",
    "invariant_blocked",
    "failed",
)


def upgrade() -> None:
    # --- runs ---
    op.create_table(
        "runs",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column(
            "agent_template_id",
            pg.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("agent_template_version", sa.Integer(), nullable=False),
        sa.Column("input_message", sa.Text(), nullable=False),
        sa.Column("output_content", sa.Text(), nullable=False),
        sa.Column(
            "started_at", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column(
            "completed_at", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column("termination_reason", sa.Text(), nullable=False),
        sa.Column("iteration_count", sa.Integer(), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("audit_start_hash", sa.Text(), nullable=False),
        sa.Column("audit_end_hash", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "runs_tenant_id_nonempty_check",
        "runs",
        "tenant_id <> ''",
    )
    op.create_check_constraint(
        "runs_termination_reason_check",
        "runs",
        "termination_reason IN ("
        + ", ".join(f"'{v}'" for v in _TERMINATION_REASONS)
        + ")",
    )
    op.create_check_constraint(
        "runs_iteration_count_check",
        "runs",
        "iteration_count >= 0",
    )
    op.create_check_constraint(
        "runs_total_cost_usd_check",
        "runs",
        "total_cost_usd >= 0",
    )
    op.create_check_constraint(
        "runs_audit_start_hash_length_check",
        "runs",
        "length(audit_start_hash) = 64",
    )
    op.create_check_constraint(
        "runs_audit_end_hash_length_check",
        "runs",
        "audit_end_hash IS NULL OR length(audit_end_hash) = 64",
    )
    # Pairing CHECK: only `failed` terminations may carry NULL
    # `audit_end_hash` per D95's audit-chain partial-state shape.
    # The 1-hash `InvocationFailed.partial_audit_chain_state` case
    # at the executor (loop-body-exception, end-audit-emission
    # failure sites) produces an audited-but-incomplete invocation;
    # this CHECK keeps non-failed terminations from accidentally
    # carrying NULL.
    op.create_check_constraint(
        "runs_audit_end_hash_failed_pairing_check",
        "runs",
        "(termination_reason = 'failed') OR (audit_end_hash IS NOT NULL)",
    )
    op.create_index(
        "ix_runs_agent_template_id",
        "runs",
        ["agent_template_id"],
    )
    op.create_index(
        "ix_runs_started_at",
        "runs",
        ["started_at"],
    )
    op.create_index(
        "ix_runs_trace_id",
        "runs",
        ["trace_id"],
        postgresql_where=sa.text("trace_id IS NOT NULL"),
    )

    # --- run_chunk_citations ---
    op.create_table(
        "run_chunk_citations",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("chunk_excerpt", sa.Text(), nullable=False),
        sa.Column("source_citation", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "run_chunk_citations_tenant_id_nonempty_check",
        "run_chunk_citations",
        "tenant_id <> ''",
    )
    op.create_index(
        "ix_run_chunk_citations_run_id",
        "run_chunk_citations",
        ["run_id"],
    )

    # --- run_entity_citations ---
    op.create_table(
        "run_entity_citations",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_tenant_id", sa.Text(), nullable=False),
        sa.Column("entity_name", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("entity_display_label", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "run_entity_citations_entity_tenant_id_nonempty_check",
        "run_entity_citations",
        "entity_tenant_id <> ''",
    )
    op.create_check_constraint(
        "run_entity_citations_tenant_id_nonempty_check",
        "run_entity_citations",
        "tenant_id <> ''",
    )
    op.create_index(
        "ix_run_entity_citations_run_id",
        "run_entity_citations",
        ["run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_run_entity_citations_run_id",
        table_name="run_entity_citations",
    )
    op.drop_constraint(
        "run_entity_citations_tenant_id_nonempty_check",
        "run_entity_citations",
        type_="check",
    )
    op.drop_constraint(
        "run_entity_citations_entity_tenant_id_nonempty_check",
        "run_entity_citations",
        type_="check",
    )
    op.drop_table("run_entity_citations")

    op.drop_index(
        "ix_run_chunk_citations_run_id",
        table_name="run_chunk_citations",
    )
    op.drop_constraint(
        "run_chunk_citations_tenant_id_nonempty_check",
        "run_chunk_citations",
        type_="check",
    )
    op.drop_table("run_chunk_citations")

    op.drop_index("ix_runs_trace_id", table_name="runs")
    op.drop_index("ix_runs_started_at", table_name="runs")
    op.drop_index("ix_runs_agent_template_id", table_name="runs")
    op.drop_constraint(
        "runs_audit_end_hash_failed_pairing_check", "runs", type_="check"
    )
    op.drop_constraint(
        "runs_audit_end_hash_length_check", "runs", type_="check"
    )
    op.drop_constraint(
        "runs_audit_start_hash_length_check", "runs", type_="check"
    )
    op.drop_constraint("runs_total_cost_usd_check", "runs", type_="check")
    op.drop_constraint("runs_iteration_count_check", "runs", type_="check")
    op.drop_constraint(
        "runs_termination_reason_check", "runs", type_="check"
    )
    op.drop_constraint(
        "runs_tenant_id_nonempty_check", "runs", type_="check"
    )
    op.drop_table("runs")
