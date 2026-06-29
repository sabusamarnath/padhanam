"""S103p/D216: the pure pipeline assessment — recommendation-shaped, headline
invariant to the ambiguous close-reason mix."""

from __future__ import annotations

from uuid import uuid4

from contexts.daily_driver.domain.cdd import (
    OpportunityView,
    ProofState,
    ProvenanceOrigin,
)
from contexts.daily_driver.domain.pipeline_assessment import assess_pipeline

_SCREENING = uuid4()  # an "interview" gate
_APPLY = uuid4()      # the earliest gate (not an interview)


def _opp(*, prov, status, reason=None, gate=None):
    return OpportunityView(
        opportunity_id=uuid4(), name="Co", current_gate_id=gate, unit_count=2,
        provenance_origin=prov, proof_state=ProofState.PENDING,
        status=status, closed_reason=reason,
    )


def _the_real_shape():
    # 0 confirmed-live, 6 suggested-live, 11 closed, 1 interviewed (Acme @ Screening).
    opps = []
    opps += [_opp(prov=ProvenanceOrigin.SYSTEM_SUGGESTED, status="live") for _ in range(5)]
    opps += [_opp(prov=ProvenanceOrigin.SYSTEM_SUGGESTED, status="live", gate=_APPLY)]
    opps += [_opp(prov=ProvenanceOrigin.SYSTEM_SUGGESTED, status="closed", reason="rejected") for _ in range(8)]
    opps += [_opp(prov=ProvenanceOrigin.USER_AUTHORED, status="closed", reason="rejected", gate=_SCREENING)]
    opps += [_opp(prov=ProvenanceOrigin.USER_AUTHORED, status="closed", reason="went_cold", gate=_APPLY)]
    opps += [_opp(prov=ProvenanceOrigin.USER_AUTHORED, status="closed", reason="declined")]
    return tuple(opps)


def test_the_real_shape_reads_pipeline_empty_response_failure():
    a = assess_pipeline(
        opportunities=_the_real_shape(),
        interview_gate_ids=frozenset({_SCREENING}),
        one_touch_volume=102, activity=166,
    )
    assert a.verdict_label == "pipeline empty"
    assert a.confirmed_live == 0 and a.suggested_live == 6 and a.closed == 11
    assert a.engaged == 17 and a.interviewed == 1 and a.offers == 0
    assert "upstream of interviews" in a.verdict_text
    assert "targeting" in a.move and "interview prep" in a.move  # response-rate move
    assert a.suggested_closed == 8 and a.split_proof_dependent is True


def test_headline_is_invariant_to_the_ambiguous_reason_mix():
    # AC1 / the design rule: flipping the closed reasons among the ambiguous set
    # (rejected/declined/went_cold/withdrawn) must NOT change the headline.
    base = assess_pipeline(
        opportunities=_the_real_shape(),
        interview_gate_ids=frozenset({_SCREENING}), one_touch_volume=102, activity=166,
    )
    # the "corrected" mix the operator might proof to (mostly went-cold), same shape
    opps = []
    opps += [_opp(prov=ProvenanceOrigin.SYSTEM_SUGGESTED, status="live") for _ in range(5)]
    opps += [_opp(prov=ProvenanceOrigin.SYSTEM_SUGGESTED, status="live", gate=_APPLY)]
    opps += [_opp(prov=ProvenanceOrigin.SYSTEM_SUGGESTED, status="closed", reason="went_cold") for _ in range(8)]
    opps += [_opp(prov=ProvenanceOrigin.USER_AUTHORED, status="closed", reason="rejected", gate=_SCREENING)]
    opps += [_opp(prov=ProvenanceOrigin.USER_AUTHORED, status="closed", reason="went_cold", gate=_APPLY)]
    opps += [_opp(prov=ProvenanceOrigin.USER_AUTHORED, status="closed", reason="declined")]
    corrected = assess_pipeline(
        opportunities=tuple(opps),
        interview_gate_ids=frozenset({_SCREENING}), one_touch_volume=102, activity=166,
    )
    # headline identical; only the split (closed_reasons) differs
    assert (base.verdict_label, base.verdict_text, base.because, base.move) == (
        corrected.verdict_label, corrected.verdict_text, corrected.because, corrected.move
    )
    assert base.closed_reasons != corrected.closed_reasons  # the split DID change


def test_a_confirmed_live_process_flips_the_verdict_off_empty():
    opps = _the_real_shape() + (
        _opp(prov=ProvenanceOrigin.USER_AUTHORED, status="live", gate=_SCREENING),
    )
    a = assess_pipeline(
        opportunities=opps, interview_gate_ids=frozenset({_SCREENING}),
        one_touch_volume=102, activity=166,
    )
    assert a.verdict_label == "live processes" and a.confirmed_live == 1
    assert "tend" in a.move.lower()


def test_an_offer_reads_in_the_headline():
    opps = (_opp(prov=ProvenanceOrigin.USER_AUTHORED, status="closed", reason="won", gate=_SCREENING),)
    a = assess_pipeline(
        opportunities=opps, interview_gate_ids=frozenset({_SCREENING}),
        one_touch_volume=10, activity=20,
    )
    assert a.offers == 1 and a.verdict_label == "offer in hand"


def test_suggested_closes_make_the_split_proof_dependent():
    a = assess_pipeline(
        opportunities=_the_real_shape(),
        interview_gate_ids=frozenset({_SCREENING}), one_touch_volume=102, activity=166,
    )
    assert a.split_proof_dependent is True
    # once every closed opportunity is user_authored (proofed), the split is settled
    opps = tuple(
        _opp(prov=ProvenanceOrigin.USER_AUTHORED, status="closed", reason="rejected")
        for _ in range(3)
    )
    b = assess_pipeline(
        opportunities=opps, interview_gate_ids=frozenset(),
        one_touch_volume=0, activity=0,
    )
    assert b.suggested_closed == 0 and b.split_proof_dependent is False
