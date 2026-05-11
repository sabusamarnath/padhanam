"""refactor methodology_revisions to use role_refs

Revision ID: 0006_methodology_role_refs
Revises: 0005_role_tables
Create Date: 2026-05-11

S26a-1 methodology v3 refactor per D86. The methodology aggregate
becomes a playbook composing roles rather than carrying the constraint
bundle directly; ``methodology_revisions`` loses (system_prompt,
source_ids, tool_allowlist, retrieval_strategy, filter_tree, top_k,
min_score, model_selection) and gains ``role_refs jsonb`` (array of
``{role_id, role_version, overrides}`` entries per D86).

Migration sequence:

1. Add ``role_refs jsonb`` (nullable for the in-flight migration with
   default ``'[]'::jsonb`` so the column can be added against tables
   that may or may not contain pre-existing rows).
2. For each existing methodology revision row: read the bundle
   fields, INSERT a new ``role_templates`` row named
   "{methodology_name}Role" (commit 4 renames LVT's role to LVTGuide),
   INSERT a new ``role_revisions`` row with version 1 carrying the
   bundle content and a fresh hash anchored at the genesis sentinel,
   UPDATE the methodology revision's ``role_refs`` to point at the
   new role. Recompute the methodology revision's hash chain against
   the new content surface (name, description, role_refs) at the
   migration boundary; the chain integrity check at audit time
   verifies against the post-migration content.
3. DROP the constraint bundle columns from ``methodology_revisions``.
4. ALTER ``role_refs`` to NOT NULL.

Down-migration reverses the structural changes (re-add bundle
columns, re-derive their values from the first role_ref's resolved
role revision, drop role rows). Lossy when a methodology revision
references multiple roles (Phase 1 has single-role methodologies; the
loss surface is structurally bounded until S26b's multi-role
methodologies land). The down-migration is the audit recovery path,
not a routine operation.

Hash recomputation: the migration imports ``compute_revision_hash``
from ``padhanam.security.hash_chain`` (promoted at S24 per D75). The
canonical-JSON encoding (sorted keys, format-f Decimal, UUID-to-str)
matches the use case layer exactly so the chain integrity check
against the new content surface is byte-equivalent to a create-via-
use-case flow.

Per the brief's D86 reconciliation, the migrated role row's
``source_ids`` and ``tool_allowlist`` come from the methodology
revision's prior bundle (`source_ids` is the field name; D86's
``source_filter`` does not land in Phase 1). ``cost_ceiling`` is not
introduced; the role's content surface stays at the methodology v1
shape's nine bundle fields.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Sequence, Union
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)


revision: str = "0006_methodology_role_refs"
down_revision: Union[str, None] = "0005_role_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _role_content_payload(
    *,
    name: str,
    description: str | None,
    system_prompt: str,
    source_ids: list,
    tool_allowlist: list,
    retrieval_strategy: dict,
    filter_tree: dict,
    top_k: int,
    min_score: Decimal,
    model_selection: str,
) -> dict[str, Any]:
    """Mirror of contexts/methodology/application/use_cases.py:_role_content_payload.

    Kept inline here so the migration is self-contained (an Alembic
    revision importing application-layer helpers would couple migration
    history to application code that may evolve after the migration
    has run). The shape is structural; if the application helper
    drifts, the post-migration hash chain integrity check at the
    methodology integration tests will surface the drift.
    """
    return {
        "name": name,
        "description": description or "",
        "system_prompt": system_prompt,
        "source_ids": sorted(str(s) for s in source_ids),
        "tool_allowlist": sorted(str(t) for t in tool_allowlist),
        "retrieval_strategy": dict(retrieval_strategy),
        "filter_tree": dict(filter_tree),
        "top_k": top_k,
        "min_score": min_score,
        "model_selection": model_selection,
    }


def _methodology_content_payload(
    *,
    name: str,
    description: str | None,
    role_refs: list,
) -> dict[str, Any]:
    """Mirror of the post-D86 _content_payload for methodology hashes."""
    canonical_refs = [
        {
            "role_id": str(r["role_id"]),
            "role_version": r["role_version"],
            "overrides": r.get("overrides"),
        }
        for r in role_refs
    ]
    canonical_refs.sort(key=lambda r: r["role_id"])
    return {
        "name": name,
        "description": description or "",
        "role_refs": canonical_refs,
    }


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Step 1: add role_refs as nullable jsonb so in-flight migration
    # of existing rows can populate it before NOT NULL constraint
    # tightens at step 4.
    # ------------------------------------------------------------------
    op.add_column(
        "methodology_revisions",
        sa.Column("role_refs", pg.JSONB(), nullable=True),
    )

    bind = op.get_bind()

    # ------------------------------------------------------------------
    # Step 2: read every existing methodology revision and extract its
    # bundle into a freshly-minted role aggregate.
    # ------------------------------------------------------------------
    rev_rows = bind.execute(
        sa.text(
            """
            SELECT
                mr.id AS id,
                mr.methodology_template_id AS methodology_template_id,
                mr.version AS version,
                mr.system_prompt AS system_prompt,
                mr.source_ids AS source_ids,
                mr.tool_allowlist AS tool_allowlist,
                mr.retrieval_strategy AS retrieval_strategy,
                mr.filter_tree AS filter_tree,
                mr.top_k AS top_k,
                mr.min_score AS min_score,
                mr.model_selection AS model_selection,
                mr.created_by_user_id AS created_by_user_id,
                mr.created_at AS created_at,
                mr.previous_revision_hash AS previous_revision_hash,
                mt.name AS template_name,
                mt.description AS template_description
            FROM methodology_revisions mr
            JOIN methodology_templates mt ON mt.id = mr.methodology_template_id
            ORDER BY mr.methodology_template_id, mr.version
            """
        )
    ).mappings().all()

    # First-time role per methodology template: each methodology gets
    # one auto-migrated role rooted at the constraint bundle from its
    # revision 1. Subsequent methodology revisions (if any post-S23)
    # reference the same role; the migration treats role version 1 as
    # the methodology's role at migration time, with subsequent role
    # versions reserved for future authoring.
    role_id_by_methodology: dict[str, str] = {}

    for row in rev_rows:
        methodology_template_id = row["methodology_template_id"]
        methodology_template_id_str = str(methodology_template_id)

        if methodology_template_id_str not in role_id_by_methodology:
            # First time we see this methodology — create its role.
            role_template_id = str(uuid4())
            role_template_name = f"{row['template_name']}Role"
            role_template_description = (
                f"Auto-migrated role for {row['template_name']} methodology"
            )
            now_for_role = row["created_at"]

            bind.execute(
                sa.text(
                    """
                    INSERT INTO role_templates
                        (id, name, description, created_by_user_id, created_at)
                    VALUES
                        (:id, :name, :description, :created_by_user_id, :created_at)
                    """
                ),
                {
                    "id": role_template_id,
                    "name": role_template_name,
                    "description": role_template_description,
                    "created_by_user_id": "migration:0006_methodology_role_refs",
                    "created_at": now_for_role,
                },
            )

            # Build the role revision's content payload and compute its
            # hash anchored at GENESIS_REVISION_HASH.
            source_ids_list = row["source_ids"] or []
            tool_allowlist_list = row["tool_allowlist"] or []
            retrieval_strategy_dict = row["retrieval_strategy"] or {}
            filter_tree_dict = row["filter_tree"] or {}
            min_score_value = row["min_score"]
            if not isinstance(min_score_value, Decimal):
                min_score_value = Decimal(str(min_score_value))

            role_payload = _role_content_payload(
                name=role_template_name,
                description=role_template_description,
                system_prompt=row["system_prompt"],
                source_ids=source_ids_list,
                tool_allowlist=tool_allowlist_list,
                retrieval_strategy=retrieval_strategy_dict,
                filter_tree=filter_tree_dict,
                top_k=row["top_k"],
                min_score=min_score_value,
                model_selection=row["model_selection"],
            )
            role_hash = compute_revision_hash(
                content_payload=role_payload,
                previous_hash=GENESIS_REVISION_HASH,
            )

            bind.execute(
                sa.text(
                    """
                    INSERT INTO role_revisions
                        (id, role_template_id, version, system_prompt,
                         source_ids, tool_allowlist, retrieval_strategy,
                         filter_tree, top_k, min_score, model_selection,
                         created_by_user_id, created_at,
                         previous_revision_hash, this_revision_hash)
                    VALUES
                        (:id, :role_template_id, :version, :system_prompt,
                         CAST(:source_ids AS jsonb),
                         CAST(:tool_allowlist AS jsonb),
                         CAST(:retrieval_strategy AS jsonb),
                         CAST(:filter_tree AS jsonb),
                         :top_k, :min_score, :model_selection,
                         :created_by_user_id, :created_at,
                         :previous_revision_hash, :this_revision_hash)
                    """
                ),
                {
                    "id": str(uuid4()),
                    "role_template_id": role_template_id,
                    "version": 1,
                    "system_prompt": row["system_prompt"],
                    "source_ids": json.dumps(
                        [str(s) for s in source_ids_list]
                    ),
                    "tool_allowlist": json.dumps(list(tool_allowlist_list)),
                    "retrieval_strategy": json.dumps(retrieval_strategy_dict),
                    "filter_tree": json.dumps(filter_tree_dict),
                    "top_k": row["top_k"],
                    "min_score": min_score_value,
                    "model_selection": row["model_selection"],
                    "created_by_user_id": "migration:0006_methodology_role_refs",
                    "created_at": now_for_role,
                    "previous_revision_hash": GENESIS_REVISION_HASH,
                    "this_revision_hash": role_hash,
                },
            )

            role_id_by_methodology[methodology_template_id_str] = role_template_id

    # ------------------------------------------------------------------
    # Step 3: re-anchor methodology revision hashes against the new
    # content surface (name, description, role_refs) and populate
    # role_refs.
    # ------------------------------------------------------------------
    # Group revisions by methodology template so we can walk the chain
    # within each template, chaining new hashes forward from the
    # genesis sentinel for revision 1 onwards.
    by_methodology: dict[str, list] = {}
    for row in rev_rows:
        by_methodology.setdefault(str(row["methodology_template_id"]), []).append(row)

    for methodology_template_id_str, group in by_methodology.items():
        # Sort by version ascending so we re-chain the hashes in order.
        group_sorted = sorted(group, key=lambda r: r["version"])
        role_template_id = role_id_by_methodology[methodology_template_id_str]
        role_ref_entry = {
            "role_id": role_template_id,
            "role_version": 1,
            "overrides": None,
        }
        role_refs_json = [role_ref_entry]

        previous_hash = GENESIS_REVISION_HASH
        for row in group_sorted:
            new_payload = _methodology_content_payload(
                name=row["template_name"],
                description=row["template_description"],
                role_refs=role_refs_json,
            )
            new_hash = compute_revision_hash(
                content_payload=new_payload,
                previous_hash=previous_hash,
            )

            bind.execute(
                sa.text(
                    """
                    UPDATE methodology_revisions
                    SET role_refs = CAST(:role_refs AS jsonb),
                        previous_revision_hash = :previous_hash,
                        this_revision_hash = :this_hash
                    WHERE id = :id
                    """
                ),
                {
                    "role_refs": json.dumps(role_refs_json),
                    "previous_hash": previous_hash,
                    "this_hash": new_hash,
                    "id": str(row["id"]),
                },
            )

            previous_hash = new_hash

    # ------------------------------------------------------------------
    # Step 4: drop the constraint bundle columns and tighten role_refs
    # to NOT NULL.
    # ------------------------------------------------------------------
    op.drop_column("methodology_revisions", "system_prompt")
    op.drop_column("methodology_revisions", "source_ids")
    op.drop_column("methodology_revisions", "tool_allowlist")
    op.drop_column("methodology_revisions", "retrieval_strategy")
    op.drop_column("methodology_revisions", "filter_tree")
    op.drop_column("methodology_revisions", "top_k")
    op.drop_column("methodology_revisions", "min_score")
    op.drop_column("methodology_revisions", "model_selection")

    op.alter_column("methodology_revisions", "role_refs", nullable=False)


def downgrade() -> None:
    """Reverse the methodology v3 refactor.

    Re-adds the constraint bundle columns, populates them by reading
    the first role_ref's resolved role revision for each methodology
    revision, then drops role rows that were auto-created by the
    upgrade. Lossy for multi-role methodologies (only single-role
    exists at S26a-1; the loss surface is structurally bounded).
    """
    op.add_column(
        "methodology_revisions",
        sa.Column("system_prompt", sa.Text(), nullable=True),
    )
    op.add_column(
        "methodology_revisions",
        sa.Column("source_ids", pg.JSONB(), nullable=True),
    )
    op.add_column(
        "methodology_revisions",
        sa.Column("tool_allowlist", pg.JSONB(), nullable=True),
    )
    op.add_column(
        "methodology_revisions",
        sa.Column("retrieval_strategy", pg.JSONB(), nullable=True),
    )
    op.add_column(
        "methodology_revisions",
        sa.Column("filter_tree", pg.JSONB(), nullable=True),
    )
    op.add_column(
        "methodology_revisions",
        sa.Column("top_k", sa.Integer(), nullable=True),
    )
    op.add_column(
        "methodology_revisions",
        sa.Column("min_score", sa.Numeric(), nullable=True),
    )
    op.add_column(
        "methodology_revisions",
        sa.Column("model_selection", sa.Text(), nullable=True),
    )

    bind = op.get_bind()

    rev_rows = bind.execute(
        sa.text(
            """
            SELECT id, role_refs
            FROM methodology_revisions
            """
        )
    ).mappings().all()

    auto_migrated_role_ids: set[str] = set()

    for row in rev_rows:
        role_refs = row["role_refs"] or []
        if not role_refs:
            continue
        first_ref = role_refs[0]
        role_id = first_ref["role_id"]
        role_version = first_ref["role_version"]

        role_rev = bind.execute(
            sa.text(
                """
                SELECT
                    system_prompt, source_ids, tool_allowlist,
                    retrieval_strategy, filter_tree, top_k, min_score,
                    model_selection
                FROM role_revisions
                WHERE role_template_id = :role_template_id
                  AND version = :version
                """
            ),
            {"role_template_id": role_id, "version": role_version},
        ).mappings().first()

        if role_rev is None:
            continue

        bind.execute(
            sa.text(
                """
                UPDATE methodology_revisions
                SET system_prompt = :system_prompt,
                    source_ids = CAST(:source_ids AS jsonb),
                    tool_allowlist = CAST(:tool_allowlist AS jsonb),
                    retrieval_strategy = CAST(:retrieval_strategy AS jsonb),
                    filter_tree = CAST(:filter_tree AS jsonb),
                    top_k = :top_k,
                    min_score = :min_score,
                    model_selection = :model_selection
                WHERE id = :id
                """
            ),
            {
                "system_prompt": role_rev["system_prompt"],
                "source_ids": json.dumps(role_rev["source_ids"]),
                "tool_allowlist": json.dumps(role_rev["tool_allowlist"]),
                "retrieval_strategy": json.dumps(role_rev["retrieval_strategy"]),
                "filter_tree": json.dumps(role_rev["filter_tree"]),
                "top_k": role_rev["top_k"],
                "min_score": role_rev["min_score"],
                "model_selection": role_rev["model_selection"],
                "id": str(row["id"]),
            },
        )
        auto_migrated_role_ids.add(role_id)

    # Drop role rows that were auto-created by the upgrade. We
    # identify them by the migration's created_by_user_id sentinel
    # so down-migration does not drop roles authored after the
    # upgrade (post-S26a-1).
    bind.execute(
        sa.text(
            """
            DELETE FROM role_revisions
            WHERE created_by_user_id = 'migration:0006_methodology_role_refs'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM role_templates
            WHERE created_by_user_id = 'migration:0006_methodology_role_refs'
            """
        )
    )

    # Tighten newly-added bundle columns to NOT NULL after backfill.
    op.alter_column("methodology_revisions", "system_prompt", nullable=False)
    op.alter_column("methodology_revisions", "source_ids", nullable=False)
    op.alter_column("methodology_revisions", "tool_allowlist", nullable=False)
    op.alter_column("methodology_revisions", "retrieval_strategy", nullable=False)
    op.alter_column("methodology_revisions", "filter_tree", nullable=False)
    op.alter_column("methodology_revisions", "top_k", nullable=False)
    op.alter_column("methodology_revisions", "min_score", nullable=False)
    op.alter_column("methodology_revisions", "model_selection", nullable=False)

    op.drop_column("methodology_revisions", "role_refs")
