"""ScoringSheetRepositoryPort — read access to scoring sheet structure.

The ``apply_scoring_sheet`` use case needs the criteria attached to a
revision plus the applier configured for each criterion. The port
exposes that join as a single read so the use case stays free of
storage concerns. Per-tenant routing is the adapter's responsibility:
the Postgres adapter holds an ``async_sessionmaker`` resolved against
the tenant's data plane via the tenancy context's session-factory
cache (D36).

Read-only port at S16. Write operations (creating sheets, revisions,
criteria, and appliers) are not exposed because no S16 use case
performs them — integration tests fixture data via direct SQL through
the same per-tenant session. When the inbound adapter for scoring-
sheet authoring lands (later in P5 or P10), a write port is added
alongside this one.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.evaluation.domain.applier import ApplierConfig
from contexts.evaluation.domain.scoring_sheet import Criterion


class ScoringSheetRepositoryPort(Protocol):
    async def get_criteria_with_appliers(
        self, scoring_sheet_revision_id: UUID
    ) -> list[tuple[Criterion, ApplierConfig]]:
        """Return every (criterion, applier_config) pair for the revision.

        Order is by ``criterion.ordering`` ascending so the use case
        applies criteria in the rubric author's intended sequence. The
        adapter joins ``scoring_sheet_criteria`` with ``appliers`` on
        ``criterion_id`` and filters by the given revision id; if no
        applier is configured for a criterion, the pair is omitted at
        S16 (no S16 use case applies an unconfigured criterion).
        """
        ...
