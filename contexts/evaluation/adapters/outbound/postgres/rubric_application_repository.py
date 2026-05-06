"""Postgres adapter for RubricApplicationRepositoryPort.

Persists one ``RubricApplication`` per ``save`` call and reads them
back joined against the interactions table for the cost-per-
successful-task use case at S17b. Per-tenant routing is the
session_factory caller's concern (D36); the adapter takes
``async_sessionmaker`` at construction so a single instance serves
one tenant's data plane.
"""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.evaluation.adapters.outbound.postgres._tables import (
    interactions,
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
                    trace_id=rubric_application.trace_id,
                )
            )
            await session.commit()

    async def list_for_revision_and_set(
        self,
        scoring_sheet_revision_id: UUID,
        interaction_set_id: UUID,
    ) -> list[RubricApplication]:
        stmt = (
            sa.select(rubric_applications)
            .select_from(
                rubric_applications.join(
                    interactions,
                    interactions.c.id == rubric_applications.c.interaction_id,
                )
            )
            .where(
                rubric_applications.c.scoring_sheet_revision_id
                == str(scoring_sheet_revision_id)
            )
            .where(
                interactions.c.interaction_set_id
                == str(interaction_set_id)
            )
            .order_by(rubric_applications.c.created_at.asc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.mappings().all()
        return [
            RubricApplication(
                id=UUID(str(row["id"])),
                scoring_sheet_revision_id=UUID(
                    str(row["scoring_sheet_revision_id"])
                ),
                criterion_id=UUID(str(row["criterion_id"])),
                interaction_id=UUID(str(row["interaction_id"])),
                applier_id=UUID(str(row["applier_id"])),
                automated_score=row["automated_score"],
                human_score=row["human_score"],
                reviewed_by_user_id=row["reviewed_by_user_id"],
                confirmed_at=row["confirmed_at"],
                created_at=row["created_at"],
                trace_id=row["trace_id"],
            )
            for row in rows
        ]
