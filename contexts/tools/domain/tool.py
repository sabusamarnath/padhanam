"""Tool and ToolRevision aggregates (D89).

Two frozen dataclasses inheriting D74's revision-shape precedent from
``MethodologyTemplate`` / ``MethodologyRevision`` and S26a-1's
``RoleTemplate`` / ``RoleRevision``. The tool aggregate lives in its
own bounded context at ``contexts/tools/`` per D68 and the P8 epic
line; co-location with methodology was rejected because tools have a
distinct evolution velocity (classification taxonomy, BC stub,
invariant enforcement) that warrants its own context.

Per D74's chain-self-containment reasoning, the parent template's
``name``, ``description``, and ``classification`` appear in the hash
content payload at hash-compute time even though only the
classification is persisted alongside the template (name and
description are too). Chain integrity verification reconstructs the
payload by reading the parent template's metadata and the revision's
persisted content fields. The canonical-JSON pattern mirrors D74 /
D75 exactly so the hash-chain primitive at
``padhanam/security/hash_chain.py`` handles tool chains without
modification.

Classification is on the template, not the revision, per D89's
"classification is a property of what the tool does" reasoning
(alternative (g) in the D-entry). Reclassifying a tool mid-revision
would semantically be a different tool. The template owns
classification; revisions evolve the parameters and returns schemas.

The ``ToolDefinition`` value object is the consumer-side surface for
the agent runtime: it carries what an LLM needs to know about a tool
(name, description, parameters schema) plus the returns schema used
by BC checks and future result validation. The inference context's
``ToolDefinition`` (at ``contexts/inference/domain/completion.py``)
is a strict subset; the wiring adapter at
``apps/cli/_cross_context.py`` translates between the two shapes.

Domain code is framework-free per D16 — stdlib dataclasses, no
Pydantic, no SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping
from uuid import UUID


class Classification(str, Enum):
    """Tool classification taxonomy (D89).

    Six categories. Three map to D82 invariants 1-3 at the invocation
    boundary (financial, communication, legal). The other three govern
    via standing consent at tool configuration per D14:

    - ``READ_ONLY``: pure information retrieval; no user-visible side
      effects. Retrieval is the canonical Phase 1 example.
    - ``DRAFTING``: produces content for the user to act on; no
      external action. The drafted-artifact-as-deliverable shape per
      the S28b conversation framing of Padhanam-as-intelligence-layer.
    - ``USER_AFFECTING_WITH_CONSENT``: modifies user-controlled
      surfaces (e.g., the tenant's own data plane) under the standing
      consent the user gave at tool configuration. Reversible by the
      user.
    - ``FINANCIAL``: maps to invariant 1 (per-transaction
      authorization). Per-invocation confirmation required. Phase 1
      authoring prohibited per D89.
    - ``COMMUNICATION``: maps to invariant 2 (per-invocation
      authorization, outbound). Per-send confirmation required.
      Phase 1 authoring prohibited per D89.
    - ``LEGAL``: maps to invariant 3 (explicit user action). Deliberate
      user action required. Phase 1 authoring prohibited per D89.

    String values are stable wire identifiers (slug shape). Schema
    CHECK constraints reference these values verbatim.
    """

    READ_ONLY = "read-only"
    DRAFTING = "drafting"
    USER_AFFECTING_WITH_CONSENT = "user-affecting-with-consent"
    FINANCIAL = "financial"
    COMMUNICATION = "communication"
    LEGAL = "legal"


# Phase 1 authoring prohibition per D89. The CLI's ``padhanam tool create``
# rejects tools authored against these classifications with a
# ``ClassificationProhibitedError`` naming the per-invocation
# confirmation pathway deferred-decisions entry. The prohibition lifts
# when that pathway lands.
PHASE_1_PROHIBITED_CLASSIFICATIONS: frozenset[Classification] = frozenset(
    {
        Classification.FINANCIAL,
        Classification.COMMUNICATION,
        Classification.LEGAL,
    }
)


# Phase 1 visible classifications: the LLM only sees tools whose
# classification is in this set. The ``ToolDefinitionsLookup`` adapter
# enforces this filter when assembling the per-invocation tool list.
# Defensive enforcement also runs at the invocation boundary in the
# ``ToolInvoker`` so a bypass yields a structured
# ``INVARIANT_BLOCKED`` termination rather than an unaudited call.
PHASE_1_VISIBLE_CLASSIFICATIONS: frozenset[Classification] = frozenset(
    {
        Classification.READ_ONLY,
        Classification.DRAFTING,
        Classification.USER_AFFECTING_WITH_CONSENT,
    }
)


@dataclass(frozen=True)
class Tool:
    """Tool template aggregate (D89).

    Immutable identity for a tool. Retirement marks ``archived_at``
    while leaving revisions intact for existing role-references per
    D31's append-only-at-version-level discipline. Roles reference
    tools by id (with version pinning at the revision level) via
    ``tool_allowlist`` (commit 4 migrates that field to the pinned
    shape).

    ``classification`` lives on the template per D89 alternative (g):
    classification is a property of what the tool does, not what role
    uses it. Reclassifying mid-revision would semantically be a
    different tool.
    """

    id: UUID
    name: str
    description: str | None
    classification: Classification
    created_by_user_id: str
    created_at: datetime
    archived_at: datetime | None = None


@dataclass(frozen=True)
class ToolRevision:
    """Tool revision aggregate (D89).

    Immutable per D31. ``previous_revision_hash`` chains forward from
    the genesis sentinel (``GENESIS_REVISION_HASH``) per tool;
    ``this_revision_hash`` is the SHA-256 of the canonical-JSON content
    payload (including the parent template's name, description, and
    classification plus the previous hash as a payload key) per D26
    inheriting the audit-mirror shape from D74 / S23.

    ``parameters_schema`` and ``returns_schema`` are JSON-schema
    payloads describing the tool's call and result shapes; the domain
    treats them as opaque dicts (matching the convention for
    ``retrieval_strategy`` and ``filter_tree`` on role revisions).
    The BC stub at commit 6 reads both to compute the
    revision-Rn-vs-Rn+1 compatibility result.

    ``bc_result`` is JSONB metadata populated by ``create_tool_revision``
    at commit 6 (forward-affordance column at commit 2's migration).
    Empty dict at commit 2 / 3; commit 6 stores the schema-diff
    outcome here. The field surfaces on the revision so the query
    surface ``list_roles_using_tool`` can compute ``can_auto_adopt``
    without recomputing BC.
    """

    id: UUID
    tool_id: UUID
    version: int
    parameters_schema: Mapping[str, Any]
    returns_schema: Mapping[str, Any]
    bc_result: Mapping[str, Any]
    created_by_user_id: str
    created_at: datetime
    previous_revision_hash: str
    this_revision_hash: str


@dataclass(frozen=True)
class ToolDefinition:
    """Outbound consumer-side description of a tool (D89).

    Carries what the agent runtime needs to surface a tool to an LLM
    plus what the BC layer and future result validators need. The
    inference context's ``ToolDefinition`` (at
    ``contexts/inference/domain/completion.py``) is a strict subset
    (name, description, parameters_schema) — the wiring adapter at
    ``apps/cli/_cross_context.py`` performs the translation.

    Classification is included so the ``ToolDefinitionsLookup`` adapter
    can filter the visible-tools list by ``PHASE_1_VISIBLE_CLASSIFICATIONS``
    without re-fetching the parent ``Tool`` template.
    """

    tool_id: UUID
    revision_id: UUID
    name: str
    description: str
    classification: Classification
    parameters_schema: Mapping[str, Any]
    returns_schema: Mapping[str, Any]


__all__ = [
    "Classification",
    "PHASE_1_PROHIBITED_CLASSIFICATIONS",
    "PHASE_1_VISIBLE_CLASSIFICATIONS",
    "Tool",
    "ToolDefinition",
    "ToolRevision",
]
