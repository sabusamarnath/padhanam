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
    OutcomeGraphRecord,
)
from contexts.ingestion.ports.unit_graph_port import (
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
