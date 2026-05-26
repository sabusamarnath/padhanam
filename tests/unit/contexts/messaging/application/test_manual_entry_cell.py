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
from datetime import datetime, timedelta, timezone
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


def _case_summary(
    *,
    title: str,
    case_id: UUID | None = None,
    created_at: datetime | None = None,
    last_activity_at: datetime | None = None,
    data_point_count: int = 0,
) -> CaseSummary:
    """Construct a CaseSummary with sensible test defaults (S50)."""
    now = datetime.now(timezone.utc)
    return CaseSummary(
        case_id=case_id if case_id is not None else uuid4(),
        title=title,
        created_at=created_at if created_at is not None else now,
        last_activity_at=(
            last_activity_at if last_activity_at is not None else now
        ),
        data_point_count=data_point_count,
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
    case = _case_summary(title="Q3 portfolio review")
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


# --- S50: resolver disambiguation on duplicate-title cases -----------


def test_helpers_format_relative_time_across_windows() -> None:
    """The cell's relative-time helper covers the dogfooding window."""
    from contexts.messaging.application.manual_entry_cell import (
        _format_relative_time,
    )

    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    assert _format_relative_time(
        now - timedelta(seconds=30), now=now
    ) == "just now"
    assert _format_relative_time(
        now - timedelta(minutes=5), now=now
    ) == "5m ago"
    assert _format_relative_time(
        now - timedelta(hours=3), now=now
    ) == "3h ago"
    assert _format_relative_time(
        now - timedelta(days=1), now=now
    ) == "1 day ago"
    assert _format_relative_time(
        now - timedelta(days=4), now=now
    ) == "4 days ago"
    # Beyond 30 days flips to absolute date.
    assert _format_relative_time(
        now - timedelta(days=45), now=now
    ) == "2026-04-11"


def test_helpers_case_discriminators_compose_three_signals() -> None:
    """The discriminator tuple carries created / count / last-activity."""
    from contexts.messaging.application.manual_entry_cell import (
        _case_discriminators,
    )

    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    case = _case_summary(
        title="Q3 portfolio review",
        created_at=now - timedelta(days=4),
        last_activity_at=now - timedelta(hours=2),
        data_point_count=3,
    )
    discriminators = _case_discriminators(case, now=now)
    assert discriminators == (
        "created 4 days ago",
        "3 data points",
        "last activity 2h ago",
    )


def test_helpers_case_discriminators_singular_data_point() -> None:
    """Singular "1 data point" prose for the count-of-one edge."""
    from contexts.messaging.application.manual_entry_cell import (
        _case_discriminators,
    )

    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    case = _case_summary(
        title="Q3", created_at=now, last_activity_at=now, data_point_count=1
    )
    discriminators = _case_discriminators(case, now=now)
    assert discriminators[1] == "1 data point"


def test_helpers_parse_positional_selection() -> None:
    """Bare positive integers parse; everything else returns None."""
    from contexts.messaging.application.manual_entry_cell import (
        _parse_positional_selection,
    )

    assert _parse_positional_selection("1") == 1
    assert _parse_positional_selection("  2  ") == 2
    assert _parse_positional_selection("3.") == 3
    assert _parse_positional_selection("12") == 12
    # Non-bare integers fall through.
    assert _parse_positional_selection("yes") is None
    assert _parse_positional_selection("the older one") is None
    assert _parse_positional_selection("1 please") is None
    assert _parse_positional_selection("") is None
    assert _parse_positional_selection("0") is None
    assert _parse_positional_selection("-1") is None


def test_add_data_point_high_confidence_multi_match_creates_resolution_pending() -> None:
    """S50: AMBIGUOUS case resolution at high confidence creates a pending.

    The cell composes a numbered disambiguation question carrying each
    candidate's discriminating signals; PendingClarification persists
    with the candidate id list embedded in proposed_intent; no
    portfolio write happens until the operator selects.
    """
    from contexts.messaging.application.manual_entry_cell import (
        _RESOLUTION_CANDIDATES_KEY,
    )

    now = datetime.now(timezone.utc)
    case_a = _case_summary(
        title="Q3 portfolio review",
        created_at=now - timedelta(days=4),
        last_activity_at=now - timedelta(days=4),
        data_point_count=0,
    )
    case_b = _case_summary(
        title="Q3 portfolio review",
        created_at=now - timedelta(days=2),
        last_activity_at=now - timedelta(hours=2),
        data_point_count=2,
    )
    gateway = _FakeGateway(cases=(case_a, case_b))
    repo = _FakePendingRepo()
    cell = _cell(
        _extraction(
            intent_type="add_data_point",
            case_reference="Q3 portfolio review",
            data_point_type="GOAL",
            value_text="ship Wave 1",
        ),
        gateway,
        confidence=0.95,
        pending_repo=repo,
    )
    state = _turn_once(cell, "add a goal to Q3 portfolio review: ship Wave 1")

    # No portfolio write at the disambiguation turn.
    assert gateway.created_data_points == []
    # Pending persists with the candidates sidecar.
    pendings = list(repo.pendings.values())
    assert len(pendings) == 1
    pending = pendings[0]
    assert pending.status is PendingClarificationStatus.PENDING
    candidates = pending.proposed_intent[_RESOLUTION_CANDIDATES_KEY]
    assert len(candidates) == 2
    candidate_ids = {UUID(c["id"]) for c in candidates}
    assert candidate_ids == {case_a.case_id, case_b.case_id}
    # The clarification phrases as a question and numbers the options.
    response: CellResponse = state.payload["cell_response"]
    assert "Which" in response.text
    assert "1." in response.text and "2." in response.text
    assert "data point" in response.text  # discriminator surfaces
    # No citations on a clarification per D131.
    assert not response.has_citations


def test_positional_reply_resolves_pending_and_executes() -> None:
    """S50: a bare integer reply selects the chosen candidate.

    Verifies that the action runs against the selected case id, the
    pending transitions to RESOLVED, the cited confirmation surfaces
    the chosen case's title, and the confidence band reports the
    resolved-by-selection lineage.
    """
    now = datetime.now(timezone.utc)
    case_a = _case_summary(
        title="Q3 portfolio review",
        created_at=now - timedelta(days=4),
        data_point_count=0,
    )
    case_b = _case_summary(
        title="Q3 portfolio review",
        created_at=now - timedelta(days=2),
        data_point_count=2,
    )
    gateway = _FakeGateway(cases=(case_a, case_b))
    repo = _FakePendingRepo()

    async def _drive():
        cell = _cell(
            _extraction(
                intent_type="add_data_point",
                case_reference="Q3 portfolio review",
                data_point_type="GOAL",
                value_text="ship Wave 1",
            ),
            gateway,
            confidence=0.95,
            pending_repo=repo,
        )
        opened = await cell.open(
            ConversationInvocation(purpose="manual_entry", actor_id="op")
        )
        first = await cell.turn(
            opened,
            ConversationInput(
                text="add a goal to Q3 portfolio review: ship Wave 1"
            ),
        )
        # Turn 2 — operator selects positional "2". Fresh cell
        # construction (per-request shape); extraction shape is
        # irrelevant since the pending dictates the flow.
        select_cell = _cell(
            _extraction(intent_type="unclear"),
            gateway,
            confidence=0.0,
            pending_repo=repo,
        )
        second = await select_cell.turn(first, ConversationInput(text="2"))
        return first, second

    first, second = asyncio.run(_drive())

    assert first.payload["confidence_band"] == "high"
    # The data point was created on the selection turn against case_b's id.
    assert len(gateway.created_data_points) == 1
    chosen_case_id, _data_point_type, _value = gateway.created_data_points[0]
    assert chosen_case_id == case_b.case_id
    # The cited confirmation surfaces the chosen case's title.
    response: CellResponse = second.payload["cell_response"]
    assert "Q3 portfolio review" in response.text
    assert response.has_citations
    assert second.payload["confidence_band"] == "resolved_by_selection"
    # Pending transitioned to RESOLVED.
    pending = list(repo.pendings.values())[0]
    assert pending.status is PendingClarificationStatus.RESOLVED


def test_positional_reply_out_of_range_re_renders_without_resolving() -> None:
    """S50: out-of-range selection keeps the pending and re-renders."""
    now = datetime.now(timezone.utc)
    cases = (
        _case_summary(title="Q3 portfolio review", created_at=now),
        _case_summary(title="Q3 portfolio review", created_at=now),
    )
    gateway = _FakeGateway(cases=cases)
    repo = _FakePendingRepo()

    async def _drive():
        cell = _cell(
            _extraction(
                intent_type="add_data_point",
                case_reference="Q3 portfolio review",
                data_point_type="GOAL",
                value_text="ship Wave 1",
            ),
            gateway,
            confidence=0.95,
            pending_repo=repo,
        )
        opened = await cell.open(
            ConversationInvocation(purpose="manual_entry", actor_id="op")
        )
        first = await cell.turn(
            opened,
            ConversationInput(text="add a goal: ship Wave 1"),
        )
        select_cell = _cell(
            _extraction(intent_type="unclear"),
            gateway,
            confidence=0.0,
            pending_repo=repo,
        )
        second = await select_cell.turn(first, ConversationInput(text="5"))
        return first, second

    first, second = asyncio.run(_drive())

    assert gateway.created_data_points == []
    response: CellResponse = second.payload["cell_response"]
    assert "between 1 and 2" in response.text
    assert second.payload["confidence_band"] == "resolution_out_of_range"
    # Pending stays PENDING for the next try.
    pending = list(repo.pendings.values())[0]
    assert pending.status is PendingClarificationStatus.PENDING


def test_correcting_reply_cancels_resolution_pending() -> None:
    """S50: "no" still cancels a resolution-ambiguity pending."""
    now = datetime.now(timezone.utc)
    cases = (
        _case_summary(title="Q3 portfolio review", created_at=now),
        _case_summary(title="Q3 portfolio review", created_at=now),
    )
    gateway = _FakeGateway(cases=cases)
    repo = _FakePendingRepo()

    async def _drive():
        cell = _cell(
            _extraction(
                intent_type="add_data_point",
                case_reference="Q3 portfolio review",
                data_point_type="GOAL",
                value_text="ship",
            ),
            gateway,
            confidence=0.95,
            pending_repo=repo,
        )
        opened = await cell.open(
            ConversationInvocation(purpose="manual_entry", actor_id="op")
        )
        first = await cell.turn(opened, ConversationInput(text="ship Wave 1"))
        cancel_cell = _cell(
            _extraction(intent_type="unclear", clarification="?"),
            gateway,
            confidence=0.0,
            pending_repo=repo,
        )
        second = await cancel_cell.turn(first, ConversationInput(text="no"))
        return first, second

    first, second = asyncio.run(_drive())

    assert gateway.created_data_points == []
    pending = list(repo.pendings.values())[0]
    assert pending.status is PendingClarificationStatus.RESOLVED  # cancelled


def test_add_data_point_no_match_returns_clarification_no_pending() -> None:
    """S50: NO_MATCH path keeps simpler shape (no pending created)."""
    now = datetime.now(timezone.utc)
    gateway = _FakeGateway(
        cases=(_case_summary(title="annual planning", created_at=now),)
    )
    repo = _FakePendingRepo()
    cell = _cell(
        _extraction(
            intent_type="add_data_point",
            case_reference="hiring pipeline",
            data_point_type="GOAL",
            value_text="raise",
        ),
        gateway,
        confidence=0.95,
        pending_repo=repo,
    )
    state = _turn_once(cell, "add a goal to the hiring pipeline")

    assert gateway.created_data_points == []
    assert repo.pendings == {}
    response: CellResponse = state.payload["cell_response"]
    assert "could not find" in response.text.lower()
