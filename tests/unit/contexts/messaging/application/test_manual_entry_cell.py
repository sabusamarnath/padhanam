"""Unit tests for the ManualEntryCell — first ConversationFlow implementer (S46)."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from contexts.messaging.application.cell_response import CellResponse
from contexts.messaging.application.manual_entry_cell import ManualEntryCell
from contexts.messaging.application.ports.portfolio_gateway import (
    CaseSummary,
    CaseWriteOutcome,
    DataPointSummary,
    DataPointWriteOutcome,
)
from shared_kernel import (
    ActorContext,
    ConversationClosure,
    ConversationInput,
    ConversationInvocation,
    LatencyTier,
    StructuredOutputResponse,
    TenantContext,
)
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
        actor_id="twilio-webhook",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _extraction(**fields: str) -> dict[str, Any]:
    """Build a structured-output extraction object with empty defaults."""
    base = {
        "intent_type": "unclear",
        "title": "",
        "case_reference": "",
        "data_point_type": "",
        "data_point_reference": "",
        "value_text": "",
        "clarification": "",
    }
    base.update(fields)
    return base


class _FakeStructuredOutput:
    def __init__(self, value: dict[str, Any]) -> None:
        self._value = value
        self.requests: list[Any] = []

    async def generate_structured(
        self, request: Any
    ) -> StructuredOutputResponse[dict[str, Any]]:
        self.requests.append(request)
        return StructuredOutputResponse(
            value=self._value, confidence=None, provider_metadata={}
        )


class _FakeGateway:
    def __init__(
        self,
        *,
        cases: tuple[CaseSummary, ...] = (),
        data_points: tuple[DataPointSummary, ...] = (),
    ) -> None:
        self._cases = cases
        self._data_points = data_points
        self.created_cases: list[tuple[str, str]] = []
        self.created_data_points: list[tuple[Any, str, dict[str, Any]]] = []
        self.revised: list[tuple[Any, dict[str, Any]]] = []

    async def find_cases(self, *, actor: ActorContext):
        return self._cases

    async def find_data_points(self, *, actor: ActorContext):
        return self._data_points

    async def create_case(self, *, actor, raw_text, title):
        self.created_cases.append((raw_text, title))
        return CaseWriteOutcome(
            case_id=uuid4(), intake_id=uuid4(), title=title
        )

    async def create_data_point(
        self, *, actor, raw_text, case_id, data_point_type, value
    ):
        self.created_data_points.append((case_id, data_point_type, value))
        return DataPointWriteOutcome(
            data_point_id=uuid4(),
            case_id=case_id,
            intake_id=uuid4(),
            assertion_ids=(uuid4(),),
        )

    async def revise_data_point(self, *, actor, raw_text, data_point_id, value):
        self.revised.append((data_point_id, value))
        return DataPointWriteOutcome(
            data_point_id=data_point_id,
            case_id=uuid4(),
            intake_id=uuid4(),
            assertion_ids=(uuid4(), uuid4()),
        )


def _cell(extraction: dict[str, Any], gateway: _FakeGateway) -> ManualEntryCell:
    return ManualEntryCell(
        structured_output_port=_FakeStructuredOutput(extraction),
        portfolio_gateway=gateway,
        actor=_actor(),
    )


def _turn_once(cell: ManualEntryCell, text: str):
    async def _drive():
        state = await cell.open(
            ConversationInvocation(purpose="manual_entry", actor_id="op")
        )
        return await cell.turn(state, ConversationInput(text=text))

    return asyncio.run(_drive())


def test_open_returns_fresh_state() -> None:
    state = asyncio.run(
        _cell(_extraction(), _FakeGateway()).open(
            ConversationInvocation(purpose="manual_entry", actor_id="op")
        )
    )
    assert state.turn_count == 0
    assert state.is_open is True


def test_create_case_intent_drives_create_and_cites() -> None:
    gateway = _FakeGateway()
    cell = _cell(
        _extraction(intent_type="create_case", title="Q3 portfolio review"),
        gateway,
    )
    state = _turn_once(cell, "start a case for the Q3 portfolio review")

    assert gateway.created_cases == [
        ("start a case for the Q3 portfolio review", "Q3 portfolio review")
    ]
    response: CellResponse = state.payload["cell_response"]
    assert "Recorded a new case" in response.text
    assert len(response.cited_artefacts) == 1
    assert len(response.cited_intake_records) == 1
    assert response.cited_audit_events == ()
    assert "Q3 portfolio review" in state.payload["response_text"]


def test_add_data_point_resolves_case_and_creates() -> None:
    case = CaseSummary(case_id=uuid4(), title="Q3 portfolio review")
    gateway = _FakeGateway(cases=(case,))
    cell = _cell(
        _extraction(
            intent_type="add_data_point",
            case_reference="the Q3 review",
            data_point_type="GOAL",
            value_text="ship Wave 1 by end of May",
        ),
        gateway,
    )
    state = _turn_once(cell, "add a goal to the Q3 review: ship Wave 1")

    assert len(gateway.created_data_points) == 1
    case_id, dp_type, value = gateway.created_data_points[0]
    assert case_id == case.case_id
    assert dp_type == "GOAL"
    assert value == {"text": "ship Wave 1 by end of May"}
    response: CellResponse = state.payload["cell_response"]
    assert len(response.cited_artefacts) == 1


def test_add_data_point_ambiguous_returns_clarification() -> None:
    gateway = _FakeGateway(
        cases=(
            CaseSummary(case_id=uuid4(), title="Q3 review meeting"),
            CaseSummary(case_id=uuid4(), title="Q3 review planning"),
        )
    )
    cell = _cell(
        _extraction(
            intent_type="add_data_point",
            case_reference="the Q3 review",
            data_point_type="STATUS",
            value_text="on track",
        ),
        gateway,
    )
    state = _turn_once(cell, "add a status to the Q3 review")

    assert gateway.created_data_points == []
    response: CellResponse = state.payload["cell_response"]
    assert not response.has_citations
    assert "More than one" in response.text


def test_add_data_point_no_match_returns_clarification() -> None:
    gateway = _FakeGateway(
        cases=(CaseSummary(case_id=uuid4(), title="annual planning"),)
    )
    cell = _cell(
        _extraction(
            intent_type="add_data_point",
            case_reference="the hiring pipeline",
            data_point_type="GOAL",
            value_text="close two roles",
        ),
        gateway,
    )
    state = _turn_once(cell, "add a goal to the hiring pipeline")

    assert gateway.created_data_points == []
    response: CellResponse = state.payload["cell_response"]
    assert "could not find" in response.text


def test_revise_data_point_resolves_and_revises() -> None:
    dp = DataPointSummary(
        data_point_id=uuid4(),
        case_id=uuid4(),
        data_point_type="GOAL",
        label="ship Wave 1 by end of May",
    )
    gateway = _FakeGateway(data_points=(dp,))
    cell = _cell(
        _extraction(
            intent_type="revise_data_point",
            data_point_reference="the Wave 1 ship goal",
            value_text="ship Wave 1 by mid-June",
        ),
        gateway,
    )
    state = _turn_once(cell, "revise the Wave 1 ship goal to mid-June")

    assert len(gateway.revised) == 1
    data_point_id, value = gateway.revised[0]
    assert data_point_id == dp.data_point_id
    assert value == {"text": "ship Wave 1 by mid-June"}
    response: CellResponse = state.payload["cell_response"]
    assert response.cited_artefacts == (dp.data_point_id,)


def test_unclear_intent_returns_clarification_without_touching_gateway() -> None:
    gateway = _FakeGateway()
    cell = _cell(
        _extraction(
            intent_type="unclear",
            clarification="Which case did you mean?",
        ),
        gateway,
    )
    state = _turn_once(cell, "do the thing")

    assert gateway.created_cases == []
    assert gateway.created_data_points == []
    response: CellResponse = state.payload["cell_response"]
    assert response.text == "Which case did you mean?"
    assert not response.has_citations


def test_turn_advances_count_and_keeps_conversation_id() -> None:
    cell = _cell(
        _extraction(intent_type="unclear", clarification="?"), _FakeGateway()
    )

    async def _drive():
        opened = await cell.open(
            ConversationInvocation(purpose="manual_entry", actor_id="op")
        )
        first = await cell.turn(opened, ConversationInput(text="a"))
        second = await cell.turn(first, ConversationInput(text="b"))
        return opened, first, second

    opened, first, second = asyncio.run(_drive())
    assert (first.turn_count, second.turn_count) == (1, 2)
    assert opened.conversation_id == second.conversation_id


def test_close_returns_terminal_outcome() -> None:
    cell = _cell(_extraction(), _FakeGateway())

    async def _drive():
        opened = await cell.open(
            ConversationInvocation(purpose="manual_entry", actor_id="op")
        )
        return opened, await cell.close(
            opened, ConversationClosure(reason="handled")
        )

    opened, outcome = asyncio.run(_drive())
    assert outcome.conversation_id == opened.conversation_id
    assert outcome.resolution == "handled"


def test_intent_extraction_uses_real_time_tier() -> None:
    port = _FakeStructuredOutput(_extraction(intent_type="unclear"))
    cell = ManualEntryCell(
        structured_output_port=port,
        portfolio_gateway=_FakeGateway(),
        actor=_actor(),
    )
    asyncio.run(
        cell.turn(
            asyncio.run(
                cell.open(
                    ConversationInvocation(
                        purpose="manual_entry", actor_id="op"
                    )
                )
            ),
            ConversationInput(text="hello"),
        )
    )
    assert port.requests[0].latency_tier is LatencyTier.REAL_TIME_REQUIRED
