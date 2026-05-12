"""role.tool_allowlist tuple-shape pin migration (D89 commit 4)

Revision ID: 0010_role_tool_allowlist_pin
Revises: 0009_create_tools_tables
Create Date: 2026-05-12

Per D89, the role aggregate's ``tool_allowlist`` field migrates from
the prior shape (JSONB array of opaque name strings) to the pinned
tuple shape (JSONB array of ``{"tool_id": <uuid>, "revision_id":
<uuid>}`` dicts). Pinning at role authoring time produces durable
references that survive tool revision evolution per D89's
alternative-(f) reasoning.

Migration behaviour per existing row:

- Empty allowlist (``[]``): no-op, byte-equivalent before and after.
  The seven McKinsey roles seeded at ``0008_create_mckinsey_7_step``
  all have ``tool_allowlist = []``; their content payload encoding
  hashes identically.

- ``["retrieval"]``: resolves to the well-known retrieval tool seeded
  at ``0009_create_tools_tables`` (tool_id
  ``00000000-0000-0000-0000-000000000001``, revision_id
  ``00000000-0000-0000-0000-000000000002``). Hash re-anchoring applied
  per the methodology-precedent at S26a-1's
  ``0006_methodology_role_refs``: recompute the role revision's
  ``this_revision_hash`` against the new content payload, walk the
  chain forward updating downstream revisions' ``previous_revision_hash``
  + ``this_revision_hash``.

- Any other string entry: raises. Phase 1 has retrieval as the only
  named platform-managed tool; an unknown name in an existing
  allowlist would indicate prior corruption or a non-Phase-1
  scenario not covered by this migration.

The hash re-anchoring path is defensive forward-affordance: the
current live DB state has all roles with empty allowlist (the
LVTGuide row from ``0007_lvt_split`` is no longer present per
integration-test fixture truncation), so the recompute path is
unexercised in practice at session close. The path is preserved so
re-seeding the LVT methodology in the future works correctly.

Schema: the column type stays ``jsonb`` (the JSONB primitive accepts
both string-array and object-array shapes). The shape change is
runtime-enforced by the canonical-JSON serialiser in
``contexts.methodology.application.use_cases._role_content_payload``
and the postgres adapter's row-to-domain materialiser. No DDL
required at this migration; the data migration is sufficient.

Downgrade: convert each role revision's allowlist back from the
object shape to the prior string shape by looking up the tool name
from the ``tools`` table. Recompute hashes against the prior
content payload encoding. The downgrade is the audit recovery path
per D26; routine operation does not exercise it.
"""
from __future__ import annotations

import json
from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa

from padhanam.security.hash_chain import compute_revision_hash


revision: str = "0010_role_tool_allowlist_pin"
down_revision: Union[str, None] = "0009_create_tools_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RETRIEVAL_TOOL_ID = "00000000-0000-0000-0000-000000000001"
_RETRIEVAL_REVISION_ID = "00000000-0000-0000-0000-000000000002"


def _resolve_name_to_pin(name: str) -> tuple[str, str]:
    if name == "retrieval":
        return (_RETRIEVAL_TOOL_ID, _RETRIEVAL_REVISION_ID)
    raise ValueError(
        f"unknown tool name {name!r} in role allowlist; "
        f"only 'retrieval' is platform-managed at Phase 1 per D89"
    )


def _role_content_payload(
    *,
    name: str,
    description: str | None,
    system_prompt: str,
    source_ids: list[str],
    tool_allowlist: list[dict],
    retrieval_strategy: dict,
    filter_tree: dict,
    top_k: int,
    min_score: str,
    model_selection: str,
) -> dict:
    """Mirror of the use-case-layer helper for byte-equivalent hashing."""
    from decimal import Decimal

    return {
        "name": name,
        "description": description or "",
        "system_prompt": system_prompt,
        "source_ids": sorted(source_ids),
        "tool_allowlist": sorted(
            (
                {"tool_id": e["tool_id"], "revision_id": e["revision_id"]}
                for e in tool_allowlist
            ),
            key=lambda e: (e["tool_id"], e["revision_id"]),
        ),
        "retrieval_strategy": dict(retrieval_strategy),
        "filter_tree": dict(filter_tree),
        "top_k": top_k,
        "min_score": Decimal(str(min_score)),
        "model_selection": model_selection,
    }


def upgrade() -> None:
    bind = op.get_bind()
    # Fetch all role revisions with their parent template's metadata,
    # ordered by template then version so the chain walk is
    # deterministic.
    rows = bind.execute(
        sa.text(
            """
            SELECT r.id, r.role_template_id, r.version, r.system_prompt,
                   r.source_ids, r.tool_allowlist, r.retrieval_strategy,
                   r.filter_tree, r.top_k, r.min_score, r.model_selection,
                   r.previous_revision_hash, r.this_revision_hash,
                   t.name, t.description
            FROM role_revisions r
            JOIN role_templates t ON t.id = r.role_template_id
            ORDER BY r.role_template_id, r.version
            """
        )
    ).mappings().all()

    # Track per-template re-anchor state: which revisions converted and
    # what their new this_revision_hash is, so subsequent revisions in
    # the same template chain pick up the new previous_revision_hash.
    per_template_latest_hash: dict[str, str] = {}

    for row in rows:
        old_allowlist = row["tool_allowlist"]
        if not isinstance(old_allowlist, list):
            old_allowlist = []

        # Skip already-converted rows (object-shaped). Idempotent on
        # re-run after a partial application.
        if old_allowlist and isinstance(old_allowlist[0], dict):
            continue

        new_allowlist = []
        for entry in old_allowlist:
            if isinstance(entry, str):
                tid, rid = _resolve_name_to_pin(entry)
                new_allowlist.append({"tool_id": tid, "revision_id": rid})
            elif isinstance(entry, dict):
                new_allowlist.append(entry)
            else:
                raise ValueError(
                    f"role revision {row['id']} has unexpected "
                    f"allowlist entry {entry!r}"
                )

        template_id = str(row["role_template_id"])

        # Determine the previous_revision_hash this row should chain
        # from after re-anchoring.
        if template_id in per_template_latest_hash:
            new_prev = per_template_latest_hash[template_id]
        else:
            new_prev = row["previous_revision_hash"]

        new_this_hash = compute_revision_hash(
            content_payload=_role_content_payload(
                name=row["name"],
                description=row["description"],
                system_prompt=row["system_prompt"],
                source_ids=[str(s) for s in row["source_ids"]],
                tool_allowlist=new_allowlist,
                retrieval_strategy=row["retrieval_strategy"],
                filter_tree=row["filter_tree"],
                top_k=row["top_k"],
                min_score=str(row["min_score"]),
                model_selection=row["model_selection"],
            ),
            previous_hash=new_prev,
        )

        bind.execute(
            sa.text(
                """
                UPDATE role_revisions
                SET tool_allowlist = CAST(:al AS jsonb),
                    previous_revision_hash = :prev,
                    this_revision_hash = :this
                WHERE id = :id
                """
            ),
            {
                "al": json.dumps(new_allowlist, sort_keys=True),
                "prev": new_prev,
                "this": new_this_hash,
                "id": str(row["id"]),
            },
        )

        per_template_latest_hash[template_id] = new_this_hash


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT r.id, r.role_template_id, r.version, r.system_prompt,
                   r.source_ids, r.tool_allowlist, r.retrieval_strategy,
                   r.filter_tree, r.top_k, r.min_score, r.model_selection,
                   r.previous_revision_hash, r.this_revision_hash,
                   t.name, t.description
            FROM role_revisions r
            JOIN role_templates t ON t.id = r.role_template_id
            ORDER BY r.role_template_id, r.version
            """
        )
    ).mappings().all()

    per_template_latest_hash: dict[str, str] = {}

    for row in rows:
        new_allowlist = row["tool_allowlist"]
        if not isinstance(new_allowlist, list):
            new_allowlist = []

        # Skip already-downgraded rows (string-shaped).
        if new_allowlist and isinstance(new_allowlist[0], str):
            continue

        old_allowlist = []
        for entry in new_allowlist:
            if isinstance(entry, dict):
                tid = entry["tool_id"]
                if tid == _RETRIEVAL_TOOL_ID:
                    old_allowlist.append("retrieval")
                else:
                    # Look up tool name from the tools table.
                    name_row = bind.execute(
                        sa.text("SELECT name FROM tools WHERE id = :tid"),
                        {"tid": tid},
                    ).first()
                    if name_row is None:
                        raise ValueError(
                            f"cannot downgrade role revision {row['id']}: "
                            f"tool id {tid!r} not found in tools table"
                        )
                    old_allowlist.append(name_row[0])
            elif isinstance(entry, str):
                old_allowlist.append(entry)
            else:
                raise ValueError(
                    f"role revision {row['id']} has unexpected "
                    f"allowlist entry {entry!r}"
                )

        template_id = str(row["role_template_id"])

        if template_id in per_template_latest_hash:
            new_prev = per_template_latest_hash[template_id]
        else:
            new_prev = row["previous_revision_hash"]

        # Reconstruct the pre-D89 content payload shape: tool_allowlist
        # as sorted list of strings (the pre-commit-4 encoding).
        from decimal import Decimal

        old_payload = {
            "name": row["name"],
            "description": row["description"] or "",
            "system_prompt": row["system_prompt"],
            "source_ids": sorted(str(s) for s in row["source_ids"]),
            "tool_allowlist": sorted(old_allowlist),
            "retrieval_strategy": dict(row["retrieval_strategy"]),
            "filter_tree": dict(row["filter_tree"]),
            "top_k": row["top_k"],
            "min_score": Decimal(str(row["min_score"])),
            "model_selection": row["model_selection"],
        }
        new_this_hash = compute_revision_hash(
            content_payload=old_payload,
            previous_hash=new_prev,
        )

        bind.execute(
            sa.text(
                """
                UPDATE role_revisions
                SET tool_allowlist = CAST(:al AS jsonb),
                    previous_revision_hash = :prev,
                    this_revision_hash = :this
                WHERE id = :id
                """
            ),
            {
                "al": json.dumps(old_allowlist),
                "prev": new_prev,
                "this": new_this_hash,
                "id": str(row["id"]),
            },
        )

        per_template_latest_hash[template_id] = new_this_hash
