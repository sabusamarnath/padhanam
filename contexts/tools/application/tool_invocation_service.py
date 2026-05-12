"""Tool invocation service (D89).

The application-layer surface the agent context's two thin ports
(``ToolDefinitionsLookup``, ``ToolInvoker``) consume via the wiring
adapters at ``apps/cli/_cross_context.py`` (commit 7). The service
splits its responsibility along the same read/action seam:

- ``list_visible_definitions``: takes a sequence of tool revision
  references (tool_id, revision_id) and returns the
  ``ToolDefinition`` view for each tool whose classification is in
  ``PHASE_1_VISIBLE_CLASSIFICATIONS``. The wiring adapter for
  ``ToolDefinitionsLookup`` passes the role's allowlist entries here.

- ``check_invocation_admissibility``: defensive invariant check at
  the invocation boundary per D89. Reads the named tool revision,
  inspects classification, returns an ``InvocationAdmissibility``
  carrying the outcome and (when blocked by a high-classification
  invariant) the named invariant index 1, 2, or 3 per D89's
  three-to-three mapping. The wiring adapter for ``ToolInvoker``
  invokes this check before dispatching the actual tool call; a
  blocked admissibility translates to the agent context's
  ``TerminationReason.INVARIANT_BLOCKED`` at commit 5.

The service does **not** dispatch tool execution itself — Phase 1
has retrieval as the only tool, and retrieval's mechanics live at
the ingestion context behind the agent context's
``AgentRetrievalClient`` port from S27b / D88. Dispatch is the
agent-context ``ToolInvokerAdapter``'s responsibility at commit 7;
this service is the registry-side gating layer.

The split keeps the tools context independent of ingestion: tool
metadata + classification + invariant gating live here; dispatch
binding to specific tool implementations lives in the wiring layer.
The architectural property: the tools context evolves the registry
concept (Phase 2 may add per-tenant authoring, richer classification
rules, named-callable registration) without coupling to any
particular tool's runtime mechanics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence
from uuid import UUID

from contexts.tools.domain.exceptions import (
    RevisionNotFoundError,
    ToolNotFoundError,
)
from contexts.tools.domain.tool import (
    Classification,
    PHASE_1_PROHIBITED_CLASSIFICATIONS,
    PHASE_1_VISIBLE_CLASSIFICATIONS,
    Tool,
    ToolDefinition,
    ToolRevision,
)
from contexts.tools.ports import ToolRepositoryPort


# Classification-to-invariant mapping per D89's three-to-three
# scheme. The defensive invariant check returns these indices on
# block so audit and termination paths can name the specific
# invariant the call violated.
_CLASSIFICATION_TO_INVARIANT_INDEX: dict[Classification, int] = {
    Classification.FINANCIAL: 1,
    Classification.COMMUNICATION: 2,
    Classification.LEGAL: 3,
}


class InvocationCheckOutcome(str, Enum):
    """Outcome of the defensive invariant check at the invocation boundary (D89)."""

    PERMITTED = "permitted"
    INVARIANT_BLOCKED = "invariant_blocked"
    TOOL_NOT_FOUND = "tool_not_found"
    REVISION_NOT_FOUND = "revision_not_found"


@dataclass(frozen=True)
class InvocationAdmissibility:
    """Result of the defensive invariant check.

    ``invariant_index`` is set to 1, 2, or 3 only when ``outcome`` is
    ``INVARIANT_BLOCKED``; corresponds to D82's five-invariant
    numbering per D89's mapping (financial → 1, communication → 2,
    legal → 3).
    """

    outcome: InvocationCheckOutcome
    message: str
    tool: Tool | None = None
    revision: ToolRevision | None = None
    invariant_index: int | None = None


async def list_visible_definitions(
    *,
    repository: ToolRepositoryPort,
    references: Sequence[tuple[UUID, UUID]],
) -> tuple[ToolDefinition, ...]:
    """Return ToolDefinitions for tools whose classification is visible at Phase 1.

    ``references`` is a sequence of ``(tool_id, revision_id)`` tuples
    — typically the role's allowlist after the commit 4 tuple-shape
    migration. The service walks each reference, looks up the tool
    plus revision, filters to ``PHASE_1_VISIBLE_CLASSIFICATIONS``,
    and returns the consumer-side ``ToolDefinition`` view for each
    surviving tool.

    Missing references (unknown tool id or revision id) are
    skipped silently — the lookup is best-effort against the
    registry. Callers that need strict resolution use
    ``check_invocation_admissibility`` per reference and inspect
    the ``outcome`` field.
    """
    definitions: list[ToolDefinition] = []
    for tool_id, revision_id in references:
        try:
            tool, revision = await repository.find_revision(revision_id)
        except (ToolNotFoundError, RevisionNotFoundError):
            continue
        if tool.id != tool_id:
            # Revision exists but belongs to a different tool than the
            # allowlist entry claims; the binding is structurally
            # inconsistent. Skip rather than raise; the wiring layer
            # can surface an audit event if needed.
            continue
        if tool.classification not in PHASE_1_VISIBLE_CLASSIFICATIONS:
            continue
        definitions.append(_to_definition(tool=tool, revision=revision))
    return tuple(definitions)


async def check_invocation_admissibility(
    *,
    repository: ToolRepositoryPort,
    tool_id: UUID,
    revision_id: UUID,
) -> InvocationAdmissibility:
    """Defensive invariant check at the invocation boundary (D89).

    Looks up the tool plus revision, inspects classification, and
    returns an ``InvocationAdmissibility`` with one of four outcomes:

    - ``PERMITTED``: classification is in
      ``PHASE_1_VISIBLE_CLASSIFICATIONS``. The wiring layer proceeds
      with actual dispatch.
    - ``INVARIANT_BLOCKED``: classification is in
      ``PHASE_1_PROHIBITED_CLASSIFICATIONS`` (financial /
      communication / legal). Returns ``invariant_index`` per the
      three-to-three mapping. The agent loop terminates with
      ``TerminationReason.INVARIANT_BLOCKED`` at commit 5.
    - ``TOOL_NOT_FOUND`` / ``REVISION_NOT_FOUND``: the registry
      lookup failed. The wiring layer translates these to a tool-
      not-registered error at the agent loop.

    The check is *defensive*: at Phase 1, the
    ``ToolDefinitionsLookup`` filter already excludes high-
    classification tools from the LLM's visible-tools surface, so the
    LLM cannot legitimately propose a call to one. The defensive
    layer catches future bypass (a future bug in the filter, a future
    consumer that synthesises tool_calls without going through
    definitions lookup, a future agent loop that wants to expose
    classification-filtered tools but allow operator override). The
    redundancy is intentional per D89.
    """
    try:
        tool, revision = await repository.find_revision(revision_id)
    except RevisionNotFoundError as e:
        return InvocationAdmissibility(
            outcome=InvocationCheckOutcome.REVISION_NOT_FOUND,
            message=str(e),
        )
    except ToolNotFoundError as e:
        return InvocationAdmissibility(
            outcome=InvocationCheckOutcome.TOOL_NOT_FOUND,
            message=str(e),
        )

    if tool.id != tool_id:
        return InvocationAdmissibility(
            outcome=InvocationCheckOutcome.REVISION_NOT_FOUND,
            message=(
                f"revision {revision_id} belongs to tool {tool.id} "
                f"but caller named tool {tool_id}; binding inconsistent"
            ),
        )

    if tool.classification in PHASE_1_PROHIBITED_CLASSIFICATIONS:
        idx = _CLASSIFICATION_TO_INVARIANT_INDEX[tool.classification]
        return InvocationAdmissibility(
            outcome=InvocationCheckOutcome.INVARIANT_BLOCKED,
            message=(
                f"tool {tool.name!r} (classification "
                f"{tool.classification.value!r}) is gated by "
                f"platform invariant {idx} per D82/D89; invocation "
                f"prohibited at Phase 1"
            ),
            tool=tool,
            revision=revision,
            invariant_index=idx,
        )

    return InvocationAdmissibility(
        outcome=InvocationCheckOutcome.PERMITTED,
        message="invocation admissible",
        tool=tool,
        revision=revision,
    )


def _to_definition(*, tool: Tool, revision: ToolRevision) -> ToolDefinition:
    """Compose a consumer-side ToolDefinition from the persisted aggregates."""
    return ToolDefinition(
        tool_id=tool.id,
        revision_id=revision.id,
        name=tool.name,
        description=tool.description or "",
        classification=tool.classification,
        parameters_schema=revision.parameters_schema,
        returns_schema=revision.returns_schema,
    )


__all__ = [
    "InvocationAdmissibility",
    "InvocationCheckOutcome",
    "check_invocation_admissibility",
    "list_visible_definitions",
]
