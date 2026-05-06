"""Postgres adapter for RubricApplicationRepositoryPort.

Persists one ``RubricApplication`` per ``save`` call. Per-tenant
routing is the session_factory caller's concern (D36); the adapter
takes ``async_sessionmaker`` at construction so a single instance
serves one tenant's data plane.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.evaluation.adapters.outbound.postgres._tables import (
    rubric_applications,
)
from contexts.evaluation.domain.rubric_application import RubricApplication


class PostgresRubricApplicationRepository:
    """Adapter for RubricApplicationRepositoryPort."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def save(self, rubric_application: RubricApplication) -> None:
        async with self._session_factory() as session:
            await session.execute(
                sa.insert(rubric_applications).values(
                    id=str(rubric_application.id),
                    scoring_sheet_revision_id=str(
                        rubric_application.scoring_sheet_revision_id
                    ),
                    criterion_id=str(rubric_application.criterion_id),
                    interaction_id=str(rubric_application.interaction_id),
                    applier_id=str(rubric_application.applier_id),
                    automated_score=rubric_application.automated_score,
                    human_score=rubric_application.human_score,
                    reviewed_by_user_id=rubric_application.reviewed_by_user_id,
                    confirmed_at=rubric_application.confirmed_at,
                    created_at=rubric_application.created_at,
                )
            )
            await session.commit()
