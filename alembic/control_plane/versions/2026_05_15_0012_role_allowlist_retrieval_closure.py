"""role.tool_allowlist retrieval-closure migration (D105 alt-(c) + D108 + D109)

Revision ID: 0012_role_allowlist_retrieval_closure
Revises: 0011_tenant_actor_provenance
Create Date: 2026-05-15

Closes the no-retrieval gap flagged at P8 close and P9 close, routed
to P11 open per D105 alternative (c) rejection and D108's sixth
commitment. The eight seeded roles (``LVTGuide`` plus the seven
McKinsey 7-Step roles: ``ProblemFramer``, ``Disaggregator``,
``Prioritiser``, ``Planner``, ``Analyst``, ``Synthesiser``,
``Communicator``) currently ship with empty ``tool_allowlist``; this
migration UPDATEs each to carry the platform-managed retrieval tool
reference seeded at ``0009_create_tools_tables`` (tool_id
``00000000-0000-0000-0000-000000000001``, revision_id
``00000000-0000-0000-0000-000000000002``).

The UPDATE recomputes each role-revision's ``this_revision_hash``
per D26 chain-self-containment. Without the recompute the chain
integrity verification breaks on every UPDATEd row; the recompute is
the structural integrity work that makes the UPDATE D26-honest, not
a side-detail. Recompute reuses
``padhanam.security.hash_chain.compute_revision_hash`` (the
field-set-agnostic primitive promoted from
``contexts/methodology/`` at S24 commit 8 per D75) following
``0010_role_tool_allowlist_pin``'s helper pattern.

Per-template chain walk forward: if a role has multiple revisions,
each subsequent revision's ``previous_revision_hash`` re-anchors to
the prior revision's new ``this_revision_hash``. At session open the
eight roles each carry a single revision (version=1), so the walk-
forward path is defensive forward-affordance.

Idempotency: rows whose ``tool_allowlist`` already contains the
retrieval reference are skipped; rows whose allowlist is non-empty
with content other than the retrieval reference are skipped (out of
Phase 1 scope; no tenant-authored roles exist at Phase 1).

Downgrade: reverses the UPDATE by removing the retrieval reference
from each named role's allowlist and recomputing hashes against the
empty-allowlist content payload. The downgrade is the audit
recovery path per D26; routine operation does not exercise it.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Mapping, Sequence, Union

from alembic import op
import sqlalchemy as sa

from padhanam.security.hash_chain import compute_revision_hash


revision: str = "0012_role_allowlist_retrieval_closure"
down_revision: Union[str, None] = "0011_tenant_actor_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RETRIEVAL_TOOL_ID = "00000000-0000-0000-0000-000000000001"
_RETRIEVAL_REVISION_ID = "00000000-0000-0000-0000-000000000002"

_RETRIEVAL_ENTRY: dict[str, str] = {
    "tool_id": _RETRIEVAL_TOOL_ID,
    "revision_id": _RETRIEVAL_REVISION_ID,
}

_NAMED_ROLES: tuple[str, ...] = (
    "LVTGuide",
    "ProblemFramer",
    "Disaggregator",
    "Prioritiser",
    "Planner",
    "Analyst",
    "Synthesiser",
    "Communicator",
)


def _role_content_payload(
    *,
    name: str,
    description: str | None,
    system_prompt: str,
    source_ids: list[str],
    tool_allowlist: list[dict[str, str]],
    retrieval_strategy: Mapping[str, Any],
    filter_tree: Mapping[str, Any],
    top_k: int,
    min_score: str,
    model_selection: str,
) -> dict[str, Any]:
    """Mirror of ``0010_role_tool_allowlist_pin._role_content_payload``.

    The shape must be byte-equivalent to the use-case-layer helper at
    ``contexts.methodology.application.use_cases._role_content_payload``
    so the recompute lands hashes that match what would be computed at
    application-time authoring of the same content.
    """
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


def _has_retrieval_entry(allowlist: list[dict[str, str]]) -> bool:
    return any(
        entry.get("tool_id") == _RETRIEVAL_TOOL_ID
        and entry.get("revision_id") == _RETRIEVAL_REVISION_ID
        for entry in allowlist
    )


def upgrade() -> None:
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
            WHERE t.name = ANY(:names)
            ORDER BY r.role_template_id, r.version
            """
        ),
        {"names": list(_NAMED_ROLES)},
    ).mappings().all()

    per_template_latest_hash: dict[str, str] = {}

    for row in rows:
        current_allowlist = row["tool_allowlist"] or []
        if not isinstance(current_allowlist, list):
            current_allowlist = []

        if _has_retrieval_entry(current_allowlist):
            # Idempotent: row already carries the retrieval reference.
            # Track its hash so any subsequent revisions in the same
            # template chain anchor correctly.
            per_template_latest_hash[str(row["role_template_id"])] = row[
                "this_revision_hash"
            ]
            continue

        if current_allowlist:
            # Out of Phase 1 scope: allowlist has non-empty non-retrieval
            # content. Skip rather than corrupt. Phase 1 has no
            # tenant-authored roles; this branch is defensive.
            per_template_latest_hash[str(row["role_template_id"])] = row[
                "this_revision_hash"
            ]
            continue

        new_allowlist = [_RETRIEVAL_ENTRY]

        template_id = str(row["role_template_id"])
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
            WHERE t.name = ANY(:names)
            ORDER BY r.role_template_id, r.version
            """
        ),
        {"names": list(_NAMED_ROLES)},
    ).mappings().all()

    per_template_latest_hash: dict[str, str] = {}

    for row in rows:
        current_allowlist = row["tool_allowlist"] or []
        if not isinstance(current_allowlist, list):
            current_allowlist = []

        if not _has_retrieval_entry(current_allowlist):
            # Idempotent: row already lacks the retrieval reference.
            per_template_latest_hash[str(row["role_template_id"])] = row[
                "this_revision_hash"
            ]
            continue

        new_allowlist = [
            entry
            for entry in current_allowlist
            if not (
                entry.get("tool_id") == _RETRIEVAL_TOOL_ID
                and entry.get("revision_id") == _RETRIEVAL_REVISION_ID
            )
        ]

        template_id = str(row["role_template_id"])
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
