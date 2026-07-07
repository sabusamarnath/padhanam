"""The match domain — grounded-strict coverage, tier-from-mix, fingerprint (D239)."""

from __future__ import annotations

from uuid import uuid5, NAMESPACE_URL as NS

from contexts.daily_driver.domain.matching import (
    BAND_GAP,
    BAND_PARTIAL,
    BAND_STRENGTH,
    FIT_BULLSEYE,
    FIT_OPPORTUNISTIC,
    FIT_STRONG,
    build_match,
    match_inputs_fingerprint,
    parse_match,
    split_criteria,
    suggest_fit_tier,
)


def test_split_criteria_handles_bullets_numbers_semicolons_and_dedupes() -> None:
    blob = "- 8+ years PM\n2. SQL and analytics; pricing strategy\n• A/B testing\n- SQL and analytics"
    crits = split_criteria(blob)
    assert crits == (
        "8+ years PM", "SQL and analytics", "pricing strategy",
        "A/B testing",  # the second "SQL and analytics" de-duplicated
    )


def test_split_criteria_empty() -> None:
    assert split_criteria(None) == ()
    assert split_criteria("   ") == ()


def test_parse_match_is_grounded_strict() -> None:
    """AC2 — a criterion absent from the model output is a gap (not invented); an
    assessment for a criterion that is not an input is dropped; a gap has no
    evidence; an unknown band degrades to gap."""
    criteria = ("SQL", "Leadership", "Pricing", "A/B testing")
    value = {"assessments": [
        {"criterion": "SQL", "band": "strength", "evidence": "SQL listed"},
        {"criterion": "Leadership", "band": "gap", "evidence": "should be cleared"},
        {"criterion": "Pricing", "band": "wat", "evidence": "unknown band"},
        {"criterion": "INVENTED", "band": "strength", "evidence": "not an input"},
        # "A/B testing" omitted entirely by the model
    ]}
    covs = parse_match(criteria, value)
    by = {c.criterion: c for c in covs}
    # one per input criterion, input order, no invented criteria
    assert tuple(c.criterion for c in covs) == criteria
    assert "INVENTED" not in by
    assert by["SQL"].band == BAND_STRENGTH and by["SQL"].evidence == "SQL listed"
    assert by["Leadership"].band == BAND_GAP and by["Leadership"].evidence == ""
    assert by["Pricing"].band == BAND_GAP  # unknown band -> gap
    assert by["A/B testing"].band == BAND_GAP  # omitted -> gap, never invented
    assert by["A/B testing"].evidence == ""


def test_parse_match_malformed_output_is_all_gap() -> None:
    criteria = ("A", "B")
    assert all(c.band == BAND_GAP for c in parse_match(criteria, {}))
    assert all(c.band == BAND_GAP for c in parse_match(criteria, {"assessments": "nope"}))


def test_suggest_fit_tier_from_coverage_mix() -> None:
    def covs(bands):
        return build_match(tuple(f"c{i}" for i in range(len(bands))), {
            "assessments": [
                {"criterion": f"c{i}", "band": b, "evidence": ""}
                for i, b in enumerate(bands)
            ]
        }).coverages
    # 4/4 strength -> 1.0 -> bullseye
    assert suggest_fit_tier(covs([BAND_STRENGTH] * 4)) == FIT_BULLSEYE
    # 3 strength + 1 partial of 4 -> 0.875 -> bullseye
    assert suggest_fit_tier(covs([BAND_STRENGTH]*3 + [BAND_PARTIAL])) == FIT_BULLSEYE
    # 2 strength + 2 gap of 4 -> 0.5 -> strong
    assert suggest_fit_tier(covs([BAND_STRENGTH]*2 + [BAND_GAP]*2)) == FIT_STRONG
    # 1 strength + 3 gap of 4 -> 0.25 -> opportunistic
    assert suggest_fit_tier(covs([BAND_STRENGTH] + [BAND_GAP]*3)) == FIT_OPPORTUNISTIC
    # no criteria -> no suggestion
    assert suggest_fit_tier(()) is None


def test_fingerprint_stable_and_change_sensitive() -> None:
    a, b = uuid5(NS, "a"), uuid5(NS, "b")
    crit = "- SQL\n- Pricing"
    f1 = match_inputs_fingerprint(criteria_text=crit, confirmed_items=((a, "SQL"), (b, "Pricing")))
    # order-independent (sorted internally)
    f2 = match_inputs_fingerprint(criteria_text=crit, confirmed_items=((b, "Pricing"), (a, "SQL")))
    assert f1 == f2
    # a criteria edit changes it
    assert f1 != match_inputs_fingerprint(criteria_text=crit + "\n- New", confirmed_items=((a, "SQL"), (b, "Pricing")))
    # an item text edit changes it
    assert f1 != match_inputs_fingerprint(criteria_text=crit, confirmed_items=((a, "SQL edited"), (b, "Pricing")))
    # a deletion changes it (the timestamp-approach hole this closes)
    assert f1 != match_inputs_fingerprint(criteria_text=crit, confirmed_items=((a, "SQL"),))
