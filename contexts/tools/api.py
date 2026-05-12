"""Public query interface for the tools context (D17, D89).

Per D17, every context exposes a single api.py at its root with read-
only query methods other contexts may call. At S28b commit 2 the
surface is the domain types plus the repository port and the
``RoleToolBinding`` DTO; commit 3 adds the use-case-level read
methods (``get_tool``, ``list_tools``); commit 6 adds the BC stub
result type.

Cross-context callers consume through this facade. The agent
context's two thin ports (``ToolDefinitionsLookup``, ``ToolInvoker``)
defined at ``contexts/agent/application/ports/`` are implemented by
adapters at ``apps/cli/_cross_context.py`` that call into this
module per the consumer-port-plus-wiring-adapter pattern reinforced
at S26a-1, S26a-2, S27b, and now S28b (third reinforcement, Phase 1
norm per D89).

The tools context is control-plane-scoped per D89's storage-location
resolution; the API surface carries no ``TenantContext`` parameter
because the data is platform-managed and visible across tenants by
design (the inverse of agent isolation per the P7 epic note).
Per-tenant tool authoring lifts at Phase 2 per the deferred-decisions
entry on customer-deployment evidence.
"""

from __future__ import annotations

from contexts.tools.domain.exceptions import (
    ClassificationProhibitedError,
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
from contexts.tools.ports.tool_repository import (
    RoleToolBinding,
    ToolRepositoryPort,
)

__all__ = [
    "Classification",
    "ClassificationProhibitedError",
    "PHASE_1_PROHIBITED_CLASSIFICATIONS",
    "PHASE_1_VISIBLE_CLASSIFICATIONS",
    "RevisionNotFoundError",
    "RoleToolBinding",
    "Tool",
    "ToolDefinition",
    "ToolNotFoundError",
    "ToolRepositoryPort",
    "ToolRevision",
]
