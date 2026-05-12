"""Tools context domain exceptions (D89)."""

from __future__ import annotations


class ToolNotFoundError(LookupError):
    """The named tool id does not exist in the registry."""


class RevisionNotFoundError(LookupError):
    """The named (tool_id, version) revision does not exist."""


class ClassificationProhibitedError(ValueError):
    """The authored classification is prohibited at Phase 1 (D89).

    Raised by ``create_tool`` when the operator attempts to author a
    tool with classification ``financial``, ``communication``, or
    ``legal``. The error message names the per-invocation confirmation
    pathway deferred-decisions entry so the operator understands the
    forward trajectory: the prohibition lifts when that pathway
    lands, at which point high-classification tools can be authored
    with per-invocation user confirmation as the runtime guardrail.
    """
