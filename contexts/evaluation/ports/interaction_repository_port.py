"""InteractionRepositoryPort — read access to interaction sets.

The ``replay_and_score`` orchestrator iterates the interactions in
an ``InteractionSet`` and, for each, runs the configured replay
model and applies the scoring sheet. The port exposes the read so
the orchestrator stays free of storage concerns. Per-tenant routing
is the adapter's responsibility, consistent with the other
evaluation repository ports.

S17a ships read-only at one method; write surfaces (creating
interaction sets and individual interactions) defer until an
inbound authoring path needs them. The S17a integration test
fixtures interactions via direct SQL through the same per-tenant
session — same pattern the S16 e2e test uses for scoring sheets.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.evaluation.domain.interaction import Interaction


class InteractionRepositoryPort(Protocol):
    async def list_by_set_id(
        self, interaction_set_id: UUID
    ) -> list[Interaction]:
        """Return every interaction belonging to the set, ordered by
        ``ordering`` ascending.

        Empty list if the set does not exist or holds no interactions;
        callers treat empty as "nothing to replay" rather than an
        error.
        """
        ...
