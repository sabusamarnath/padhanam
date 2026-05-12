"""ToolDefinitionsLookup Protocol port (D89, S28b commit 5).

Consumer-shaped port at the agent context. The composition resolver
calls this port at invocation time with the effective tool_allowlist
(after methodology overrides have been applied) and receives back the
tools formatted for the LLM call — name, description, parameters
schema. The wiring adapter at ``apps/cli/_cross_context.py`` (commit
7) implements this port by calling the tools context's
``list_visible_definitions`` and translating the tools-context
``ToolDefinition`` value object into the inference-context
``ToolDefinition`` shape that LiteLLM consumes.

The port returns ``inference.ToolDefinition`` because that's the
shape the LLM call needs. The translation from tools-context
``ToolDefinition`` (4 fields: name, description, parameters_schema,
returns_schema) to inference-context ``ToolDefinition`` (3 fields:
name, description, parameters) is the wiring adapter's
responsibility; the agent context never sees the tools-context
type. Independence per D17 preserved at the import boundary.

Phase 1 classification policy filtering happens at the adapter
layer (the tools-context invocation service applies
``PHASE_1_VISIBLE_CLASSIFICATIONS``); the agent context's port
contract is "give me the tools that are visible at runtime for this
allowlist", with the visibility policy embedded in the adapter.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from contexts.inference.domain.completion import ToolDefinition
from shared_kernel import ToolAllowlistEntry


class ToolDefinitionsLookup(Protocol):
    """Resolve a role's effective allowlist to LLM-ready tool definitions.

    Async because the underlying tools-context invocation service is
    async (calls the postgres repository for each tool revision lookup).
    Returns an empty tuple when the allowlist is empty or every entry
    is filtered out by Phase 1 classification policy.
    """

    async def __call__(
        self,
        *,
        allowlist: Sequence[ToolAllowlistEntry],
    ) -> tuple[ToolDefinition, ...]:
        ...
