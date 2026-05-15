"""re-seed LVTGuide role with retrieval allowlist pinned (S39b)

Revision ID: 0013_lvtguide_reseed
Revises: 0012_role_allowlist_retrieval
Create Date: 2026-05-15

Closes the S30b fixture-leak carryover that S39's smoke surfaced again:
the test-fixture leak documented at `log/captures.md:2026-05-13 [S30b]`
wiped methodology and role rows from the control plane before the
filter-fix landed; the seven McKinsey 7-Step roles survived (their
`migration:0008_create_mckinsey_7_step` actor matches the filter
exception), but LVTGuide did not. S39's smoke documented this as a
carryover; S39b's commit 3 lands the fix.

Idempotent INSERT of the LVTGuide row plus role_revisions row at
version 1, with `tool_allowlist` pinned to the retrieval tool
reference at insertion time. The pin shape matches the post-0010-and-
0012 state (the seven McKinsey roles' current `tool_allowlist`
value), so LVTGuide enters the DB in the same shape as the seven
roles would have post-S39 commit 2.

LVT system prompt and defaults lifted verbatim from briefs/p7/s25.md
(the S25 brief is the authoritative source for the pre-wipe LVT
methodology content per the S25 close at `log/sessions.md`). One
mechanical drift between the brief and current naming: the brief
specifies `retrieval_strategy: {strategy: hybrid, params: {}}` and
cites D66, but D66's actual strategy registry names this strategy
`parallel_rrf` (vector + graph in parallel via Reciprocal Rank
Fusion). The substantive intent (hybrid retrieval engaging both
stores) is preserved; the strategy-name value uses D66's canonical
`parallel_rrf` for byte-equivalent compatibility with the McKinsey
seven roles and the rest of the post-D66 platform.

`created_by_user_id = 'migration:0013_lvtguide_reseed'` preserves
provenance symmetry with the seven McKinsey roles
(`migration:0008_create_mckinsey_7_step`) so the audit shape at P12
shows all eight platform-managed roles with migration-actor
provenance.

Hash recomputation uses `padhanam.security.hash_chain.compute_revision_hash`
(the field-set-agnostic platform primitive promoted at S24 per D75)
with the canonical content payload mirroring migration 0010's
`_role_content_payload` shape (so the byte-encoding matches the
McKinsey roles' post-0012 hash basis exactly).

No downgrade path. Forward-only per the project's migration
discipline; if a downgrade is ever required for audit-recovery
reasons, a future migration writes a `0014_lvtguide_downgrade` rather
than reversing in place.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Sequence, Union
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa

from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)


revision: str = "0013_lvtguide_reseed"
down_revision: Union[str, None] = "0012_role_allowlist_retrieval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Well-known retrieval tool reference (seeded at 0009_create_tools_tables).
_RETRIEVAL_TOOL_ID = "00000000-0000-0000-0000-000000000001"
_RETRIEVAL_REVISION_ID = "00000000-0000-0000-0000-000000000002"

_ROLE_NAME = "LVTGuide"

_ROLE_DESCRIPTION = (
    "Lean Value Tree methodology assistant: locates work in the "
    "bet→initiative→epic→story hierarchy, checks alignment "
    "upward and decomposition downward, surfaces drift between strategic "
    "intent and execution."
)

# Verbatim from briefs/p7/s25.md lines 84-105.
_ROLE_SYSTEM_PROMPT = (
    "You are an LVT (Lean Value Tree) methodology assistant. LVT structures "
    "product strategy as a four-level hierarchy: bet, initiative, epic, "
    "story. Each level cascades strategic intent downward and aggregates "
    "evidence upward.\n"
    "\n"
    "Your role is to help users place work in the right level of the tree, "
    "identify when a level is misaligned with the level above, and surface "
    "drift between strategic intent and execution.\n"
    "\n"
    "When a user describes work, locate it in the tree first.\n"
    "\n"
    "A bet is a load-bearing strategic claim with named test conditions and "
    "falsifiable success criteria. Bets answer \"what proposition are we "
    "testing in the market?\"\n"
    "\n"
    "An initiative is a coherent body of work aligned with one bet's "
    "success criteria. Initiatives answer \"what concrete arc do we ship to "
    "test the bet?\"\n"
    "\n"
    "An epic is a shippable scope within an initiative that produces "
    "measurable outcomes. Epics answer \"what ships, and how do we know it "
    "worked?\"\n"
    "\n"
    "A story is the smallest unit of value within an epic. Stories answer "
    "\"what does the team do this week?\"\n"
    "\n"
    "When asked to assess work, locate it first, then check alignment "
    "upward (does this epic actually serve its initiative? does this "
    "initiative actually test its bet?) and decomposition downward (does "
    "this initiative break into shippable epics? do the stories aggregate "
    "to the epic's outcomes?).\n"
    "\n"
    "Push back on weak placements. A bet without falsifiable success "
    "criteria is a vision statement. An initiative without measurable "
    "outcomes is a roadmap header. An epic without shippable scope is a "
    "wish. A story without acceptance criteria is a task.\n"
    "\n"
    "Use the source materials attached to this agent for the user's "
    "specific bet, initiatives, epics, and stories. Cite specific source "
    "content when grounding assessments. When source materials contradict "
    "each other, surface the contradiction rather than papering over it.\n"
    "\n"
    "Your output is recommendation-shaped: name the placement, name the "
    "alignment status, name the gap, recommend a next step. End with a "
    "position, not a menu."
)

# LVT-specific defaults from briefs/p7/s25.md lines 109-115.
# retrieval_strategy: brief said "hybrid" citing D66; D66's actual registry
# names this strategy "parallel_rrf". Using D66's canonical name (see
# module docstring's "mechanical drift" note).
_RETRIEVAL_STRATEGY: dict[str, Any] = {
    "strategy": "parallel_rrf",
    "params": {},
}
_FILTER_TREE: dict[str, Any] = {"node": {}}
_TOP_K: int = 8
# Min score 0.3 lifted verbatim from S25 brief (LVT-specific, divergent
# from the McKinsey platform default of 0.5; the LVT methodology used 0.3
# at create time per the brief's bundle).
_MIN_SCORE: Decimal = Decimal("0.3")
_MODEL_SELECTION: str = "qwen2.5:7b"

_TOOL_ALLOWLIST: list[dict[str, str]] = [
    {"tool_id": _RETRIEVAL_TOOL_ID, "revision_id": _RETRIEVAL_REVISION_ID},
]

_MIGRATION_ACTOR = "migration:0013_lvtguide_reseed"


def _role_content_payload(
    *,
    name: str,
    description: str,
    system_prompt: str,
    source_ids: list[str],
    tool_allowlist: list[dict[str, str]],
    retrieval_strategy: dict[str, Any],
    filter_tree: dict[str, Any],
    top_k: int,
    min_score: Decimal,
    model_selection: str,
) -> dict[str, Any]:
    """Mirror of `0010_role_tool_allowlist_pin._role_content_payload`.

    Tuple-shape `tool_allowlist` entries sort by (tool_id, revision_id)
    so the canonical encoding is byte-stable; matches the
    application-layer helper at `contexts.methodology.application.use_cases`
    and the post-0010 / post-0012 hash basis used by the seven McKinsey
    roles.
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
        "min_score": min_score,
        "model_selection": model_selection,
    }


def upgrade() -> None:
    bind = op.get_bind()

    # Idempotency guard: if LVTGuide already exists, no-op.
    existing = bind.execute(
        sa.text(
            "SELECT id FROM role_templates WHERE name = :name LIMIT 1"
        ),
        {"name": _ROLE_NAME},
    ).first()
    if existing is not None:
        return

    template_id = uuid4()
    revision_id = uuid4()

    bind.execute(
        sa.text(
            """
            INSERT INTO role_templates
                (id, name, description, created_by_user_id, created_at,
                 archived_at)
            VALUES
                (:id, :name, :description, :actor, now(), NULL)
            """
        ),
        {
            "id": str(template_id),
            "name": _ROLE_NAME,
            "description": _ROLE_DESCRIPTION,
            "actor": _MIGRATION_ACTOR,
        },
    )

    content_payload = _role_content_payload(
        name=_ROLE_NAME,
        description=_ROLE_DESCRIPTION,
        system_prompt=_ROLE_SYSTEM_PROMPT,
        source_ids=[],
        tool_allowlist=_TOOL_ALLOWLIST,
        retrieval_strategy=_RETRIEVAL_STRATEGY,
        filter_tree=_FILTER_TREE,
        top_k=_TOP_K,
        min_score=_MIN_SCORE,
        model_selection=_MODEL_SELECTION,
    )
    this_revision_hash = compute_revision_hash(
        content_payload=content_payload,
        previous_hash=GENESIS_REVISION_HASH,
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO role_revisions
                (id, role_template_id, version, system_prompt, source_ids,
                 tool_allowlist, retrieval_strategy, filter_tree, top_k,
                 min_score, model_selection, created_by_user_id, created_at,
                 previous_revision_hash, this_revision_hash)
            VALUES
                (:id, :template_id, 1, :system_prompt,
                 CAST(:source_ids AS jsonb),
                 CAST(:tool_allowlist AS jsonb),
                 CAST(:retrieval_strategy AS jsonb),
                 CAST(:filter_tree AS jsonb),
                 :top_k, :min_score, :model_selection,
                 :actor, now(), :prev, :this)
            """
        ),
        {
            "id": str(revision_id),
            "template_id": str(template_id),
            "system_prompt": _ROLE_SYSTEM_PROMPT,
            "source_ids": json.dumps([]),
            "tool_allowlist": json.dumps(_TOOL_ALLOWLIST, sort_keys=True),
            "retrieval_strategy": json.dumps(
                _RETRIEVAL_STRATEGY, sort_keys=True
            ),
            "filter_tree": json.dumps(_FILTER_TREE, sort_keys=True),
            "top_k": _TOP_K,
            "min_score": _MIN_SCORE,
            "model_selection": _MODEL_SELECTION,
            "actor": _MIGRATION_ACTOR,
            "prev": GENESIS_REVISION_HASH,
            "this": this_revision_hash,
        },
    )


def downgrade() -> None:
    # Forward-only per project discipline; downgrade stub allows the
    # alembic CLI to invoke it without erroring but production
    # operation never exercises this path.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM role_revisions WHERE role_template_id IN ("
            "SELECT id FROM role_templates WHERE name = :name "
            "AND created_by_user_id = :actor)"
        ),
        {"name": _ROLE_NAME, "actor": _MIGRATION_ACTOR},
    )
    bind.execute(
        sa.text(
            "DELETE FROM role_templates "
            "WHERE name = :name AND created_by_user_id = :actor"
        ),
        {"name": _ROLE_NAME, "actor": _MIGRATION_ACTOR},
    )
