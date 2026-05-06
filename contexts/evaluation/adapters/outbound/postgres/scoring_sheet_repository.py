"""Postgres adapter for ScoringSheetRepositoryPort.

Reads ``scoring_sheet_criteria`` joined with ``appliers`` on
``criterion_id``, filtered by ``scoring_sheet_revision_id``. Returns
domain objects; SQLAlchemy Core + manual row→domain construction
mirrors the registry-adapter pattern from D34 (frozen dataclasses are
not ORM-friendly to load).
"""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.evaluation.adapters.outbound.postgres._tables import (
    appliers,
    scoring_sheet_criteria,
)
from contexts.evaluation.domain.applier import ApplierConfig, ApplierType
from contexts.evaluation.domain.scoring_sheet import Criterion, CriterionLevel


class PostgresScoringSheetRepository:
    """Adapter for ScoringSheetRepositoryPort."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def get_criteria_with_appliers(
        self, scoring_sheet_revision_id: UUID
    ) -> list[tuple[Criterion, ApplierConfig]]:
        stmt = (
            sa.select(
                scoring_sheet_criteria,
                appliers,
            )
            .select_from(
                scoring_sheet_criteria.join(
                    appliers,
                    appliers.c.criterion_id == scoring_sheet_criteria.c.id,
                )
            )
            .where(
                scoring_sheet_criteria.c.scoring_sheet_revision_id
                == str(scoring_sheet_revision_id)
            )
            .order_by(scoring_sheet_criteria.c.ordering.asc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.mappings().all()

        pairs: list[tuple[Criterion, ApplierConfig]] = []
        for row in rows:
            criterion = Criterion(
                id=UUID(str(row["id"])),
                scoring_sheet_revision_id=UUID(
                    str(row["scoring_sheet_revision_id"])
                ),
                name=row["name"],
                description=row["description"] or "",
                levels=tuple(
                    CriterionLevel(
                        label=level["label"],
                        definition=level["definition"],
                        # S17b extension: is_success flags whether a
                        # rubric_application at this level counts as
                        # a successful task. Legacy rows persisted
                        # before the extension default to False so
                        # the read path stays tolerant until rows are
                        # rewritten.
                        is_success=bool(level.get("is_success", False)),
                    )
                    for level in row["levels"]
                ),
                ordering=row["ordering"],
            )
            # The select projects scoring_sheet_criteria first then
            # appliers; SQLAlchemy mappings disambiguate by column name
            # but where there's a name collision (id, etc.) we must
            # read by Column object reference.
            applier_config = ApplierConfig(
                id=UUID(str(row[appliers.c.id])),
                scoring_sheet_revision_id=UUID(
                    str(row[appliers.c.scoring_sheet_revision_id])
                ),
                criterion_id=UUID(str(row[appliers.c.criterion_id])),
                applier_type=ApplierType(row[appliers.c.applier_type]),
                deterministic_function_name=row[
                    appliers.c.deterministic_function_name
                ],
                prompt_template=row[appliers.c.prompt_template],
                judge_model=row[appliers.c.judge_model],
            )
            pairs.append((criterion, applier_config))
        return pairs
