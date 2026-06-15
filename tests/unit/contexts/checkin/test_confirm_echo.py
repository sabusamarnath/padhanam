"""The lever-aware confirm echo (D192, S97b).

Locks the privacy-by-design + partial-completion-catchable shape: multi-lever
goals summarise at the count level (never the clinical lever names), single-
lever goals read plainly, and a goal the reply was silent on is omitted.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from contexts.checkin.domain.confirm_echo import build_confirm_echo
from contexts.checkin.domain.lever import EligibleLever
from contexts.checkin.domain.outcome import CheckinState, ParsedLeverOutcome

_HEALTH = uuid4()
_LITANY = uuid4()
_VOICE = uuid4()

# Health regimen — four clinical medication levers (their names must never
# reach the echo).
_MED_NAMES = (
    "Aspirin, ramipril, atorvastatin, ezetimibe",
    "Second dose of isosorbide dinitrate",
    "Bisoprolol, first dose of isosorbide dinitrate",
    "Lansoprazole",
)
_MED_IDS = tuple(uuid4() for _ in _MED_NAMES)


def _health_levers() -> tuple[EligibleLever, ...]:
    return tuple(
        EligibleLever(
            commitment_id=cid, name=name, goal_id=_HEALTH, goal_name="Health regimen"
        )
        for cid, name in zip(_MED_IDS, _MED_NAMES)
    )


def _did(cid: UUID) -> ParsedLeverOutcome:
    return ParsedLeverOutcome(commitment_id=cid, state=CheckinState.DID)


def _didnt(cid: UUID) -> ParsedLeverOutcome:
    return ParsedLeverOutcome(
        commitment_id=cid, state=CheckinState.REPORTED_DIDNT
    )


def test_multi_lever_goal_all_done_reads_at_count_level() -> None:
    echo = build_confirm_echo(
        levers=_health_levers(),
        parsed=tuple(_did(cid) for cid in _MED_IDS),
    )
    assert "Health regimen: all 4 done" in echo
    # No clinical lever name ever reaches the channel.
    for name in _MED_NAMES:
        assert name not in echo


def test_multi_lever_goal_partial_exposes_the_miss_without_names() -> None:
    parsed = (
        _did(_MED_IDS[0]),
        _did(_MED_IDS[1]),
        _did(_MED_IDS[2]),
        _didnt(_MED_IDS[3]),
    )
    echo = build_confirm_echo(levers=_health_levers(), parsed=parsed)
    assert "Health regimen: 3 done, 1 not done" in echo
    for name in _MED_NAMES:
        assert name not in echo
    assert "tell me which you missed" in echo


def test_single_lever_goal_reads_plainly() -> None:
    levers = (
        EligibleLever(
            commitment_id=_LITANY, name="Litany", goal_id=_LITANY, goal_name="Litany"
        ),
        EligibleLever(
            commitment_id=_VOICE, name="Voice", goal_id=_VOICE, goal_name="Voice projection"
        ),
    )
    echo = build_confirm_echo(
        levers=levers, parsed=(_did(_LITANY), _didnt(_VOICE))
    )
    assert "Litany: done" in echo
    assert "Voice projection: not done" in echo


def test_silent_goal_is_omitted_entirely() -> None:
    """A goal the reply never spoke to writes nothing, so it is not echoed
    (silence is not a miss — it must not surface as 'not done')."""
    levers = (
        EligibleLever(
            commitment_id=_LITANY, name="Litany", goal_id=_LITANY, goal_name="Litany"
        ),
        EligibleLever(
            commitment_id=_VOICE, name="Voice", goal_id=_VOICE, goal_name="Voice projection"
        ),
    )
    echo = build_confirm_echo(levers=levers, parsed=(_did(_LITANY),))
    assert "Litany: done" in echo
    assert "Voice projection" not in echo
    assert "not done" not in echo
