"""Application-layer Protocol ports for cross-context use cases (D79).

Distinct from ``contexts/agent/ports/`` which holds the persistence-side
``AgentRepositoryPort``. The ports in this subpackage are consumer-
shaped abstractions over other contexts' application surfaces: the
agent context defines the shapes it needs from methodology and
ingestion, and apps/cli adapters translate those producer contexts'
public api surfaces into the consumer-side Protocol calls.

The pattern preserves D17's independence contracts: no imports from
``contexts.methodology`` or ``contexts.ingestion`` reach the agent
context's domain or application layers; the apps/cli wiring layer
is the legitimate seam.
"""

from contexts.agent.application.ports.methodology_lookup import (
    MethodologyLookup,
    MethodologyView,
)
from contexts.agent.application.ports.role_lookup import (
    RoleLookup,
    RoleView,
)
from contexts.agent.application.ports.source_lookup import (
    SourceLookup,
    SourceNotFoundError,
)

__all__ = [
    "MethodologyLookup",
    "MethodologyView",
    "RoleLookup",
    "RoleView",
    "SourceLookup",
    "SourceNotFoundError",
]
