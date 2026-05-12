"""create tools and tool_revisions; seed retrieval tool

Revision ID: 0009_create_tools_tables
Revises: 0008_create_mckinsey_7_step
Create Date: 2026-05-12

Tool registry's persistence schema lands on the control-plane
Postgres instance per D33 and D89's storage-location resolution
(alongside methodologies and roles, not per-tenant as the P8 epic
note initially framed). Per-tenant tool authoring lifts at Phase 2
per the deferred-decisions entry on customer-deployment evidence.

Two tables mirror the methodology / role precedent from S23 / S26a-1:

- ``tools``: human-stable identity for a tool with classification per
  D89's six-category taxonomy. Partial unique index on ``name`` where
  ``archived_at IS NULL`` mirrors the methodology_templates pattern.
  CHECK constraint pins the classification value space to the six
  D89 categories.

- ``tool_revisions``: per-version content (parameters_schema,
  returns_schema, bc_result forward-affordance column) plus hash-chain
  pointers per D26. ``bc_result`` defaults to ``{}`` at commit 2 / 3;
  commit 6's BC stub populates it at create_tool_revision time.

The retrieval tool seeds as part of this migration with the fixed UUID
``00000000-0000-0000-0000-000000000001``. The well-known UUID exists
so platform-managed role allowlists can reference retrieval durably
across the role allowlist tuple-shape migration at S28b commit 4. The
classification is ``read-only`` per D89. The parameters_schema
matches the prior hardcoded ``_RETRIEVAL_TOOL_DEFINITION`` in
``contexts/agent/adapters/outbound/agent_loop_executor.py`` from S27b
verbatim. The returns_schema is a string shape because retrieval
results format as a single tool-result string at the loop boundary
(see ``_format_chunks_as_tool_result`` in the executor).

Hashes computed via ``padhanam.security.hash_chain.compute_revision_hash``
imported directly. The canonical-JSON encoding (sorted keys, format-f
Decimal, UUID-to-str) matches the use case layer at commit 3 byte-
equivalent so chain integrity verification against migration-seeded
rows succeeds.

Idempotency: guards on the retrieval tool's id. If the row already
exists, the migration leaves it untouched.

Downgrade: drops the seeded retrieval row by id, then drops the two
tables. The two-step drop is so the post-migration use case rows (any
operator-authored tools, when commit 8's CLI lands) would also be
removed by the table drop without manual cleanup; the explicit id-
guarded delete is just there to be order-independent if the table
drop is partial.

Out of scope:
- ``role_revisions.tool_allowlist`` shape migration (lands at S28b
  commit 4 via Alembic 0010_role_tool_allowlist_pin).
- BC stub computation (lands at S28b commit 6).
- Per-tenant tool storage (deferred to Phase 2 per D89's
  deferred-decisions trajectory).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)


revision: str = "0009_create_tools_tables"
down_revision: Union[str, None] = "0008_create_mckinsey_7_step"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Well-known UUID per D89 commit-2 reasoning. The constant is the
# durable anchor for platform-managed roles to reference retrieval
# across the commit-4 role allowlist tuple-shape migration. The
# constant lives in the migration to keep migration intent self-
# documenting; the seed_helpers test asserts the constant matches
# the runtime tools-registry seed.
RETRIEVAL_TOOL_ID = UUID("00000000-0000-0000-0000-000000000001")
RETRIEVAL_TOOL_NAME = "retrieval"
RETRIEVAL_TOOL_DESCRIPTION = (
    "Search the agent's grounded knowledge base for relevant chunks "
    "matching the query. Returns text excerpts ranked by relevance."
)
RETRIEVAL_PARAMETERS_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The natural-language search query.",
        },
    },
    "required": ["query"],
}
RETRIEVAL_RETURNS_SCHEMA = {
    "type": "string",
    "description": (
        "A single string containing the chunks formatted as "
        "'[score=N.NNN] <chunk text>' joined by blank lines, or "
        "'(no chunks matched the query)' on empty result."
    ),
}

_MIGRATION_ACTOR = "migration:0009_create_tools_tables"
_CLASSIFICATION_VALUES = (
    "read-only",
    "drafting",
    "user-affecting-with-consent",
    "financial",
    "communication",
    "legal",
)


def upgrade() -> None:
    op.create_table(
        "tools",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("classification", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "classification IN ("
            + ", ".join(f"'{v}'" for v in _CLASSIFICATION_VALUES)
            + ")",
            name="tools_classification_check",
        ),
    )

    op.create_index(
        "ix_tools_name_unique_active",
        "tools",
        ["name"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    op.create_table(
        "tool_revisions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tool_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("tools.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("parameters_schema", pg.JSONB(), nullable=False),
        sa.Column("returns_schema", pg.JSONB(), nullable=False),
        sa.Column(
            "bc_result",
            pg.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("previous_revision_hash", sa.Text(), nullable=False),
        sa.Column("this_revision_hash", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "tool_id",
            "version",
            name="tool_revisions_tool_version_unique",
        ),
    )

    _seed_retrieval_tool()


def _seed_retrieval_tool() -> None:
    """Idempotent seed of the platform-managed retrieval tool."""
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM tools WHERE id = :tid"),
        {"tid": str(RETRIEVAL_TOOL_ID)},
    ).first()
    if existing is not None:
        return

    now = datetime.now(timezone.utc)

    bind.execute(
        sa.text(
            "INSERT INTO tools "
            "(id, name, description, classification, created_by_user_id, "
            " created_at, archived_at) "
            "VALUES (:id, :name, :description, :classification, :actor, "
            "        :created_at, NULL)"
        ),
        {
            "id": str(RETRIEVAL_TOOL_ID),
            "name": RETRIEVAL_TOOL_NAME,
            "description": RETRIEVAL_TOOL_DESCRIPTION,
            "classification": "read-only",
            "actor": _MIGRATION_ACTOR,
            "created_at": now,
        },
    )

    revision_id = UUID("00000000-0000-0000-0000-000000000002")
    this_hash = compute_revision_hash(
        content_payload={
            "name": RETRIEVAL_TOOL_NAME,
            "description": RETRIEVAL_TOOL_DESCRIPTION,
            "classification": "read-only",
            "parameters_schema": RETRIEVAL_PARAMETERS_SCHEMA,
            "returns_schema": RETRIEVAL_RETURNS_SCHEMA,
        },
        previous_hash=GENESIS_REVISION_HASH,
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO tool_revisions
              (id, tool_id, version,
               parameters_schema, returns_schema, bc_result,
               created_by_user_id, created_at,
               previous_revision_hash, this_revision_hash)
            VALUES
              (:id, :tool_id, :version,
               CAST(:parameters_schema AS jsonb),
               CAST(:returns_schema AS jsonb),
               CAST(:bc_result AS jsonb),
               :actor, :created_at, :prev, :this)
            """
        ),
        {
            "id": str(revision_id),
            "tool_id": str(RETRIEVAL_TOOL_ID),
            "version": 1,
            "parameters_schema": json.dumps(
                RETRIEVAL_PARAMETERS_SCHEMA,
                sort_keys=True,
            ),
            "returns_schema": json.dumps(
                RETRIEVAL_RETURNS_SCHEMA,
                sort_keys=True,
            ),
            "bc_result": json.dumps({}),
            "actor": _MIGRATION_ACTOR,
            "created_at": now,
            "prev": GENESIS_REVISION_HASH,
            "this": this_hash,
        },
    )


def downgrade() -> None:
    op.drop_table("tool_revisions")
    op.drop_index(
        "ix_tools_name_unique_active",
        table_name="tools",
    )
    op.drop_table("tools")
