"""MethodologyOverridesLookup Protocol port (D88, S27b).

The agent runtime's runtime-time companion to ``MethodologyLookup``
(D79). Where ``MethodologyLookup`` resolves a methodology revision to
its first role's content for the clone-from-methodology use case,
``MethodologyOverridesLookup`` resolves a methodology revision to the
per-role overrides for a specific role within the methodology — the
shape ``invoke_agent`` needs at runtime to compose effective
constraints per D87.

The two ports are kept separate (rather than overloading
``MethodologyLookup``) because their use-case boundaries differ: the
clone-time port runs once per agent creation and returns the resolved
role's content; the runtime port runs once per invocation and returns
just the override dict for the agent's specific role within a
particular methodology revision. Separate ports keep the port
boundaries aligned with the consumer use cases.

The port returns the methodology's structured override mapping for
the matching ``role_id`` (or an empty dict when no override exists
for that role in the methodology revision). Override shape per D87:
``dict[str, dict[str, Any]]`` keyed by role-bundle field name with
each value the canonical ``{"mode": <str>, "value": <any>}`` form.
The agent context's composition resolver consumes this dict directly.

The wiring adapter at ``apps/cli/_cross_context.py`` implements this
Protocol by reading the methodology revision through the methodology
repository and scanning ``role_refs`` for the matching role_id.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from padhanam.security import Principal


class MethodologyOverridesLookup(Protocol):
    """Callable port for runtime per-role override resolution (D88).

    Accepts ``methodology_template_id``, ``methodology_version``, and
    ``role_id`` (the agent's ``source_role_id``); returns the
    methodology revision's ``role_refs`` entry's ``overrides``
    dictionary for the matching role.

    Returns an empty dict when the methodology revision carries no
    ``role_refs`` entry for the given ``role_id`` (the agent's role
    is not part of this methodology) and when the matching entry's
    ``overrides`` is empty. The two empty cases are
    indistinguishable at the composition layer because both produce
    the same identity composition (role base, no overlay).

    ``version=None`` resolves to the methodology template's latest
    revision; the adapter records the resolved integer at the
    lookup site, but the runtime caller typically passes the agent's
    pinned ``source_methodology_template_version`` so the resolved
    version matches the agent's lineage exactly.

    Lookup failure propagates as ``LookupError`` from the underlying
    repository for unknown methodology id or version.
    """

    async def __call__(
        self,
        *,
        methodology_template_id: UUID,
        methodology_version: int | None,
        role_id: UUID,
        principal: Principal,
    ) -> dict[str, dict[str, Any]]: ...
