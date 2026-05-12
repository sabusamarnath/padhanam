"""Application-layer Protocol ports for cross-context use cases (D79, D88).

Distinct from ``contexts/agent/ports/`` which holds the persistence-side
``AgentRepositoryPort`` plus the runtime-side ``AgentExecutor`` port.
The ports in this subpackage are consumer-shaped abstractions over
other contexts' application surfaces: the agent context defines the
shapes it needs from methodology and ingestion, and apps/cli adapters
translate those producer contexts' public api surfaces into the
consumer-side Protocol calls.

The pattern preserves D17's independence contracts: no imports from
``contexts.methodology`` or ``contexts.ingestion`` reach the agent
context's domain or application layers; the apps/cli wiring layer
is the legitimate seam.

S27b (D88) adds two runtime-time ports alongside the existing
clone-time ports: ``AgentRetrievalClient`` (consumer-shaped retrieval
surface; wiring adapter composes ingestion's split methods) and
``MethodologyOverridesLookup`` (runtime per-role override resolver
distinct from clone-time ``MethodologyLookup``).
"""

from contexts.agent.application.ports.methodology_lookup import (
    MethodologyLookup,
    MethodologyView,
)
from contexts.agent.application.ports.methodology_overrides_lookup import (
    MethodologyOverridesLookup,
)
from contexts.agent.application.ports.retrieval_client import (
    AgentRetrievalClient,
    RetrievedChunk,
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
    "AgentRetrievalClient",
    "MethodologyLookup",
    "MethodologyOverridesLookup",
    "MethodologyView",
    "RetrievedChunk",
    "RoleLookup",
    "RoleView",
    "SourceLookup",
    "SourceNotFoundError",
]
