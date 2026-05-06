"""Postgres adapter for InteractionRepositoryPort.

Reads ``interactions`` filtered by ``interaction_set_id``, ordered
by ``ordering``. Returns domain objects; SQLAlchemy Core + manual
row→domain construction mirrors the registry-adapter pattern from
D34. Per-tenant routing handled at session-factory construction
time, consistent with the other evaluation repositories.
"""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.evaluation.adapters.outbound.postgres._tables import interactions
from contexts.evaluation.domain.interaction import Interaction


class PostgresInteractionRepository:
    """Adapter for InteractionRepositoryPort."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def list_by_set_id(
        self, interaction_set_id: UUID
    ) -> list[Interaction]:
        stmt = (
            sa.select(interactions)
            .where(
                interactions.c.interaction_set_id == str(interaction_set_id)
            )
            .order_by(interactions.c.ordering.asc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.mappings().all()
        return [
            Interaction(
                id=UUID(str(row["id"])),
                interaction_set_id=UUID(str(row["interaction_set_id"])),
                input=row["input"],
                expected_output=row["expected_output"],
                ordering=row["ordering"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
