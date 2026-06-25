"""Matcher precision: source-class taxonomy + genuine-match bar (S103i, D209)."""

from __future__ import annotations

from uuid import uuid4

from contexts.daily_driver.domain.goal_assessment import (
    ElementEvidence,
    LinkStatus,
    binding_rationale,
    element_token_counts,
)
from contexts.daily_driver.domain.precision import (
    MARKET,
    PIPELINE,
    UnitSource,
    apply_precision,
    is_genuine_bind,
    source_disposition,
)
from contexts.daily_driver.domain.work_unit import FacetType


# --- Mechanism A: source-class taxonomy --------------------------------------

def test_listing_subject_routes_to_market():
    d = source_disposition(FacetType.EMAIL, "linkedin.com",
                           "Casey, apply now to 'Head of AI at Zephyr Corp'")
    assert d == MARKET


def test_application_ack_routes_to_pipeline():
    d = source_disposition(FacetType.EMAIL, "wtwco.com",
                           "WTW Careers – We've received your application")
    assert d == PIPELINE


def test_ats_domain_routes_to_pipeline():
    d = source_disposition(FacetType.EMAIL, "talent.icims.com", "Your status")
    assert d == PIPELINE


def test_board_domain_default_routes_to_market():
    d = source_disposition(FacetType.EMAIL, "linkedin.com", "Vizrt and more")
    assert d == MARKET


def test_internal_facet_defers_to_the_bar():
    assert source_disposition(FacetType.MEETING, "", "Megan's warm-ups") is None
    assert source_disposition(FacetType.TASK, "", "Buy milk") is None


def test_direct_unknown_sender_defers():
    # A real company thread or a newsletter — the bar decides, not the source class.
    assert source_disposition(FacetType.EMAIL, "nytimes.com",
                              "The Olivia Rodrigo interview") is None


# --- Mechanism B: genuine-match bar ------------------------------------------

def test_single_generic_token_is_not_genuine():
    # "warm" is in >1 element label -> generic -> a single-token match is not genuine.
    counts = element_token_counts((
        "Targeting segments warm over cold",
        "Referral pursuit chase a warm referral",
    ))
    assert is_genuine_bind(("Megan's articulation warm-ups",),
                           "Referral pursuit chase a warm referral", counts) is False


def test_discriminative_single_token_is_genuine():
    counts = element_token_counts(("Acme interview prep",))
    assert is_genuine_bind(("Acme interview Tuesday",),
                           "Acme interview prep", counts) is True


def test_two_corroborating_tokens_are_genuine():
    counts = element_token_counts((
        "Tailoring effort per application investment",
        "Time budget per application",
    ))
    # shares both "application" and "investment" -> corroboration, kept.
    assert is_genuine_bind(("application investment for the role",),
                           "Tailoring effort per application investment", counts) is True


def test_two_corpus_generic_tokens_do_not_corroborate():
    # D212: stopword-grade/corpus-generic tokens do not count toward a genuine
    # match. Two shared tokens that are BOTH corpus-common (in >threshold units)
    # are parked, not kept on the old "two-plus tokens" rule.
    counts = element_token_counts(("Interview stage scheduling",))
    corpus = {"interview": 40, "stage": 35}  # both corpus-common
    assert is_genuine_bind(
        ("interview stage for the role",), "Interview stage scheduling",
        counts, corpus,
    ) is False


def test_discriminative_plus_generic_is_still_genuine():
    # D212: a corpus-rare discriminative token survives even alongside a generic
    # one — the Acme case is kept, only the basis ignores the generic word.
    counts = element_token_counts(("Acme application",))
    corpus = {"acme": 3, "application": 60}
    assert is_genuine_bind(
        ("your acme application update",), "Acme application", counts, corpus,
    ) is True


def test_bar_is_consistent_with_the_read_side_honest_why():
    # D204 tie: the bar un-binds exactly what the honest-why rates weak on a
    # single token. A generic single token reads weak; the bar rejects it.
    counts = element_token_counts((
        "Targeting warm over cold",
        "Referral pursuit warm referral",
    ))
    label = "Referral pursuit warm referral"
    title = "Megan's warm-ups"
    genuine = is_genuine_bind((title,), label, counts)
    _basis, strength = binding_rationale(
        unit_title=title, element_label=label, tier="lexical_keyword",
        token_element_counts=counts,
    )
    # both agree it is weak / not genuine
    assert genuine is False and strength != "strong"


# --- routing + park + protect -------------------------------------------------

def _ev(unit_id, element_id, tier="lexical_keyword"):
    return ElementEvidence(
        unit_id=unit_id, element_kind="lever", element_id=element_id,
        outcome_id=uuid4(), tier=tier,
        status=LinkStatus.CANDIDATE if tier != "lexical_exact" else LinkStatus.CONFIRMED,
        basis="element-keyword",
    )


def test_apply_precision_routes_parks_and_protects():
    board_u, ack_u, noise_u, real_u, prot_u = (uuid4() for _ in range(5))
    el = uuid4()
    labels = {el: "Referral pursuit chase a warm referral"}
    counts = element_token_counts(tuple(labels.values()) + ("Targeting warm",))
    ev = (
        _ev(board_u, el), _ev(ack_u, el), _ev(noise_u, el),
        _ev(real_u, el), _ev(prot_u, el),
    )
    src = {
        board_u: UnitSource(FacetType.EMAIL, "linkedin.com", "apply now to X", 1, ("apply now to X",)),
        ack_u: UnitSource(FacetType.EMAIL, "wtwco.com", "we received your application", 1, ("ack",)),
        noise_u: UnitSource(FacetType.MEETING, "", "warm-ups", 1, ("Megan's warm-ups",)),
        real_u: UnitSource(FacetType.EMAIL, "acme.example", "interview", 3, ("Referral pursuit warm",)),
        prot_u: UnitSource(FacetType.MEETING, "", "warm-ups", 1, ("warm",)),
    }
    res = apply_precision(
        ev, unit_source=src, element_label_by_id=labels,
        token_element_counts=counts, protected_unit_ids=frozenset({prot_u}),
    )
    assert board_u in res.market_units
    assert ack_u in res.pipeline_units
    assert noise_u in res.parked_units          # internal facet, generic "warm" -> parked
    kept_units = {e.unit_id for e in res.kept}
    assert prot_u in kept_units                 # protected, kept untouched
    assert real_u in kept_units                 # shares "referral" + "warm" -> 2 tokens, kept
