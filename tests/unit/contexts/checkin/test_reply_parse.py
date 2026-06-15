"""The pure check-in parse mapping + prompt (D192, D184, S97b, Commit 3).

Deterministic coverage of the response mapping and the prompt's silence rule.
The model's behaviour on real replies (does it omit unmentioned levers, expand
"did my meds") is verified separately against live Ollama; here we lock the
parts that are ours: index mapping, out-of-range/invalid drops, dedup, and that
an absent lever produces no entry (silence is not a miss).
"""

from __future__ import annotations

from uuid import uuid4

from contexts.checkin.domain.lever import EligibleLever
from contexts.checkin.domain.outcome import CheckinState
from contexts.checkin.domain.reply_parse import (
    build_parse_prompt,
    map_parsed_outcomes,
)

_HEALTH = uuid4()
_LITANY = uuid4()
_MED = tuple(uuid4() for _ in range(4))


def _levers() -> tuple[EligibleLever, ...]:
    health = tuple(
        EligibleLever(
            commitment_id=cid,
            name=f"med {i}",
            goal_id=_HEALTH,
            goal_name="Health regimen",
        )
        for i, cid in enumerate(_MED)
    )
    litany = EligibleLever(
        commitment_id=_LITANY, name="Litany", goal_id=_LITANY, goal_name="Litany"
    )
    return health + (litany,)


def test_maps_indices_to_commitment_ids_and_states() -> None:
    levers = _levers()
    # model: meds 1-4 did (the goal-level expansion), litany (5) not done
    value = {
        "outcomes": [
            {"lever": 1, "state": "did"},
            {"lever": 2, "state": "did"},
            {"lever": 3, "state": "did"},
            {"lever": 4, "state": "did"},
            {"lever": 5, "state": "reported_didnt"},
        ]
    }
    out = map_parsed_outcomes(value, levers)
    by_id = {o.commitment_id: o.state for o in out}
    for cid in _MED:
        assert by_id[cid] is CheckinState.DID
    assert by_id[_LITANY] is CheckinState.REPORTED_DIDNT


def test_unmentioned_lever_is_absent_silence_is_not_a_miss() -> None:
    levers = _levers()
    # model only spoke to litany (index 5) — the four meds are silent.
    value = {"outcomes": [{"lever": 5, "state": "did"}]}
    out = map_parsed_outcomes(value, levers)
    assert len(out) == 1
    assert out[0].commitment_id == _LITANY
    # No med lever appears as a reported_didnt (or anything).
    assert all(o.commitment_id not in _MED for o in out)


def test_out_of_range_and_invalid_entries_are_dropped() -> None:
    levers = _levers()
    value = {
        "outcomes": [
            {"lever": 99, "state": "did"},      # out of range
            {"lever": 0, "state": "did"},       # out of range (1-based)
            {"lever": 5, "state": "banana"},    # invalid state
            {"lever": 1, "state": "did"},       # valid
        ]
    }
    out = map_parsed_outcomes(value, levers)
    assert len(out) == 1
    assert out[0].commitment_id == _MED[0]


def test_repeated_lever_keeps_last_state() -> None:
    levers = _levers()
    value = {
        "outcomes": [
            {"lever": 5, "state": "did"},
            {"lever": 5, "state": "reported_didnt"},
        ]
    }
    out = map_parsed_outcomes(value, levers)
    assert len(out) == 1
    assert out[0].state is CheckinState.REPORTED_DIDNT


def test_empty_or_malformed_value_yields_nothing() -> None:
    levers = _levers()
    assert map_parsed_outcomes({}, levers) == ()
    assert map_parsed_outcomes({"outcomes": "nope"}, levers) == ()
    assert map_parsed_outcomes({"outcomes": [42, None]}, levers) == ()


def test_prompt_groups_by_goal_numbers_levers_and_states_silence_rule() -> None:
    prompt = build_parse_prompt(reply_text="did my meds", levers=_levers())
    assert 'Goal "Health regimen":' in prompt
    assert 'Goal "Litany":' in prompt
    assert "  5. Litany" in prompt
    assert "Silence is not a miss" in prompt
    assert "did my meds" in prompt
