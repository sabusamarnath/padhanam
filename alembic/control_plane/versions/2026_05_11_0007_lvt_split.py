"""split LVT methodology: rename auto-migrated role to LVTGuide

Revision ID: 0007_lvt_split
Revises: 0006_methodology_role_refs
Create Date: 2026-05-11

Data-only migration per D86's LVT methodology + LVTGuide role split
commitment. Operates on the role row that 0006_methodology_role_refs
auto-migrated from the LVT methodology's prior constraint bundle.

Sequence at S23: LVT methodology landed with a single flat content
bundle (D74's shape).
Sequence at S26a-1 commit 3 (0006_methodology_role_refs): the LVT
bundle moved to a role row auto-named "LVTRole" with
created_by_user_id sentinel 'migration:0006_methodology_role_refs'.
This migration (0007_lvt_split) renames that role to "LVTGuide" and
sets a clearer description, then re-anchors the role's revision-1
hash because the role's name and description span its hash payload
per D74's chain-self-containment.

The migration is a no-op when the auto-migrated LVTRole row does not
exist (fresh databases that never seeded LVT; test environments that
truncated the methodology tables). Down-migration reverses the rename
plus description and re-anchors the hash.

Per D86, the LVTGuide role becomes the canonical first-class role for
the LVT methodology going forward; subsequent methodology revisions
that reference the role do so via role_refs entries pointing at this
role's id.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa

from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)


revision: str = "0007_lvt_split"
down_revision: Union[str, None] = "0006_methodology_role_refs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_NAME = "LVTRole"
_NEW_NAME = "LVTGuide"
_NEW_DESCRIPTION = (
    "Lean Value Tree guide role: helps the user place work in the "
    "bet → initiative → epic → story hierarchy, checks alignment "
    "upward and decomposition downward, surfaces drift between "
    "strategic intent and execution."
)
_OLD_DESCRIPTION_TEMPLATE = "Auto-migrated role for LVT methodology"


def _role_content_payload(
    *,
    name: str,
    description: str,
    system_prompt: str,
    source_ids: list,
    tool_allowlist: list,
    retrieval_strategy: dict,
    filter_tree: dict,
    top_k: int,
    min_score: Decimal,
    model_selection: str,
) -> dict[str, Any]:
    """Mirror of the use case layer's role content payload helper."""
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


def _rename_role(*, new_name: str, new_description: str, old_name: str) -> None:
    """Look up the role by old_name (and migration sentinel), rename it,
    and re-anchor its revision-1 hash against the new name/description.
    """
    bind = op.get_bind()
    role_row = bind.execute(
        sa.text(
            """
            SELECT id
            FROM role_templates
            WHERE name = :name
              AND created_by_user_id = 'migration:0006_methodology_role_refs'
            LIMIT 1
            """
        ),
        {"name": old_name},
    ).mappings().first()

    if role_row is None:
        # No LVT seed in this database — fresh control plane or test
        # truncation. Migration is a no-op.
        return

    role_template_id = role_row["id"]

    bind.execute(
        sa.text(
            """
            UPDATE role_templates
            SET name = :name, description = :description
            WHERE id = :id
            """
        ),
        {"name": new_name, "description": new_description, "id": role_template_id},
    )

    # Re-anchor revision-1 hash with the new name + description.
    rev_row = bind.execute(
        sa.text(
            """
            SELECT
                system_prompt, source_ids, tool_allowlist,
                retrieval_strategy, filter_tree, top_k, min_score,
                model_selection, previous_revision_hash
            FROM role_revisions
            WHERE role_template_id = :id AND version = 1
            """
        ),
        {"id": role_template_id},
    ).mappings().first()

    if rev_row is None:
        return

    min_score_value = rev_row["min_score"]
    if not isinstance(min_score_value, Decimal):
        min_score_value = Decimal(str(min_score_value))

    payload = _role_content_payload(
        name=new_name,
        description=new_description,
        system_prompt=rev_row["system_prompt"],
        source_ids=rev_row["source_ids"] or [],
        tool_allowlist=rev_row["tool_allowlist"] or [],
        retrieval_strategy=rev_row["retrieval_strategy"] or {},
        filter_tree=rev_row["filter_tree"] or {},
        top_k=rev_row["top_k"],
        min_score=min_score_value,
        model_selection=rev_row["model_selection"],
    )
    new_hash = compute_revision_hash(
        content_payload=payload,
        previous_hash=rev_row["previous_revision_hash"] or GENESIS_REVISION_HASH,
    )

    bind.execute(
        sa.text(
            """
            UPDATE role_revisions
            SET this_revision_hash = :hash
            WHERE role_template_id = :id AND version = 1
            """
        ),
        {"hash": new_hash, "id": role_template_id},
    )


def upgrade() -> None:
    _rename_role(
        new_name=_NEW_NAME,
        new_description=_NEW_DESCRIPTION,
        old_name=_OLD_NAME,
    )


def downgrade() -> None:
    _rename_role(
        new_name=_OLD_NAME,
        new_description=_OLD_DESCRIPTION_TEMPLATE,
        old_name=_NEW_NAME,
    )
