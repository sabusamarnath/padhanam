"""Check-in composer eligibility scopes to active goals (S103e follow-up).

The S97b check-in composer fires on eligible **homeostatic** goals, and every
goal archived at S103e is homeostatic — so the composer is exactly the surface
that would still fire on an archived goal if its eligibility were unscoped.

Step-0 finding: ``EligibleLeversReaderAdapter`` does **not** run a separate
``:Outcome{mode:'homeostatic'}`` traversal. It reads ``goals_reader.list_goals``
— the same seam S103e scoped to active goals (``archived_at IS NULL``) — and
filters by mode in Python. So an archived homeostatic goal never appears in
``list_goals`` and never becomes eligible; the scope is inherited, no code
change needed. These tests pin that inherited guarantee: eligibility is a pure
function of ``list_goals`` (the scoped read), so a goal absent from it (archived)
produces no eligible lever. A future refactor adding an unscoped traversal would
break them.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from apps.api._checkin_wiring import EligibleLeversReaderAdapter
from contexts.daily_driver.domain.commitment import Commitment
from contexts.daily_driver.domain.goal import ControlAxis, Goal, GoalMode, Subject
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000d001"


def _actor() -> ActorContext:
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id="t"
        ),
        actor_id="operator",
        role_list=frozenset({ROLE_OPERATOR}),
        authorisation_set=authorisations_for_roles(frozenset({ROLE_OPERATOR})),
    )


def _homeostatic_goal(name: str, commitment_id: UUID) -> Goal:
    return Goal(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name=name,
        mode=GoalMode.HOMEOSTATIC,
        control=ControlAxis.SELF,
        subject=Subject.SELF,
        lever_commitment_id=commitment_id,
        lever_commitment_ids=(commitment_id,),
    )


def _daily_commitment(commitment_id: UUID, name: str) -> Commitment:
    return Commitment(
        id=commitment_id,
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name=name,
        expected_interval_days=1,
        authored_by_user_id="operator",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )


class _FakeGoalsReader:
    """Stands in for the scoped GoalGraphAdapter: list_goals returns only the
    goals it is given (the real adapter returns active goals only)."""

    def __init__(self, goals: tuple[Goal, ...]) -> None:
        self._goals = goals

    async def list_goals(self, *, tenant_context: TenantContext) -> tuple[Goal, ...]:
        return self._goals


class _FakeCommitmentRepo:
    def __init__(self, commitments: dict[UUID, Commitment]) -> None:
        self._by_id = commitments

    async def get_commitment(
        self, *, tenant_context: TenantContext, commitment_id: UUID
    ) -> Commitment | None:
        return self._by_id.get(commitment_id)


def test_active_homeostatic_goal_is_eligible() -> None:
    cid = uuid4()
    goal = _homeostatic_goal("Health regimen", cid)
    adapter = EligibleLeversReaderAdapter(
        goals_reader=_FakeGoalsReader((goal,)),
        commitment_repository=_FakeCommitmentRepo({cid: _daily_commitment(cid, "Aspirin")}),
    )
    eligible = asyncio.run(adapter.list_eligible(actor=_actor()))
    assert {e.goal_name for e in eligible} == {"Health regimen"}


def test_archived_homeostatic_goal_absent_from_list_goals_yields_no_checkin() -> None:
    # The scoped list_goals excludes archived goals (S103e), so the adapter
    # never sees the archived homeostatic goal — it produces no eligible lever,
    # hence the composer sends no check-in. Modelled as: list_goals returns the
    # active set only (here, empty — the get-a-job-only re-scoped state, where
    # every homeostatic goal was archived).
    archived_cid = uuid4()
    adapter = EligibleLeversReaderAdapter(
        goals_reader=_FakeGoalsReader(()),  # archived -> absent from list_goals
        commitment_repository=_FakeCommitmentRepo(
            {archived_cid: _daily_commitment(archived_cid, "Aspirin")}
        ),
    )
    eligible = asyncio.run(adapter.list_eligible(actor=_actor()))
    assert eligible == ()
