"""Unit tests for the ManualEntryCell — first ConversationFlow implementer (S46, S47).

S47 adds the confidence-aware three-case discipline (D134) and
PendingClarification multi-turn state. The existing S46 tests run
at high confidence (Case 1: proceed) and the new tests cover Case 2
(medium → PendingClarification), Case 3 (low / parse-failure →
generic clarification), and the multi-turn confirmation /
cancellation flow.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

from contexts.audit.domain.events import AuditEvent
from contexts.messaging.application.cell_response import CellResponse
from contexts.messaging.application.manual_entry_cell import ManualEntryCell
from contexts.messaging.application.ports.portfolio_gateway import (
    CaseSummary,
    CaseWriteOutcome,
    DataPointSummary,
    DataPointWriteOutcome,
)
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
    PendingClarificationStatus,
)
from shared_kernel import (
    ActorContext,
    ConfidenceThresholds,
    ConversationClosure,
    ConversationInput,
    ConversationInvocation,
    LatencyTier,
    StructuredOutputParseFailure,
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
    """Returns a preset extraction with a configurable confidence."""

    def __init__(
        self,
        value: dict[str, Any],
        *,
        confidence: float | None = 0.95,
        raises: Exception | None = None,
    ) -> None:
        self._value = value
        self._confidence = confidence
        self._raises = raises
        self.requests: list[Any] = []

    async def generate_structured(
        self, request: Any
    ) -> StructuredOutputResponse[dict[str, Any]]:
        self.requests.append(request)
        if self._raises is not None:
            raise self._raises
        return StructuredOutputResponse(
            value=self._value,
            confidence=self._confidence,
            provider_metadata={},
        )


class _FakeConfidenceCalculator:
    """Reads ``response.confidence`` directly (mirrors self-reported)."""

    def compute(self, *, request: Any, response: Any) -> float:
        return float(response.confidence) if response.confidence is not None else 0.5


class _RecordingThresholdResolver:
    """Records ``resolve`` calls; returns the configured pair (S47 addendum)."""

    def __init__(
        self, *, high: float = 0.8, medium: float = 0.5
    ) -> None:
        self._thresholds = ConfidenceThresholds(high=high, medium=medium)
        self.calls: list[str | None] = []

    def resolve(
        self, operation_class: str | None = None
    ) -> ConfidenceThresholds:
        self.calls.append(operation_class)
        return self._thresholds


class _FakePendingRepo:
    def __init__(self) -> None:
        self.pendings: dict[UUID, PendingClarification] = {}

    async def save(self, *, tenant_context, pending) -> None:
        self.pendings[pending.id] = pending

    async def update_status(self, *, tenant_context, pending) -> None:
        self.pendings[pending.id] = pending

    async def get_by_id(self, *, tenant_context, pending_id):
        return self.pendings.get(pending_id)

    async def get_active_for_user(self, *, tenant_context, user_id):
        for p in self.pendings.values():
            if (
                str(p.tenant_id) == tenant_context.tenant_id
                and p.user_id == user_id
                and p.status is PendingClarificationStatus.PENDING
            ):
                return p
        return None


class _FakePendingReader:
    def __init__(self, repo: _FakePendingRepo) -> None:
        self._repo = repo

    async def get_active(self, *, tenant_id: UUID, user_id: str):
        for p in self._repo.pendings.values():
            if (
                p.tenant_id == tenant_id
                and p.user_id == user_id
                and p.status is PendingClarificationStatus.PENDING
            ):
                return p
        return None


class _FakeAuditPort:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event


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


def _cell(
    extraction: dict[str, Any] | _FakeStructuredOutput,
    gateway: _FakeGateway,
    *,
    confidence: float | None = 0.95,
    raises: Exception | None = None,
    high_cutoff: float = 0.8,
    medium_cutoff: float = 0.5,
    pending_repo: _FakePendingRepo | None = None,
    threshold_resolver: _RecordingThresholdResolver | None = None,
) -> ManualEntryCell:
    structured_output = (
        extraction
        if isinstance(extraction, _FakeStructuredOutput)
        else _FakeStructuredOutput(
            extraction, confidence=confidence, raises=raises
        )
    )
    repo = pending_repo if pending_repo is not None else _FakePendingRepo()
    resolver = (
        threshold_resolver
        if threshold_resolver is not None
        else _RecordingThresholdResolver(
            high=high_cutoff, medium=medium_cutoff
        )
    )
    return ManualEntryCell(
        structured_output_port=structured_output,
        portfolio_gateway=gateway,
        actor=_actor(),
        confidence_calculator=_FakeConfidenceCalculator(),
        threshold_resolver=resolver,
        pending_clarification_reader=_FakePendingReader(repo),
        pending_clarification_repository=repo,
        audit_port=_FakeAuditPort(),
    )


def _turn_once(cell: ManualEntryCell, text: str):
    async def _drive():
        state = await cell.open(
            ConversationInvocation(purpose="manual_entry", actor_id="op")
        )
        return await cell.turn(state, ConversationInput(text=text))

    return asyncio.run(_drive())


# --- Case 1: high confidence (existing S46 behaviour) -----------------


def test_open_returns_fresh_state() -> None:
    state = asyncio.run(
        _cell(_extraction(), _FakeGateway()).open(
            ConversationInvocation(purpose="manual_entry", actor_id="op")
        )
    )
    assert state.turn_count == 0
    assert state.is_open is True


def test_create_case_intent_high_confidence_proceeds() -> None:
    gateway = _FakeGateway()
    cell = _cell(
        _extraction(intent_type="create_case", title="Q3 portfolio review"),
        gateway,
    )
    state = _turn_once(cell, "start a case for the Q3 portfolio review")

    assert len(gateway.created_cases) == 1
    response: CellResponse = state.payload["cell_response"]
    assert "Recorded a new case" in response.text
    assert state.payload["confidence_band"] == "high"
    assert len(response.cited_artefacts) == 1


def test_add_data_point_high_confidence_resolves_and_creates() -> None:
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
    response: CellResponse = state.payload["cell_response"]
    assert response.has_citations


def test_revise_data_point_high_confidence_resolves_and_revises() -> None:
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
    response: CellResponse = state.payload["cell_response"]
    assert response.text == "Which case did you mean?"
    assert not response.has_citations


# --- Case 2: medium confidence (new at S47) ---------------------------


def test_create_case_medium_confidence_creates_pending_and_clarifies() -> None:
    """D134 Case 2: medium confidence proposes the action as a question."""
    gateway = _FakeGateway()
    repo = _FakePendingRepo()
    cell = _cell(
        _extraction(intent_type="create_case", title="Q3 portfolio review"),
        gateway,
        confidence=0.6,
        pending_repo=repo,
    )
    state = _turn_once(cell, "start a case for the Q3 portfolio review")

    # No portfolio write at Case 2.
    assert gateway.created_cases == []
    # The cell asks a shape-aware clarification phrased as a question.
    response: CellResponse = state.payload["cell_response"]
    assert "Is that right?" in response.text
    assert "Q3 portfolio review" in response.text
    assert state.payload["confidence_band"] == "medium"
    # A PendingClarification persists for the operator.
    pendings = list(repo.pendings.values())
    assert len(pendings) == 1
    assert pendings[0].status is PendingClarificationStatus.PENDING
    assert pendings[0].user_id == "twilio-webhook"


def test_add_data_point_medium_confidence_creates_pending() -> None:
    gateway = _FakeGateway()
    repo = _FakePendingRepo()
    cell = _cell(
        _extraction(
            intent_type="add_data_point",
            case_reference="the Q3 review",
            data_point_type="GOAL",
            value_text="ship Wave 1",
        ),
        gateway,
        confidence=0.6,
        pending_repo=repo,
    )
    state = _turn_once(cell, "add a goal")

    assert gateway.created_data_points == []
    response: CellResponse = state.payload["cell_response"]
    assert "Is that right?" in response.text
    assert state.payload["confidence_band"] == "medium"
    assert len(repo.pendings) == 1


# --- Case 3: low confidence and parse failure ------------------------


def test_low_confidence_returns_generic_clarification() -> None:
    """D134 Case 3: below medium cut-off renders generic clarification."""
    gateway = _FakeGateway()
    repo = _FakePendingRepo()
    cell = _cell(
        _extraction(intent_type="create_case", title="something"),
        gateway,
        confidence=0.2,
        pending_repo=repo,
    )
    state = _turn_once(cell, "do something")

    assert gateway.created_cases == []
    assert repo.pendings == {}
    assert state.payload["confidence_band"] == "low"
    response: CellResponse = state.payload["cell_response"]
    assert not response.has_citations


def test_parse_failure_routes_to_case_3() -> None:
    """D130 extension: StructuredOutputParseFailure routes to Case 3."""
    gateway = _FakeGateway()
    repo = _FakePendingRepo()
    cell = _cell(
        _FakeStructuredOutput(
            _extraction(),
            raises=StructuredOutputParseFailure(
                "model produced bad JSON",
                raw_content="not json",
            ),
        ),
        gateway,
        pending_repo=repo,
    )
    state = _turn_once(cell, "do the thing")

    assert gateway.created_cases == []
    assert repo.pendings == {}
    assert state.payload["confidence_band"] == "parse_failure"
    response: CellResponse = state.payload["cell_response"]
    assert "Could you say a little more" in response.text


# --- Multi-turn: confirmation resolves and executes -------------------


def test_confirmation_resolves_pending_and_executes() -> None:
    """A confirming reply resolves the pending and runs the action."""
    gateway = _FakeGateway()
    repo = _FakePendingRepo()
    # Turn 1: medium confidence creates the pending.
    cell = _cell(
        _extraction(intent_type="create_case", title="Q3 portfolio review"),
        gateway,
        confidence=0.6,
        pending_repo=repo,
    )

    async def _drive():
        opened = await cell.open(
            ConversationInvocation(purpose="manual_entry", actor_id="op")
        )
        first = await cell.turn(
            opened,
            ConversationInput(
                text="start a case for the Q3 portfolio review"
            ),
        )
        # Turn 2 with a new cell construction (per-request shape).
        # High-confidence is irrelevant — the pending dictates flow.
        confirm_cell = _cell(
            _extraction(intent_type="unclear"),
            gateway,
            confidence=0.0,
            pending_repo=repo,
        )
        second = await confirm_cell.turn(
            first, ConversationInput(text="yes")
        )
        return first, second

    first, second = asyncio.run(_drive())

    assert first.payload["confidence_band"] == "medium"
    # Case was created on the confirmation turn.
    assert len(gateway.created_cases) == 1
    assert second.payload["confidence_band"] == "confirmed_pending"
    response: CellResponse = second.payload["cell_response"]
    assert "Recorded a new case" in response.text
    # The pending transitioned to RESOLVED.
    pending = list(repo.pendings.values())[0]
    assert pending.status is PendingClarificationStatus.RESOLVED


def test_cancellation_resolves_pending_and_falls_through() -> None:
    """A correcting reply cancels the pending and runs as a fresh turn."""
    gateway = _FakeGateway()
    repo = _FakePendingRepo()
    cell = _cell(
        _extraction(intent_type="create_case", title="Q3 portfolio review"),
        gateway,
        confidence=0.6,
        pending_repo=repo,
    )

    async def _drive():
        opened = await cell.open(
            ConversationInvocation(purpose="manual_entry", actor_id="op")
        )
        first = await cell.turn(
            opened,
            ConversationInput(
                text="start a case for the Q3 portfolio review"
            ),
        )
        cancel_cell = _cell(
            _extraction(intent_type="unclear", clarification="?"),
            gateway,
            confidence=0.0,  # falls through to Case 3 generic
            pending_repo=repo,
        )
        second = await cancel_cell.turn(
            first, ConversationInput(text="no")
        )
        return first, second

    first, second = asyncio.run(_drive())

    # The original proposal did not execute on the cancel.
    assert gateway.created_cases == []
    # The pending transitioned to RESOLVED with cancelled.
    pending = list(repo.pendings.values())[0]
    assert pending.status is PendingClarificationStatus.RESOLVED


# --- Existing scaffolding tests carry through ------------------------


def test_turn_advances_count_and_keeps_conversation_id() -> None:
    cell = _cell(
        _extraction(intent_type="unclear", clarification="?"),
        _FakeGateway(),
        confidence=0.95,
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


# --- S47 addendum: ThresholdResolver consumption ---------------------


def test_cell_consults_threshold_resolver_at_turn() -> None:
    """S47 addendum: the cell consults the ThresholdResolver port per turn.

    The resolver is consulted on the band-dispatching path (anything
    other than an extracted UnclearIntent, which routes to Case 3
    without needing the cut-offs). High-confidence create_case
    exercises the band check.
    """
    resolver = _RecordingThresholdResolver()
    cell = _cell(
        _extraction(intent_type="create_case", title="Q3 review"),
        _FakeGateway(),
        confidence=0.95,
        threshold_resolver=resolver,
    )
    _turn_once(cell, "start a case for the Q3 review")
    assert resolver.calls == [None]


def test_cell_source_carries_no_numeric_threshold_literals() -> None:
    """The cell source consumes thresholds via the port; no literals.

    A grep-style structural check on the cell module — the addendum's
    discipline is that ``confidence_high_cutoff`` / ``_medium_cutoff``
    numeric literals do not appear in the cell source. Configuration
    values live at ``padhanam/config/messaging.py``; the cell receives
    them through the resolver port.
    """
    import inspect
    from contexts.messaging.application import manual_entry_cell

    source = inspect.getsource(manual_entry_cell)
    # The legacy float-cutoff parameters and their default values must
    # be absent. The cell may still mention threshold concepts in
    # docstrings or comments; we forbid the numeric defaults.
    assert "confidence_high_cutoff" not in source
    assert "confidence_medium_cutoff" not in source
    assert "= 0.8" not in source
    assert "= 0.5" not in source


def test_intent_extraction_uses_real_time_tier() -> None:
    port = _FakeStructuredOutput(_extraction(intent_type="unclear"))
    repo = _FakePendingRepo()
    cell = ManualEntryCell(
        structured_output_port=port,
        portfolio_gateway=_FakeGateway(),
        actor=_actor(),
        confidence_calculator=_FakeConfidenceCalculator(),
        threshold_resolver=_RecordingThresholdResolver(),
        pending_clarification_reader=_FakePendingReader(repo),
        pending_clarification_repository=repo,
        audit_port=_FakeAuditPort(),
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
