"""RubricApplicationRepositoryPort — write surface for score results.

The ``apply_scoring_sheet`` use case persists one
``RubricApplication`` record per (criterion, applier_config) pair it
processes. The port exposes a single ``save`` method; batched-insert
optimisation defers until measurement justifies (S17/S18 territory).
Per-tenant routing is the adapter's responsibility — the Postgres
adapter holds an ``async_sessionmaker`` resolved against the tenant's
data plane via the tenancy context's session-factory cache (D36).
"""

from __future__ import annotations

from typing import Protocol

from contexts.evaluation.domain.rubric_application import RubricApplication


class RubricApplicationRepositoryPort(Protocol):
    async def save(self, rubric_application: RubricApplication) -> None:
        """Persist one rubric_application record."""
        ...
