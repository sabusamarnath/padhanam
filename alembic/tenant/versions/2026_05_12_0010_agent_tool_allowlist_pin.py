"""agent_revisions.tool_allowlist tuple-shape pin migration (D89 commit 4)

Revision ID: 0010_agent_tool_allowlist_pin
Revises: 0009_agent_role_lineage
Create Date: 2026-05-12

Per-tenant counterpart to the control-plane
``0010_role_tool_allowlist_pin``. The agent aggregate's
``tool_allowlist`` field migrates from JSONB array of opaque name
strings to the pinned tuple shape (JSONB array of
``{"tool_id": <uuid>, "revision_id": <uuid>}`` dicts) per D89.

Migration behaviour mirrors the control-plane role migration:

- Empty allowlist (``[]``): no-op, hash unchanged.
- ``["retrieval"]``: resolves to the well-known retrieval tool seeded
  at control-plane ``0009_create_tools_tables``. Hash re-anchoring
  applied per D74's chain-self-containment pattern.
- Any other string entry: raises (Phase 1 only knows retrieval).

The current tenant-a state at session-open has the S27b e2e
McKinsey agent with empty allowlist; the migration's recompute path
is unexercised in practice but preserved as defensive
forward-affordance for any future agent revision authored with
``["retrieval"]`` before the commit-8 ``padhanam tool`` CLI lands.

Note: the agent aggregate's ``previous_revision_hash`` content
payload uses the agent context's ``_content_payload`` helper at
``contexts/agent/application/use_cases.py``, which is byte-equivalent
to the role helper's encoding for ``tool_allowlist`` (both sort by
``(tool_id, revision_id)`` and serialise as
``{"tool_id": str, "revision_id": str}`` dicts). The migration
duplicates the helper's encoding inline per the methodology
precedent at S26b's ``0008_create_mckinsey_7_step``.

Downgrade reverses the conversion using the same tools-table name
lookup; the cross-plane lookup opens a separate engine against the
control-plane Postgres because the tools table lives there per D89.
"""
from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from padhanam.security.hash_chain import compute_revision_hash


revision: str = "0010_agent_tool_allowlist_pin"
down_revision: Union[str, None] = "0009_agent_role_lineage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RETRIEVAL_TOOL_ID = "00000000-0000-0000-0000-000000000001"
_RETRIEVAL_REVISION_ID = "00000000-0000-0000-0000-000000000002"


def _resolve_name_to_pin(name: str) -> tuple[str, str]:
    if name == "retrieval":
        return (_RETRIEVAL_TOOL_ID, _RETRIEVAL_REVISION_ID)
    raise ValueError(
        f"unknown tool name {name!r} in agent allowlist; "
        f"only 'retrieval' is platform-managed at Phase 1 per D89"
    )


def _agent_content_payload(
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
    rows = bind.execute(
        sa.text(
            """
            SELECT r.id, r.agent_template_id, r.version, r.system_prompt,
                   r.source_ids, r.tool_allowlist, r.retrieval_strategy,
                   r.filter_tree, r.top_k, r.min_score, r.model_selection,
                   r.previous_revision_hash, r.this_revision_hash,
                   t.name, t.description
            FROM agent_revisions r
            JOIN agent_templates t ON t.id = r.agent_template_id
            ORDER BY r.agent_template_id, r.version
            """
        )
    ).mappings().all()

    per_template_latest_hash: dict[str, str] = {}

    for row in rows:
        old_allowlist = row["tool_allowlist"]
        if not isinstance(old_allowlist, list):
            old_allowlist = []

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
                    f"agent revision {row['id']} has unexpected "
                    f"allowlist entry {entry!r}"
                )

        template_id = str(row["agent_template_id"])

        if template_id in per_template_latest_hash:
            new_prev = per_template_latest_hash[template_id]
        else:
            new_prev = row["previous_revision_hash"]

        new_this_hash = compute_revision_hash(
            content_payload=_agent_content_payload(
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
                UPDATE agent_revisions
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
    """Reverse the conversion using the control-plane tools table.

    Opens a sync sqlalchemy connection against control plane to look
    up the tool name from a tool_id. Pattern mirrors S26a-2's
    ``0009_agent_role_lineage`` cross-plane backfill.
    """
    from padhanam.config import ControlPlaneSettings

    cp = ControlPlaneSettings()
    cp_url = (
        f"postgresql+psycopg://{cp.user}:{cp.password}@{cp.host}:{cp.port}/{cp.db}"
    )
    cp_engine = sa.create_engine(cp_url)

    def lookup_tool_name(tool_id: str) -> str:
        if tool_id == _RETRIEVAL_TOOL_ID:
            return "retrieval"
        with cp_engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT name FROM tools WHERE id = :tid"),
                {"tid": tool_id},
            ).first()
            if row is None:
                raise ValueError(
                    f"tool id {tool_id!r} not found in control-plane tools"
                )
            return row[0]

    try:
        bind = op.get_bind()
        rows = bind.execute(
            sa.text(
                """
                SELECT r.id, r.agent_template_id, r.version, r.system_prompt,
                       r.source_ids, r.tool_allowlist, r.retrieval_strategy,
                       r.filter_tree, r.top_k, r.min_score, r.model_selection,
                       r.previous_revision_hash, r.this_revision_hash,
                       t.name, t.description
                FROM agent_revisions r
                JOIN agent_templates t ON t.id = r.agent_template_id
                ORDER BY r.agent_template_id, r.version
                """
            )
        ).mappings().all()

        per_template_latest_hash: dict[str, str] = {}

        for row in rows:
            new_allowlist = row["tool_allowlist"]
            if not isinstance(new_allowlist, list):
                new_allowlist = []

            if new_allowlist and isinstance(new_allowlist[0], str):
                continue

            old_allowlist = []
            for entry in new_allowlist:
                if isinstance(entry, dict):
                    old_allowlist.append(lookup_tool_name(entry["tool_id"]))
                elif isinstance(entry, str):
                    old_allowlist.append(entry)
                else:
                    raise ValueError(
                        f"agent revision {row['id']} has unexpected "
                        f"allowlist entry {entry!r}"
                    )

            template_id = str(row["agent_template_id"])

            if template_id in per_template_latest_hash:
                new_prev = per_template_latest_hash[template_id]
            else:
                new_prev = row["previous_revision_hash"]

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
                    UPDATE agent_revisions
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
    finally:
        cp_engine.dispose()
