"""RubricApplicationRepositoryPort — write+read surface for score results.

The ``apply_scoring_sheet`` use case persists one ``RubricApplication``
record per (criterion, applier_config) pair it processes; the
``cost_per_successful_task`` use case at S17b reads the persisted
records joined against the interaction set to compute the cost
rollup. Two methods, one read and one write; per-tenant routing is
the adapter's responsibility — the Postgres adapter holds an
``async_sessionmaker`` resolved against the tenant's data plane via
the tenancy context's session-factory cache (D36).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.evaluation.domain.rubric_application import RubricApplication


class RubricApplicationRepositoryPort(Protocol):
    async def save(self, rubric_application: RubricApplication) -> None:
        """Persist one rubric_application record."""
        ...

    async def list_for_revision_and_set(
        self,
        scoring_sheet_revision_id: UUID,
        interaction_set_id: UUID,
    ) -> list[RubricApplication]:
        """Return every rubric_application persisted for the given
        revision and interaction set.

        Joins rubric_applications with interactions on interaction_id
        and filters by both revision id and interaction_set_id. The
        cost-per-successful-task use case at S17b consumes this read
        path; the regression-report use case at S18 will follow the
        same shape.
        """
        ...
