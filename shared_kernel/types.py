from __future__ import annotations

from dataclasses import dataclass
from typing import NewType
from uuid import UUID

TenantId = NewType("TenantId", str)
Jurisdiction = NewType("Jurisdiction", str)


@dataclass(frozen=True, order=True)
class ToolAllowlistEntry:
    """Pinned reference to a specific tool revision (D89, S28b commit 4).

    Lives in ``shared_kernel`` because both the methodology context
    (``RoleRevision.tool_allowlist``) and the agent context
    (``AgentRevision.tool_allowlist``, plus the consumer-side
    ``MethodologyView`` / ``RoleView`` / ``EffectiveConstraintBundle``)
    reference this exact shape. Per the shared_kernel discipline,
    referentially-equal cross-context types live here; the alternative
    (parallel definitions in both contexts) would violate D17 if either
    context imported the other's type.

    Pinning at role authoring time per D89's commit 4 reasoning: the
    role binds to a *specific* tool revision so revision evolution
    does not silently drift the role's behaviour. The pre-D89
    allowlist shape was ``tuple[str, ...]`` (opaque tool names);
    Alembic 0010_role_tool_allowlist_pin converts existing rows to
    this tuple shape, recomputing role revision hashes against the
    new content surface per D74's chain-self-containment pattern.

    ``order=True`` so the canonical hash payload helper can sort
    tool_allowlist deterministically before encoding.
    """

    tool_id: UUID
    revision_id: UUID
