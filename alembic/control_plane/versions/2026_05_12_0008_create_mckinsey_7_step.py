"""create McKinsey 7-Step methodology with seven role aggregates

Revision ID: 0008_create_mckinsey_7_step
Revises: 0007_lvt_split
Create Date: 2026-05-12

Data-only migration per S26b. Authors the McKinsey 7-Step methodology
and its seven first-class role aggregates against D86's role-first
model and D87's structured per-field overrides shape.

Eight new rows on control-plane Postgres:

- seven ``role_templates`` rows: ProblemFramer, Disaggregator,
  Prioritiser, Planner, Analyst, Synthesiser, Communicator.
- seven ``role_revisions`` rows at ``version = 1`` each, chained from
  the genesis sentinel ``"0" * 64``.
- one ``methodology_templates`` row: McKinsey 7-Step.
- one ``methodology_revisions`` row at ``version = 1`` with
  ``role_refs`` JSONB referencing the seven role templates in the
  brief's sequential order, each entry carrying an augment-mode
  ``system_prompt`` override matching the brief's overrides table
  verbatim.

The role bundles use the substrate-mapped values from S26b's
pre-write reconciliation:

- ``source_ids = []`` (roles are platform-managed on control plane;
  source_ids are tenant-scoped UUIDs by design).
- ``tool_allowlist = []`` (no tool registry exists at Phase 1; S28b
  ships it. The brief's "may expand to data-gathering tools" and
  "may expand to document generation tools" wording for Analyst and
  Communicator defer to a methodology revision after S28b).
- ``retrieval_strategy = {"strategy": "parallel_rrf", "params": {}}``
  (D66's catalogue's hybrid entry; closest match to the brief's
  "vector primary, graph secondary" intent. Cascade variants defer
  per D66 until retrieval evaluation surfaces a need).
- ``filter_tree = {"node": {}}`` (the empty-tree representation per
  D67; matches the LVT methodology's empty-tree shape).
- ``top_k = 8`` (verbatim from the brief).
- ``min_score = Decimal("0.5")`` (verbatim from the brief).
- ``model_selection = "qwen2.5:7b"`` (matches LVT's dev default
  consistent with the live stack; the brief's "default (LiteLLM-
  routed)" wording maps to the dev environment default).

Hashes computed via ``padhanam.security.hash_chain.compute_revision_hash``
imported directly per S26a-1's promotion-of-the-helper convention.
The canonical-JSON encoding (sorted keys, format-f Decimal,
UUID-to-str) matches the use case layer exactly so the chain
integrity check against the migration's content is byte-equivalent
to a create-via-use-case flow.

Per D87, the methodology revision's ``role_refs`` JSONB carries
``overrides`` as the structured ``{<field>: {"mode", "value"}}``
shape. Empty overrides would canonicalise to ``null``; the McKinsey
methodology's seven role_refs each carry one populated override key
(``system_prompt`` with mode ``augment``).

Idempotency: the migration guards on the methodology name. If the
McKinsey 7-Step row already exists, the migration is a no-op.

Downgrade: drops the eight rows by the migration's
``created_by_user_id`` sentinel (``migration:0008_create_mckinsey_7_step``)
so post-migration roles or methodologies authored by other actors
remain intact. The downgrade is the audit recovery path, not a
routine operation.

Out of scope:
- AgentExecutor port / AgentLoopExecutor adapter (S27b).
- Tool registry context (S28b); ``tool_allowlist`` stays empty here.
- Workflow runtime (Phase 2 per D83); the methodology's role_refs
  ordering is structurally sequential but not runtime-executed.
- Skills aggregate (Phase 2 per D86 sub-commitment (d)).
- Resolver semantics for override modes (S27b per D87).
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


revision: str = "0008_create_mckinsey_7_step"
down_revision: Union[str, None] = "0007_lvt_split"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MIGRATION_ACTOR = "migration:0008_create_mckinsey_7_step"
_METHODOLOGY_NAME = "McKinsey 7-Step"
_METHODOLOGY_DESCRIPTION = (
    "Structured approach to problem-solving across seven sequential steps. "
    "Suited for complex business problems requiring rigorous decomposition, "
    "prioritisation, and synthesis. Originated in McKinsey publications "
    "including Bulletproof Problem Solving."
)


# Per-role content. Each entry is the role authored as a standalone
# first-class aggregate per D86; the system_prompt is function-focused
# (what the role does, what inputs and outputs, what responsibilities)
# without procedural content per D86 sub-commitment (e). The McKinsey
# 7-Step specialisation lives in the methodology's role_refs overrides.
_ROLE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "ProblemFramer",
        "description": (
            "Frames problems for structured analysis. Produces a sharpened "
            "problem statement with explicit scope, situation, complication, "
            "and success criteria for downstream decomposition."
        ),
        "system_prompt": (
            "You frame problems for structured analysis. Your job: receive a "
            "raw problem statement or topic from the user; produce a sharpened "
            "problem statement with explicit scope (what is in and out), "
            "context (situation), complication (what makes this hard or "
            "urgent), and success criteria (what good looks like). You hand "
            "the sharpened problem to the Disaggregator role for "
            "decomposition. You do not analyse the problem yourself; you "
            "frame it."
        ),
    },
    {
        "name": "Disaggregator",
        "description": (
            "Decomposes a framed problem into structured component trees "
            "where each branch represents a distinct sub-problem and the "
            "branches together are collectively exhaustive."
        ),
        "system_prompt": (
            "You decompose problems into structured component trees. Your "
            "job: receive a sharpened problem from the ProblemFramer; produce "
            "a structured decomposition where each branch represents a "
            "distinct sub-problem and branches together are collectively "
            "exhaustive. The decomposition is the input the Prioritiser uses "
            "to rank tractability. You do not solve sub-problems; you "
            "structure them."
        ),
    },
    {
        "name": "Prioritiser",
        "description": (
            "Ranks decomposition branches by impact and tractability to "
            "identify the highest-value sub-problems for workplan "
            "construction."
        ),
        "system_prompt": (
            "You prioritise sub-problems from a decomposition tree. Your job: "
            "receive the issue tree from the Disaggregator; score each branch "
            "on impact (how much resolving this moves the overall problem) "
            "and tractability (how feasible resolving this is in available "
            "time and resources); produce a ranked list with the top branches "
            "flagged as priorities. The ranking feeds the Planner role for "
            "workplan construction. You do not solve sub-problems; you order "
            "them."
        ),
    },
    {
        "name": "Planner",
        "description": (
            "Produces a workplan covering prioritised sub-problems with "
            "deliverables, owners, deadlines, and analyses to be run."
        ),
        "system_prompt": (
            "You produce workplans for prioritised sub-problems. Your job: "
            "receive the prioritised list from the Prioritiser; for each "
            "priority branch, specify the analyses to be run, the data "
            "needed, the owners, the deliverables, and the deadlines. The "
            "workplan feeds the Analyst role for execution. You do not run "
            "analyses; you plan them."
        ),
    },
    {
        "name": "Analyst",
        "description": (
            "Executes a workplan: gathers data, runs analyses, produces "
            "evidence-backed findings."
        ),
        "system_prompt": (
            "You execute analyses per a workplan. Your job: receive the "
            "workplan from the Planner; conduct the specified analyses; "
            "gather and structure the data needed; produce findings backed "
            "by evidence (data sources, citations, observable indicators); "
            "pass findings to the Synthesiser role. You produce one finding "
            "per workplan item with explicit evidence."
        ),
    },
    {
        "name": "Synthesiser",
        "description": (
            "Integrates findings into a coherent storyline addressing the "
            "original problem framing."
        ),
        "system_prompt": (
            "You synthesise findings into integrated storylines. Your job: "
            "receive the set of findings from the Analyst; identify the "
            "storyline that addresses the original problem from the "
            "ProblemFramer's framing; integrate findings into a coherent "
            "narrative with explicit logical flow; pass the storyline to the "
            "Communicator. You do not produce new analyses; you integrate "
            "existing ones."
        ),
    },
    {
        "name": "Communicator",
        "description": (
            "Produces audience-appropriate communication of the synthesised "
            "storyline calibrated to the user's stated audience and channel."
        ),
        "system_prompt": (
            "You communicate problem-solving outcomes to audiences. Your "
            "job: receive the storyline from the Synthesiser; produce "
            "audience-appropriate communication (executive summary, detailed "
            "report, presentation outline, or narrative) calibrated to the "
            "user's stated audience and channel. You do not change the "
            "storyline's substance; you express it appropriately."
        ),
    },
]


# Per-role overrides from the brief's overrides table. Each entry is a
# system_prompt addition under mode "augment" per D87 (the per-field
# default mode for system_prompt). The brief's "other" column is "none"
# for all seven entries; the migration omits those keys from each
# role_ref's overrides.
_ROLE_OVERRIDES: dict[str, str] = {
    "ProblemFramer": (
        "Apply the SCQ framework (Situation, Complication, Question) when "
        "framing"
    ),
    "Disaggregator": (
        "Apply MECE (Mutually Exclusive, Collectively Exhaustive) "
        "decomposition; produce an issue tree"
    ),
    "Prioritiser": (
        "Use impact-tractability matrix; flag the top quartile as priorities"
    ),
    "Planner": (
        "Workplan structure: hypothesis, analyses, data needed, owner, "
        "deadline, deliverable"
    ),
    "Analyst": (
        "Findings include data, source citations, confidence level"
    ),
    "Synthesiser": (
        "Apply pyramid principle to storyline construction"
    ),
    "Communicator": (
        "Default communication style is structured prose with executive "
        "summary"
    ),
}


# Substrate-mapped role-bundle defaults shared across all seven roles
# per S26b's pre-write reconciliation. See the module docstring for
# the per-field rationale.
_ROLE_BUNDLE_DEFAULTS = {
    "source_ids": [],
    "tool_allowlist": [],
    "retrieval_strategy": {"strategy": "parallel_rrf", "params": {}},
    "filter_tree": {"node": {}},
    "top_k": 8,
    "min_score": Decimal("0.5"),
    "model_selection": "qwen2.5:7b",
}


def _role_content_payload(
    *,
    name: str,
    description: str,
    system_prompt: str,
) -> dict[str, Any]:
    """Mirror of contexts/methodology/application/use_cases.py:_role_content_payload.

    Kept inline so the migration is self-contained; the structural
    shape is what matters for byte-equivalent hashes. If the
    application helper drifts from this shape, the integration test's
    golden-hash assertion at S26b commit 4 surfaces the drift.
    """
    return {
        "name": name,
        "description": description or "",
        "system_prompt": system_prompt,
        "source_ids": sorted(str(s) for s in _ROLE_BUNDLE_DEFAULTS["source_ids"]),
        "tool_allowlist": sorted(
            str(t) for t in _ROLE_BUNDLE_DEFAULTS["tool_allowlist"]
        ),
        "retrieval_strategy": dict(_ROLE_BUNDLE_DEFAULTS["retrieval_strategy"]),
        "filter_tree": dict(_ROLE_BUNDLE_DEFAULTS["filter_tree"]),
        "top_k": _ROLE_BUNDLE_DEFAULTS["top_k"],
        "min_score": _ROLE_BUNDLE_DEFAULTS["min_score"],
        "model_selection": _ROLE_BUNDLE_DEFAULTS["model_selection"],
    }


def _methodology_content_payload(
    *,
    name: str,
    description: str,
    role_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Mirror of the post-D87 use_cases._content_payload for methodology hashes.

    Each role_ref's ``overrides`` is the D87 structured shape
    (``{<field>: {"mode", "value"}}``); empty overrides canonicalise
    to ``None`` for byte-stability with the LVT methodology authored
    pre-D87. McKinsey's seven role_refs each carry populated overrides
    so the canonical form preserves the dict verbatim.
    """
    canonical_refs = [
        {
            "role_id": str(r["role_id"]),
            "role_version": r["role_version"],
            "overrides": (
                None if not r.get("overrides") else dict(r["overrides"])
            ),
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
    bind = op.get_bind()

    # Idempotency guard: if McKinsey 7-Step already exists, no-op.
    existing = bind.execute(
        sa.text(
            "SELECT id FROM methodology_templates WHERE name = :name LIMIT 1"
        ),
        {"name": _METHODOLOGY_NAME},
    ).first()
    if existing is not None:
        return

    now = sa.func.now()

    # --------------------------------------------------------------
    # Step 1: insert seven role_templates plus seven role_revisions.
    # --------------------------------------------------------------
    role_ids_by_name: dict[str, str] = {}
    for role_def in _ROLE_DEFINITIONS:
        role_template_id = str(uuid4())
        role_ids_by_name[role_def["name"]] = role_template_id

        bind.execute(
            sa.text(
                """
                INSERT INTO role_templates
                    (id, name, description, created_by_user_id, created_at)
                VALUES
                    (:id, :name, :description, :created_by_user_id, NOW())
                """
            ),
            {
                "id": role_template_id,
                "name": role_def["name"],
                "description": role_def["description"],
                "created_by_user_id": _MIGRATION_ACTOR,
            },
        )

        role_payload = _role_content_payload(
            name=role_def["name"],
            description=role_def["description"],
            system_prompt=role_def["system_prompt"],
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
                    (:id, :role_template_id, 1, :system_prompt,
                     CAST(:source_ids AS jsonb),
                     CAST(:tool_allowlist AS jsonb),
                     CAST(:retrieval_strategy AS jsonb),
                     CAST(:filter_tree AS jsonb),
                     :top_k, :min_score, :model_selection,
                     :created_by_user_id, NOW(),
                     :previous_revision_hash, :this_revision_hash)
                """
            ),
            {
                "id": str(uuid4()),
                "role_template_id": role_template_id,
                "system_prompt": role_def["system_prompt"],
                "source_ids": json.dumps(_ROLE_BUNDLE_DEFAULTS["source_ids"]),
                "tool_allowlist": json.dumps(
                    _ROLE_BUNDLE_DEFAULTS["tool_allowlist"]
                ),
                "retrieval_strategy": json.dumps(
                    _ROLE_BUNDLE_DEFAULTS["retrieval_strategy"]
                ),
                "filter_tree": json.dumps(_ROLE_BUNDLE_DEFAULTS["filter_tree"]),
                "top_k": _ROLE_BUNDLE_DEFAULTS["top_k"],
                "min_score": _ROLE_BUNDLE_DEFAULTS["min_score"],
                "model_selection": _ROLE_BUNDLE_DEFAULTS["model_selection"],
                "created_by_user_id": _MIGRATION_ACTOR,
                "previous_revision_hash": GENESIS_REVISION_HASH,
                "this_revision_hash": role_hash,
            },
        )

    # --------------------------------------------------------------
    # Step 2: insert the McKinsey 7-Step methodology template plus
    # revision 1. ``role_refs`` JSONB preserves the brief's sequential
    # order (ProblemFramer ... Communicator); the canonical hash
    # payload sorts by role_id internally for determinism.
    # --------------------------------------------------------------
    methodology_template_id = str(uuid4())

    bind.execute(
        sa.text(
            """
            INSERT INTO methodology_templates
                (id, name, description, created_by_user_id, created_at)
            VALUES
                (:id, :name, :description, :created_by_user_id, NOW())
            """
        ),
        {
            "id": methodology_template_id,
            "name": _METHODOLOGY_NAME,
            "description": _METHODOLOGY_DESCRIPTION,
            "created_by_user_id": _MIGRATION_ACTOR,
        },
    )

    role_refs_storage: list[dict[str, Any]] = []
    for role_def in _ROLE_DEFINITIONS:
        addition = _ROLE_OVERRIDES[role_def["name"]]
        role_refs_storage.append(
            {
                "role_id": role_ids_by_name[role_def["name"]],
                "role_version": 1,
                "overrides": {
                    "system_prompt": {"mode": "augment", "value": addition},
                },
            }
        )

    methodology_payload = _methodology_content_payload(
        name=_METHODOLOGY_NAME,
        description=_METHODOLOGY_DESCRIPTION,
        role_refs=role_refs_storage,
    )
    methodology_hash = compute_revision_hash(
        content_payload=methodology_payload,
        previous_hash=GENESIS_REVISION_HASH,
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO methodology_revisions
                (id, methodology_template_id, version, role_refs,
                 created_by_user_id, created_at,
                 previous_revision_hash, this_revision_hash)
            VALUES
                (:id, :methodology_template_id, 1,
                 CAST(:role_refs AS jsonb),
                 :created_by_user_id, NOW(),
                 :previous_revision_hash, :this_revision_hash)
            """
        ),
        {
            "id": str(uuid4()),
            "methodology_template_id": methodology_template_id,
            "role_refs": json.dumps(role_refs_storage),
            "created_by_user_id": _MIGRATION_ACTOR,
            "previous_revision_hash": GENESIS_REVISION_HASH,
            "this_revision_hash": methodology_hash,
        },
    )


def downgrade() -> None:
    """Drop the eight rows by the migration's actor sentinel.

    Roles or methodologies authored by other actors after this
    migration ran remain untouched.
    """
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            DELETE FROM methodology_revisions
            WHERE created_by_user_id = :actor
            """
        ),
        {"actor": _MIGRATION_ACTOR},
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM methodology_templates
            WHERE created_by_user_id = :actor
            """
        ),
        {"actor": _MIGRATION_ACTOR},
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM role_revisions
            WHERE created_by_user_id = :actor
            """
        ),
        {"actor": _MIGRATION_ACTOR},
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM role_templates
            WHERE created_by_user_id = :actor
            """
        ),
        {"actor": _MIGRATION_ACTOR},
    )
