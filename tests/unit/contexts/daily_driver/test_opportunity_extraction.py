"""S103o/D215: the pure extraction parse + cluster-and-classify."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.daily_driver.domain.opportunity_extraction import (
    EXTRACTION_SCHEMA,
    UnitExtraction,
    build_extraction_prompt,
    cluster_and_classify,
    parse_extraction,
)

_NOW = datetime(2026, 6, 29, tzinfo=timezone.utc)


def test_prompt_teaches_content_over_sender_and_lists_items():
    p = build_extraction_prompt((("Acme interview", "We'd like to invite you"),))
    assert "real hiring company" in p and "applicant-tracking" in p
    assert "[1] subject: Acme interview" in p


def test_parse_maps_index_to_unit_id_and_drops_bad_rows():
    u1, u2 = uuid4(), uuid4()
    value = {"items": [
        {"index": 1, "company": "Acme", "role": "PM", "outcome_signal": "rejected"},
        {"index": 2, "company": "  ", "role": "", "outcome_signal": "weird"},  # bad signal -> none
        {"index": 9, "company": "X", "role": "Y", "outcome_signal": "offer"},  # out of range -> dropped
    ]}
    out = parse_extraction(value, (u1, u2))
    assert len(out) == 2
    assert out[0] == UnitExtraction(unit_id=u1, company="Acme", role="PM", signal="rejected")
    assert out[1].unit_id == u2 and out[1].company == "" and out[1].signal == "none"


def test_multi_touch_clusters_single_touch_does_not():
    a1, a2, b1 = uuid4(), uuid4(), uuid4()
    ex = (
        UnitExtraction(a1, "Acme", "PM", "ongoing"),
        UnitExtraction(a2, "Acme", "PM", "rejected"),
        UnitExtraction(b1, "Acme", "Eng", "none"),  # single touch -> not an opportunity
    )
    opps = cluster_and_classify(ex, now=_NOW)
    assert len(opps) == 1
    assert opps[0].company == "Acme" and set(opps[0].unit_ids) == {a1, a2}


def test_unextracted_company_falls_out_of_clustering():
    a1, a2 = uuid4(), uuid4()
    ex = (UnitExtraction(a1, "", "PM", "ongoing"), UnitExtraction(a2, "", "PM", "ongoing"))
    assert cluster_and_classify(ex, now=_NOW) == ()


def test_classification_from_content_signals():
    def opp(signal):
        u1, u2 = uuid4(), uuid4()
        ex = (UnitExtraction(u1, "Co", "R", signal), UnitExtraction(u2, "Co", "R", "ongoing"))
        return cluster_and_classify(ex, now=_NOW)[0]
    assert (opp("offer").status, opp("offer").closed_reason) == ("closed", "won")
    assert (opp("rejected").status, opp("rejected").closed_reason) == ("closed", "rejected")
    assert (opp("declined").status, opp("declined").closed_reason) == ("closed", "declined")
    assert (opp("withdrawn").status, opp("withdrawn").closed_reason) == ("closed", "withdrawn_or_killed")


def test_no_signal_recent_is_live_stale_is_went_cold():
    a1, a2 = uuid4(), uuid4()
    ex = (UnitExtraction(a1, "Co", "R", "ongoing"), UnitExtraction(a2, "Co", "R", "none"))
    # recent -> live (the operator confirms/closes)
    recent = {a1: _NOW - timedelta(days=5), a2: _NOW - timedelta(days=10)}
    assert cluster_and_classify(ex, latest_by_unit=recent, now=_NOW)[0].status == "live"
    # stale, no close signal -> went-cold (absence of response over a long gap)
    stale = {a1: _NOW - timedelta(days=200), a2: _NOW - timedelta(days=210)}
    cold = cluster_and_classify(ex, latest_by_unit=stale, now=_NOW)[0]
    assert (cold.status, cold.closed_reason) == ("closed", "went_cold")


def test_schema_shape():
    assert EXTRACTION_SCHEMA["type"] == "object"
    item = EXTRACTION_SCHEMA["properties"]["items"]["items"]
    assert set(item["required"]) == {"index", "company", "role", "outcome_signal"}
