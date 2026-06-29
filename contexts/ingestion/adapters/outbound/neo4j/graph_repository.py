"""Neo4j implementation of GraphRepositoryPort (D63 / D64).

Long-lived adapter constructed once per process; wraps the shared
``AsyncDriver`` plus the Neo4jSettings credentials. Each
GraphRepositoryPort method opens a fresh
``TenantScopedNeo4jSession`` for the duration of the call so the
bound tenant_id predicate is auto-applied to every Cypher
template the wrapper executes.

The adapter translates Neo4j driver exceptions into the port's
two error categories: retryable infra failures
(``ServiceUnavailable``, ``SessionExpired``, ``TransientError``,
``IncompleteCommit``) become ``GraphRepositoryError``; everything
else (auth, schema mismatch, malformed Cypher, value errors from
the wrapper's tenant-id validation) becomes
``GraphRepositoryConfigurationError``.

Construction: pass ``Neo4jSettings`` and a connection lifecycle
hook (``close()``) that the application's shutdown path calls so
the driver disposes cleanly.
"""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from contexts.ingestion.ports.outcome_graph_port import (
    AuthoredCddRecord,
    GateRecord,
    OpportunityRecord,
    OutcomeGraphRecord,
)
from contexts.ingestion.ports.unit_graph_port import (
    ElementEvidenceRecord,
    ElementEvidenceWrite,
    GoalEdgeRecord,
    GoalEdgeWrite,
    UnitGraphRecord,
    UnitWrite,
)

from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import (
    AuthError,
    ConfigurationError,
    Neo4jError,
    ServiceUnavailable,
    SessionExpired,
    TransientError,
)

from contexts.ingestion.adapters.outbound.neo4j.session import (
    TenantScopedNeo4jSession,
)
from contexts.ingestion.domain.entity import Entity
from contexts.ingestion.domain.relationship import Relationship
from contexts.ingestion.ports.graph_repository_port import (
    GraphRepositoryConfigurationError,
    GraphRepositoryError,
)
from padhanam.config import Neo4jSettings
from shared_kernel import TenantContext


_RETRYABLE_DRIVER_EXC = (ServiceUnavailable, SessionExpired, TransientError)
_NON_RETRYABLE_DRIVER_EXC = (AuthError, ConfigurationError)


def make_async_driver(settings: Neo4jSettings) -> AsyncDriver:
    """Construct a Neo4j AsyncDriver from Neo4jSettings.

    The neo4j wrapper module is the single import surface for the
    bolt driver per D63; consumers outside this module that need a
    driver (e.g. the retrieval adapter at S22) call this helper
    rather than importing ``neo4j.AsyncGraphDatabase`` directly.
    Callers own the returned driver's lifecycle and must call
    ``await driver.close()`` at shutdown.
    """
    return AsyncGraphDatabase.driver(
        settings.bolt_uri,
        auth=(settings.user, settings.password),
    )


class Neo4jGraphRepository:
    """Concrete GraphRepositoryPort against the shared Neo4j 5
    Community instance per D63.
    """

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    @classmethod
    def from_settings(cls, settings: Neo4jSettings) -> "Neo4jGraphRepository":
        driver = AsyncGraphDatabase.driver(
            settings.bolt_uri,
            auth=(settings.user, settings.password),
        )
        return cls(driver)

    async def close(self) -> None:
        await self._driver.close()

    async def merge_entities(
        self,
        entities: Sequence[Entity],
        tenant_context: TenantContext,
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.merge_entities(entities)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except ValueError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def merge_relationships(
        self,
        relationships: Sequence[Relationship],
        tenant_context: TenantContext,
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.merge_relationships(relationships)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except ValueError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def get_entities_by_chunk_ids(
        self,
        chunk_ids: Sequence[UUID],
        tenant_context: TenantContext,
    ) -> Sequence[Entity]:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.get_entities_by_chunk_ids(chunk_ids)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def get_relationships_by_chunk_ids(
        self,
        chunk_ids: Sequence[UUID],
        tenant_context: TenantContext,
    ) -> Sequence[Relationship]:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.get_relationships_by_chunk_ids(chunk_ids)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    # --- OutcomeGraphPort (D163): the typed goal-graph capability ----------

    async def merge_outcome(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        name: str,
        control: str,
        subject: str,
        mode: str,
        ladder: Sequence[str],
        current_target_level: str | None,
        terminal_target: str | None = None,
        terminal_state: str | None = None,
        aliases: Sequence[str] = (),
        domain: str | None = None,
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.merge_outcome(
                    outcome_id=outcome_id,
                    name=name,
                    control=control,
                    subject=subject,
                    mode=mode,
                    ladder=ladder,
                    current_target_level=current_target_level,
                    terminal_target=terminal_target,
                    terminal_state=terminal_state,
                    aliases=aliases,
                    domain=domain,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def merge_lever_for_outcome(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        commitment_id: UUID,
        step_order: int | None = None,
        step_state: str | None = None,
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.merge_lever_for_outcome(
                    outcome_id=outcome_id,
                    commitment_id=commitment_id,
                    step_order=step_order,
                    step_state=step_state,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def set_outcome_target(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        current_target_level: str,
    ) -> str | None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.set_outcome_target(
                    outcome_id=outcome_id,
                    current_target_level=current_target_level,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def archive_outcome(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.archive_outcome(outcome_id=outcome_id)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def unarchive_outcome(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.unarchive_outcome(outcome_id=outcome_id)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def list_archived_outcome_ids(
        self, *, tenant_context: TenantContext
    ) -> list[UUID]:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.list_archived_outcome_ids()
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def list_outcomes(
        self,
        *,
        tenant_context: TenantContext,
    ) -> Sequence[OutcomeGraphRecord]:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.list_outcomes()
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    # --- Authored CDD layer (S102, D200) -----------------------------------

    async def merge_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        element_kind: str,
        element_id: UUID,
        label: str,
        provenance_origin: str,
        proof_state: str,
        gate_id: UUID | None = None,
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.merge_authored_element(
                    outcome_id=outcome_id,
                    element_kind=element_kind,
                    element_id=element_id,
                    label=label,
                    provenance_origin=provenance_origin,
                    proof_state=proof_state,
                    gate_id=gate_id,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def merge_gate(
        self,
        *,
        tenant_context: TenantContext,
        gate_id: UUID,
        outcome_id: UUID,
        name: str,
        gate_order: int,
        local_outcome: str,
        local_goal: str,
        provenance_origin: str,
        proof_state: str,
        step_commitment_id: UUID | None = None,
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.merge_gate(
                    gate_id=gate_id,
                    outcome_id=outcome_id,
                    name=name,
                    gate_order=gate_order,
                    local_outcome=local_outcome,
                    local_goal=local_goal,
                    provenance_origin=provenance_origin,
                    proof_state=proof_state,
                    step_commitment_id=step_commitment_id,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def list_gates(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> Sequence[GateRecord]:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                rows = await s.list_gates(outcome_id=outcome_id)
                return [
                    GateRecord(
                        gate_id=UUID(r["gate_id"]),
                        outcome_id=outcome_id,
                        name=r["name"],
                        gate_order=r["gate_order"],
                        local_outcome=r["local_outcome"],
                        local_goal=r["local_goal"],
                        provenance_origin=r["provenance_origin"],
                        proof_state=r["proof_state"],
                        step_commitment_id=(
                            UUID(r["step_commitment_id"])
                            if r.get("step_commitment_id")
                            else None
                        ),
                    )
                    for r in rows
                ]
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def merge_opportunity(
        self,
        *,
        tenant_context: TenantContext,
        opportunity_id: UUID,
        outcome_id: UUID,
        name: str,
        current_gate_id: UUID | None,
        provenance_origin: str,
        proof_state: str,
        source: str | None = None,
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.merge_opportunity(
                    opportunity_id=opportunity_id, outcome_id=outcome_id,
                    name=name, current_gate_id=current_gate_id,
                    provenance_origin=provenance_origin, proof_state=proof_state,
                    source=source,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def list_opportunities(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> Sequence[OpportunityRecord]:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                rows = await s.list_opportunities(outcome_id=outcome_id)
                return [
                    OpportunityRecord(
                        opportunity_id=UUID(r["opportunity_id"]),
                        name=r["name"],
                        current_gate_id=(
                            UUID(r["current_gate_id"])
                            if r.get("current_gate_id") else None
                        ),
                        provenance_origin=r["provenance_origin"],
                        proof_state=r["proof_state"],
                        unit_count=r["unit_count"],
                        source=r.get("source"),
                        status=r.get("status") or "live",
                        closed_reason=r.get("closed_reason"),
                        closed_at=r.get("closed_at"),
                    )
                    for r in rows
                ]
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def set_outcome_disposition(
        self, *, tenant_context: TenantContext, outcome_id: UUID,
        moat: int, pipeline: int, market: int, parked: int,
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.set_outcome_disposition(
                    outcome_id=outcome_id, moat=moat, pipeline=pipeline,
                    market=market, parked=parked,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def close_opportunity(
        self, *, tenant_context: TenantContext, opportunity_id: UUID,
        closed_reason: str,
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.close_opportunity(
                    opportunity_id=opportunity_id, closed_reason=closed_reason
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def reopen_opportunity(
        self, *, tenant_context: TenantContext, opportunity_id: UUID
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.reopen_opportunity(opportunity_id=opportunity_id)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def attach_unit_to_opportunity(
        self, *, tenant_context: TenantContext, unit_id: UUID, opportunity_id: UUID
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.attach_unit_to_opportunity(
                    unit_id=unit_id, opportunity_id=opportunity_id
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def clear_opportunity_units(
        self, *, tenant_context: TenantContext, opportunity_id: UUID
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.clear_opportunity_units(opportunity_id=opportunity_id)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def set_element_gate(
        self,
        *,
        tenant_context: TenantContext,
        element_kind: str,
        element_id: UUID,
        gate_id: UUID,
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.set_element_gate(
                    element_kind=element_kind,
                    element_id=element_id,
                    gate_id=gate_id,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def delete_authored_edge(
        self,
        *,
        tenant_context: TenantContext,
        edge_type: str,
        source_kind: str,
        source_id: UUID,
        target_kind: str,
        target_id: UUID,
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.delete_authored_edge(
                    edge_type=edge_type,
                    source_kind=source_kind,
                    source_id=source_id,
                    target_kind=target_kind,
                    target_id=target_id,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def set_authored_outcome(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        expected_outcome: str,
        provenance_origin: str,
        proof_state: str,
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.set_authored_outcome(
                    outcome_id=outcome_id,
                    expected_outcome=expected_outcome,
                    provenance_origin=provenance_origin,
                    proof_state=proof_state,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def accept_authored_outcome(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.accept_authored_outcome(outcome_id=outcome_id)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def clear_authored_outcome(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.clear_authored_outcome(outcome_id=outcome_id)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def merge_authored_edge(
        self,
        *,
        tenant_context: TenantContext,
        edge_type: str,
        source_kind: str,
        source_id: UUID,
        target_kind: str,
        target_id: UUID,
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.merge_authored_edge(
                    edge_type=edge_type,
                    source_kind=source_kind,
                    source_id=source_id,
                    target_kind=target_kind,
                    target_id=target_id,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def read_authored_cdd(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
    ) -> AuthoredCddRecord:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.read_authored_cdd(outcome_id=outcome_id)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def set_authored_proof_state(
        self,
        *,
        tenant_context: TenantContext,
        element_kind: str,
        element_id: UUID,
        proof_state: str,
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.set_authored_proof_state(
                    element_kind=element_kind,
                    element_id=element_id,
                    proof_state=proof_state,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def set_authored_label(
        self,
        *,
        tenant_context: TenantContext,
        element_kind: str,
        element_id: UUID,
        label: str,
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.set_authored_label(
                    element_kind=element_kind,
                    element_id=element_id,
                    label=label,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def delete_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        element_kind: str,
        element_id: UUID,
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.delete_authored_element(
                    element_kind=element_kind, element_id=element_id
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def reclassify_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        from_kind: str,
        to_kind: str,
        element_id: UUID,
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.reclassify_authored_element(
                    from_kind=from_kind, to_kind=to_kind, element_id=element_id
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    # --- UnitGraphPort (D168): the typed work-unit-graph capability --------

    async def replace_units(
        self,
        *,
        tenant_context: TenantContext,
        units: Sequence[UnitWrite],
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.replace_units(units)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def list_units(
        self,
        *,
        tenant_context: TenantContext,
    ) -> Sequence[UnitGraphRecord]:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.list_units()
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def replace_goal_edges(
        self,
        *,
        tenant_context: TenantContext,
        edges: Sequence[GoalEdgeWrite],
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.replace_goal_edges(edges)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def list_goal_edges(
        self,
        *,
        tenant_context: TenantContext,
    ) -> Sequence[GoalEdgeRecord]:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.list_goal_edges()
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def replace_element_evidence(
        self,
        *,
        tenant_context: TenantContext,
        evidence: Sequence[ElementEvidenceWrite],
    ) -> None:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                await s.replace_element_evidence(evidence)
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def list_element_evidence(
        self,
        *,
        tenant_context: TenantContext,
    ) -> Sequence[ElementEvidenceRecord]:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.list_element_evidence()
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def list_user_owned_unit_ids(
        self, *, tenant_context: TenantContext
    ) -> set[UUID]:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.list_user_owned_unit_ids()
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def list_clustered_unit_ids(
        self, *, tenant_context: TenantContext
    ) -> set[UUID]:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.list_clustered_unit_ids()
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def unlink_element_evidence(
        self,
        *,
        tenant_context: TenantContext,
        unit_id: UUID,
        element_kind: str,
        element_id: UUID,
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.unlink_element_evidence(
                    unit_id=unit_id, element_kind=element_kind,
                    element_id=element_id,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e

    async def relink_element_evidence(
        self,
        *,
        tenant_context: TenantContext,
        unit_id: UUID,
        from_kind: str,
        from_element_id: UUID,
        to_kind: str,
        to_element_id: UUID,
    ) -> bool:
        try:
            async with TenantScopedNeo4jSession(self._driver, tenant_context) as s:
                return await s.relink_element_evidence(
                    unit_id=unit_id, from_kind=from_kind,
                    from_element_id=from_element_id, to_kind=to_kind,
                    to_element_id=to_element_id,
                )
        except _RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryError(str(e)) from e
        except _NON_RETRYABLE_DRIVER_EXC as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
        except Neo4jError as e:
            raise GraphRepositoryConfigurationError(str(e)) from e
