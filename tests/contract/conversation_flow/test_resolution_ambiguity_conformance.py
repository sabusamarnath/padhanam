"""Resolution-ambiguity routing conformance scenario (D139, S51).

D139 commits cross-cutting resolution-ambiguity routing: every
ConversationFlow implementer routes ambiguous resolutions through
D134's PendingClarification rather than picking deterministically or
returning raw candidates. S50 is the first instance (manual entry cell,
duplicate-title cases); S51 is the second (audit-conversation, title-
ambiguous case references at FindByCase).

The scenario fires against test fixtures providing multi-match
conditions at each implementer's resolver step. Per-implementer setup
differs (the multi-match-triggering shape is implementer-specific), so
the scenario uses per-implementer factory functions exposed by the
registration modules.

Per S49 structural-test SSOT binding: the D139 architectural
commitment admits this structural test; the test lands at the
commitment's commit (S51 commit 1 commits the charter; S51 commit 5
commits the structural test).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from contexts.audit_conversation.application.ports.portfolio_case_lookup import (
    AuditCaseSummary,
)
from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
)
from contexts.messaging.application.manual_entry_cell import ManualEntryCell
from contexts.audit_conversation.application.cell import (
    AuditConversationCell,
)

from shared_kernel import (
    ActorContext,
    ConfidenceThresholds,
    ConversationInput,
    ConversationInvocation,
    StructuredOutputResponse,
    TenantContext,
)
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

from tests.contract.conversation_flow.test_audit_conversation_conversation_flow import (
    _StubAuditPort as _AuditConvAuditPort,
    _StubAuditReader as _AuditConvAuditReader,
    _StubConfidenceCalculator as _AuditConvConfidenceCalculator,
    _StubPendingReader as _AuditConvPendingReader,
    _StubPendingRepo as _AuditConvPendingRepo,
    _StubStructuredOutput as _AuditConvStructuredOutput,
    _StubCaseLookup as _AuditConvCaseLookup,
)


# --------------------------------------------------------- manual_entry_cell

class _MEStubStructuredOutput:
    """Returns an AddDataPointIntent extraction at high confidence."""

    async def generate_structured(self, request: Any) -> Any:
        return StructuredOutputResponse(
            value={
                "intent_type": "add_data_point",
                "case_reference": "Q3 portfolio review",
                "data_point_type": "GOAL",
                "value_text": "ship Wave 1",
                "confidence": 0.95,
            },
            confidence=0.95,
            provider_metadata={},
        )


class _MEStubGateway:
    """Two cases share the same title to trigger duplicate-title ambiguity."""

    def __init__(self) -> None:
        from contexts.messaging.application.ports.portfolio_gateway import (
            CaseSummary,
        )
        now = datetime(2026, 5, 26, 14, 30, tzinfo=timezone.utc)
        self._cases = (
            CaseSummary(
                case_id=uuid4(),
                title="Q3 portfolio review",
                created_at=now,
                last_activity_at=now,
                data_point_count=2,
            ),
            CaseSummary(
                case_id=uuid4(),
                title="Q3 portfolio review",
                created_at=now,
                last_activity_at=now,
                data_point_count=2,
            ),
        )

    async def find_cases(self, *, actor: ActorContext) -> Any:
        return self._cases

    async def find_data_points(self, *, actor: ActorContext) -> Any:
        return ()

    async def create_case(self, **_kwargs: Any) -> Any:
        raise AssertionError("must not write portfolio state on ambiguous path")

    async def create_data_point(self, **_kwargs: Any) -> Any:
        raise AssertionError("must not write portfolio state on ambiguous path")

    async def revise_data_point(self, **_kwargs: Any) -> Any:
        raise AssertionError("must not write portfolio state on ambiguous path")


class _MEStubConfidenceCalc:
    def compute(self, *, request: Any, response: Any) -> float:
        return 0.95


class _MEStubPendingReader:
    async def get_active(self, *, tenant_id: Any, user_id: str) -> Any:
        return None


class _MEStubPendingRepo:
    def __init__(self) -> None:
        self.saved: list[Any] = []

    async def save(self, *, tenant_context: Any, pending: Any) -> None:
        self.saved.append(pending)

    async def update_status(
        self, *, tenant_context: Any, pending: Any
    ) -> None:
        return None

    async def get_by_id(
        self, *, tenant_context: Any, pending_id: Any
    ) -> Any:
        return None

    async def get_active_for_user(
        self, *, tenant_context: Any, user_id: str
    ) -> Any:
        return None


class _MEStubAuditPort:
    async def emit(self, event: Any) -> Any:
        return event


def _me_harness_actor() -> ActorContext:
    tenant = TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant,
        actor_id="resolution-ambiguity-harness",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _build_manual_entry_with_ambiguous_resolution() -> tuple[
    ManualEntryCell, _MEStubPendingRepo
]:
    repo = _MEStubPendingRepo()
    cell = ManualEntryCell(
        structured_output_port=_MEStubStructuredOutput(),
        portfolio_gateway=_MEStubGateway(),
        actor=_me_harness_actor(),
        confidence_calculator=_MEStubConfidenceCalc(),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        pending_clarification_reader=_MEStubPendingReader(),
        pending_clarification_repository=repo,
        audit_port=_MEStubAuditPort(),
        originating_intake_id=uuid4(),
    )
    return cell, repo


# ----------------------------------------------------- audit_conversation_cell


def _ac_harness_actor() -> ActorContext:
    tenant = TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a002",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a002",
    )
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant,
        actor_id="resolution-ambiguity-harness",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _build_audit_conversation_with_ambiguous_resolution() -> tuple[
    AuditConversationCell, _AuditConvPendingRepo
]:
    case_a = AuditCaseSummary(case_id=uuid4(), title="Q3 portfolio review")
    case_b = AuditCaseSummary(case_id=uuid4(), title="Q3 portfolio review")
    repo = _AuditConvPendingRepo()
    cell = AuditConversationCell(
        structured_output_port=_AuditConvStructuredOutput(
            value={
                "intent_class": "find_by_case",
                "case_reference": "Q3 portfolio review",
                "confidence": 0.95,
            }
        ),
        audit_event_reader=_AuditConvAuditReader(),
        portfolio_case_lookup=_AuditConvCaseLookup(cases=(case_a, case_b)),
        actor=_ac_harness_actor(),
        confidence_calculator=_AuditConvConfidenceCalculator(),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        pending_clarification_reader=_AuditConvPendingReader(),
        pending_clarification_repository=repo,
        audit_port=_AuditConvAuditPort(),
        originating_intake_id=uuid4(),
        clock=lambda: datetime(2026, 5, 26, 14, 30, tzinfo=timezone.utc),
    )
    return cell, repo


# -------------------------------------------------------------- scenarios


# Per-implementer factory + multi-match-triggering input. Adding a new
# implementer adds an entry here.
_AMBIGUOUS_RESOLUTION_FACTORIES = {
    "manual_entry_cell": (
        _build_manual_entry_with_ambiguous_resolution,
        ConversationInvocation(
            purpose="manual_entry", actor_id="resolution-ambiguity-harness"
        ),
        ConversationInput(
            text="add a goal to the Q3 portfolio review: ship Wave 1"
        ),
    ),
    "audit_conversation_cell": (
        _build_audit_conversation_with_ambiguous_resolution,
        ConversationInvocation(
            purpose="audit_query", actor_id="resolution-ambiguity-harness"
        ),
        ConversationInput(text="show audit events for the Q3 portfolio review"),
    ),
}


def test_resolution_ambiguity_routes_through_pending_clarification(
    conversation_flow_implementer: Any,
) -> None:
    """Every implementer routes resolution-ambiguity through D134's
    PendingClarification rather than picking deterministically.

    For each registered implementer, build a multi-match condition,
    drive open + turn, and assert the PendingClarification repository
    received a save carrying the resolution_candidates sidecar at
    ``proposed_intent[_RESOLUTION_CANDIDATES_KEY]`` per the D139
    structural commitment.
    """
    name = conversation_flow_implementer.name
    if name not in _AMBIGUOUS_RESOLUTION_FACTORIES:
        # A registered implementer without an ambiguous-resolution
        # factory entry is a registration-time defect; surface it.
        raise AssertionError(
            f"Implementer {name!r} registered but has no "
            "ambiguous-resolution factory entry at "
            "_AMBIGUOUS_RESOLUTION_FACTORIES. The D139 cross-cutting "
            "commitment requires every implementer to demonstrate "
            "resolution-ambiguity routing structurally."
        )

    factory, invocation, ambiguous_input = _AMBIGUOUS_RESOLUTION_FACTORIES[
        name
    ]
    cell, repo = factory()

    async def _drive() -> None:
        state = await cell.open(invocation)
        await cell.turn(state, ambiguous_input)

    asyncio.run(_drive())

    assert len(repo.saved) == 1, (
        f"Implementer {name!r} did not persist a PendingClarification on "
        "the resolution-ambiguous path; D139 requires the routing."
    )
    saved = repo.saved[0]
    candidates_sidecar = saved.proposed_intent.get("resolution_candidates")
    assert candidates_sidecar is not None, (
        f"Implementer {name!r}'s PendingClarification.proposed_intent "
        "is missing the 'resolution_candidates' sidecar that D139 "
        "structural enforcement requires."
    )
    assert len(candidates_sidecar) >= 2, (
        f"Implementer {name!r}'s resolution_candidates sidecar carries "
        f"only {len(candidates_sidecar)} candidates; the multi-match "
        "fixture provided at least two."
    )
