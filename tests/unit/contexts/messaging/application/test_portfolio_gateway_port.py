"""Unit tests for the PortfolioGateway consumer port DTOs (S46)."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from contexts.messaging.application.ports.portfolio_gateway import (
    CaseSummary,
    CaseWriteOutcome,
    DataPointSummary,
    DataPointWriteOutcome,
    PortfolioGateway,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles


def _actor() -> ActorContext:
    tenant = TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant,
        actor_id="cli-operator",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _MinimalGateway:
    """A minimal structural PortfolioGateway used to lock the port shape."""

    async def find_cases(self, *, actor: ActorContext) -> tuple[CaseSummary, ...]:
        return (CaseSummary(case_id=uuid4(), title="Q3 review"),)

    async def find_data_points(
        self, *, actor: ActorContext
    ) -> tuple[DataPointSummary, ...]:
        return ()

    async def create_case(
        self, *, actor: ActorContext, raw_text: str, title: str
    ) -> CaseWriteOutcome:
        return CaseWriteOutcome(
            case_id=uuid4(), intake_id=uuid4(), title=title
        )

    async def create_data_point(
        self,
        *,
        actor: ActorContext,
        raw_text: str,
        case_id: Any,
        data_point_type: str,
        value: dict[str, Any],
    ) -> DataPointWriteOutcome:
        return DataPointWriteOutcome(
            data_point_id=uuid4(),
            case_id=case_id,
            intake_id=uuid4(),
            assertion_ids=(uuid4(),),
        )

    async def revise_data_point(
        self,
        *,
        actor: ActorContext,
        raw_text: str,
        data_point_id: Any,
        value: dict[str, Any],
    ) -> DataPointWriteOutcome:
        return DataPointWriteOutcome(
            data_point_id=data_point_id,
            case_id=uuid4(),
            intake_id=uuid4(),
            assertion_ids=(uuid4(), uuid4()),
        )


def test_data_point_write_outcome_defaults_assertion_ids_empty() -> None:
    outcome = DataPointWriteOutcome(
        data_point_id=uuid4(), case_id=uuid4(), intake_id=uuid4()
    )
    assert outcome.assertion_ids == ()


def test_minimal_gateway_satisfies_the_port() -> None:
    gateway: PortfolioGateway = _MinimalGateway()
    actor = _actor()

    cases = asyncio.run(gateway.find_cases(actor=actor))
    assert cases[0].title == "Q3 review"

    created = asyncio.run(
        gateway.create_case(actor=actor, raw_text="add Q3 review", title="Q3")
    )
    assert isinstance(created, CaseWriteOutcome)
    assert created.title == "Q3"

    revised = asyncio.run(
        gateway.revise_data_point(
            actor=actor,
            raw_text="change it",
            data_point_id=created.case_id,
            value={"text": "new"},
        )
    )
    assert len(revised.assertion_ids) == 2
