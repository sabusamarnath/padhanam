"""Postgres adapter for CommitmentRepository (D157).

Per-tenant Postgres data planes, SQLAlchemy 2.0 Core, manual
row-to-entity materialisation, tenant-id bound at construction as
defence-in-depth per D24 / D32. Completion-log last-activity is computed
with a ``MAX(completed_at)`` grouped query and zipped against the
commitments in Python.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.daily_driver.adapters.outbound.postgres._tables import (
    commitment_checkin_responses as checkin_responses_table,
)
from contexts.daily_driver.adapters.outbound.postgres._tables import (
    commitment_completions as completions_table,
)
from contexts.daily_driver.adapters.outbound.postgres._tables import (
    commitments as commitments_table,
)
from contexts.daily_driver.domain.commitment import (
    CheckinOutcome,
    CheckinResponse,
    Commitment,
    CommitmentActivity,
    CommitmentCompletion,
    OutcomeStatus,
)
from shared_kernel import TenantContext, TenantId


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresCommitmentRepository:
    """Adapter implementation of ``CommitmentRepository`` (D157)."""

    def __init__(
        self,
        *,
        per_tenant_sessionmaker_resolver: _SessionFactoryResolver,
        bound_tenant_id: TenantId,
    ) -> None:
        self._resolve_per_tenant = per_tenant_sessionmaker_resolver
        self._bound_tenant_id = bound_tenant_id

    def _assert_bound(self, tenant_context: TenantContext) -> None:
        if str(tenant_context.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"TenantContext.tenant_id={tenant_context.tenant_id!r} does "
                f"not match adapter's bound tenant {self._bound_tenant_id!r}; "
                "tenant-isolation defence-in-depth per D24 / D32"
            )

    @staticmethod
    def _row_to_commitment(row: sa.engine.Row) -> Commitment:
        status = row.outcome_status
        return Commitment(
            id=UUID(row.id),
            tenant_id=UUID(row.tenant_id),
            jurisdiction=row.jurisdiction,
            name=row.name,
            expected_interval_days=row.expected_interval_days,
            authored_by_user_id=row.authored_by_user_id,
            created_at=row.created_at,
            expected_outcome=row.expected_outcome,
            observed_outcome=row.observed_outcome,
            outcome_status=(
                OutcomeStatus(status) if status is not None else None
            ),
            observed_at=row.observed_at,
        )

    async def add_commitment(
        self, *, tenant_context: TenantContext, commitment: Commitment
    ) -> None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(commitments_table).values(
                        id=str(commitment.id),
                        tenant_id=str(commitment.tenant_id),
                        jurisdiction=commitment.jurisdiction,
                        name=commitment.name,
                        expected_interval_days=(
                            commitment.expected_interval_days
                        ),
                        authored_by_user_id=commitment.authored_by_user_id,
                        created_at=commitment.created_at,
                        expected_outcome=commitment.expected_outcome,
                    )
                )

    async def add_completion(
        self,
        *,
        tenant_context: TenantContext,
        completion: CommitmentCompletion,
    ) -> None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(completions_table).values(
                        id=str(completion.id),
                        commitment_id=str(completion.commitment_id),
                        tenant_id=str(completion.tenant_id),
                        jurisdiction=completion.jurisdiction,
                        completed_at=completion.completed_at,
                    )
                )

    async def add_checkin_response(
        self,
        *,
        tenant_context: TenantContext,
        response: CheckinResponse,
    ) -> None:
        """Append one check-in response (the negative store; D192)."""
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(checkin_responses_table).values(
                        id=str(response.id),
                        commitment_id=str(response.commitment_id),
                        tenant_id=str(response.tenant_id),
                        jurisdiction=response.jurisdiction,
                        beat_date=response.beat_date,
                        outcome=response.outcome.value,
                    )
                )

    async def get_commitment(
        self, *, tenant_context: TenantContext, commitment_id: UUID
    ) -> Commitment | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            row = (
                await session.execute(
                    sa.select(commitments_table).where(
                        sa.and_(
                            commitments_table.c.id == str(commitment_id),
                            commitments_table.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                )
            ).one_or_none()
        return None if row is None else self._row_to_commitment(row)

    async def record_observed_outcome(
        self,
        *,
        tenant_context: TenantContext,
        commitment_id: UUID,
        observed_outcome: str | None,
        outcome_status: OutcomeStatus,
        observed_at: datetime,
    ) -> Commitment | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                result = await session.execute(
                    sa.update(commitments_table)
                    .where(
                        sa.and_(
                            commitments_table.c.id == str(commitment_id),
                            commitments_table.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                    .values(
                        observed_outcome=observed_outcome,
                        outcome_status=outcome_status.value,
                        observed_at=observed_at,
                    )
                    .returning(commitments_table)
                )
                row = result.one_or_none()
        return None if row is None else self._row_to_commitment(row)

    async def list_with_activity(
        self, *, tenant_context: TenantContext
    ) -> tuple[CommitmentActivity, ...]:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            commitment_rows = (
                await session.execute(
                    sa.select(commitments_table)
                    .where(
                        commitments_table.c.tenant_id
                        == str(self._bound_tenant_id)
                    )
                    .order_by(commitments_table.c.created_at)
                )
            ).all()
            last_rows = (
                await session.execute(
                    sa.select(
                        completions_table.c.commitment_id,
                        sa.func.max(completions_table.c.completed_at).label(
                            "last_completed_at"
                        ),
                    )
                    .where(
                        completions_table.c.tenant_id
                        == str(self._bound_tenant_id)
                    )
                    .group_by(completions_table.c.commitment_id)
                )
            ).all()
            # D192 (Option B): dids come ONLY from completions (above); the
            # negative comes ONLY from the sibling store, filtered to
            # reported_didnt — so no outcome is read from two stores.
            didnt_rows = (
                await session.execute(
                    sa.select(
                        checkin_responses_table.c.commitment_id,
                        sa.func.max(checkin_responses_table.c.beat_date).label(
                            "last_reported_didnt"
                        ),
                    )
                    .where(
                        sa.and_(
                            checkin_responses_table.c.tenant_id
                            == str(self._bound_tenant_id),
                            checkin_responses_table.c.outcome
                            == CheckinOutcome.REPORTED_DIDNT.value,
                        )
                    )
                    .group_by(checkin_responses_table.c.commitment_id)
                )
            ).all()
        last_by_commitment = {
            r.commitment_id: r.last_completed_at for r in last_rows
        }
        didnt_by_commitment = {
            r.commitment_id: r.last_reported_didnt for r in didnt_rows
        }
        return tuple(
            CommitmentActivity(
                commitment=self._row_to_commitment(row),
                last_completed_at=last_by_commitment.get(row.id),
                last_reported_didnt=didnt_by_commitment.get(row.id),
            )
            for row in commitment_rows
        )


__all__ = ["PostgresCommitmentRepository"]
