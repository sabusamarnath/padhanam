"""Unit tests for the rules-only job-search classifier + the classify use case
(D183, S89). Synthetic fixtures only — no real senders, subjects, or PII.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.email.application.classify_job_search import (
    classify_job_search_emails,
)
from contexts.email.domain.email import Email
from contexts.email.domain.job_search_classifier import classify


def test_sender_allowlist_hit_is_job_search():
    ok, kind = classify("no-reply@greenhouse.io", "Your application to Acme")
    assert ok is True and kind == "application"


def test_subject_hit_without_known_sender_is_job_search():
    ok, kind = classify("careers@somecompany.example", "Interview invitation")
    assert ok is True and kind == "interview"


def test_alert_digest_is_excluded_even_with_a_matching_sender():
    # The precision boundary: a recruiter sender sending a job *alert* digest is
    # not the operator's own activity.
    ok, kind = classify("jobs@linkedin.com", "10 new jobs for you this week")
    assert ok is False and kind is None


def test_unrelated_email_is_not_job_search():
    ok, kind = classify("friend@personal.example", "dinner on saturday?")
    assert ok is False and kind is None


def test_noisy_sender_without_a_subject_signal_is_not_job_search():
    # S89 precision pass: a network/aggregator sender (LinkedIn) is high-volume
    # recommendation noise — sender alone must NOT qualify. A LinkedIn job
    # *recommendation* digest carries no application signal in its subject.
    ok, kind = classify("notifications@linkedin.com", "Chief Executive Officer at Acme")
    assert ok is False and kind is None


def test_noisy_sender_with_a_subject_signal_still_qualifies():
    # The genuine path survives: LinkedIn application-status mail carries the
    # signal in the subject, so it still classifies.
    ok, kind = classify("notifications@linkedin.com", "Casey, your application was sent to Acme")
    assert ok is True and kind == "application"


def test_next_steps_alone_no_longer_qualifies():
    # S89 fix #2: "next step(s)" is a generic phrase that means nothing without a
    # job-context sender — it caught a whole property-purchase thread. Removed
    # from the subject-hit set; a bare "Next Steps" from an unknown sender falls.
    ok, kind = classify("agent@someestate.example", "Re: Next Steps | 12 High Street")
    assert ok is False and kind is None


def test_is_known_sender_spans_ats_and_aggregator_only():
    from contexts.email.domain.job_search_classifier import is_known_sender
    assert is_known_sender("noreply@greenhouse.io") is True       # ATS
    assert is_known_sender("notifications@linkedin.com") is True   # aggregator
    assert is_known_sender("recruiter@personal.example") is False  # unknown


def test_high_signal_from_unknown_sender_needs_subject_corroboration():
    # The calibrated bar (D184), subject-corroboration form: a high-signal kind
    # (offer/interview) from an unknown sender is demoted unless the subject
    # carries job-process context. A newsletter mentioning "offer"/"interview"
    # has none and falls; the bare keyword does not corroborate itself.
    assert classify("news@contentplatform.example", "How I got a job offer in 8 days") == (False, None)
    assert classify("digest@news.example", "The Olivia Rodrigo interview") == (False, None)


def test_corroborated_high_signal_from_unknown_sender_survives():
    # The genuine cold cases: the subject is self-evidently job-process, so the
    # unknown sender qualifies (Acme interview request, a scheduled interview, a
    # screening for a role you applied to, next steps on your application).
    assert classify("talent@acme.example", "Acme – Interview Request for Lead PM")[1] == "interview"
    assert classify("noreply@screenloop.example", "You have an interview scheduled for Tuesday")[1] == "interview"
    assert classify("careers@umbrella-pharma.example", "How was your screening experience for the role you applied to?")[1] == "interview"


def test_corroboration_never_resurrects_a_triggerless_fake():
    # Trigger-first, corroborate-second: the property thread lost its only
    # trigger when "next step" left the subject-hit set (fix #2). "next steps"
    # is a *corroborator*, not a trigger, so it cannot bring the thread back.
    assert classify("agent@someestate.example", "Re: Next Steps | 18 Acacia Avenue") == (False, None)


def test_known_sender_high_signal_needs_no_corroboration():
    # A known ATS sender mints a high-signal kind on its own — the bar only
    # rises for unknown senders.
    assert classify("no-reply@lever.co", "Your offer")[1] == "offer"


def test_kind_buckets():
    assert classify("x@lever.co", "Offer of employment — Acme")[1] == "offer"
    assert classify("x@lever.co", "Unfortunately we won't be moving forward")[1] == "rejection"
    assert classify("x@lever.co", "Schedule your technical screen")[1] == "interview"
    assert classify("x@lever.co", "We have received your application")[1] == "acknowledgement"
    assert classify("x@lever.co", "Recruiter reaching out about a role")[1] == "application"


# --- the use case: classify + persist verdicts ------------------------------

_TENANT = UUID("00000000-0000-4000-8000-00000000d001")
_NOW = datetime(2026, 6, 12, tzinfo=timezone.utc)


def _email(mid: str, frm: str, subject: str, thread_id: str | None = None) -> Email:
    return Email(
        id=uuid4(), tenant_id=_TENANT, jurisdiction="eu-west", message_id=mid,
        thread_id=thread_id, from_address=frm, to_addresses=(), cc_addresses=(),
        subject=subject, body=None, snippet=None, labels=(), history_id=None,
        content_hash="h", received_at=_NOW, created_at=_NOW, updated_at=_NOW,
    )


class _FakeStore:
    def __init__(self, emails):
        self._emails = emails
        self.written: dict[str, str | None] = {}

    async def list_emails(self, *, tenant_context, include_deleted=False):
        return tuple(self._emails)

    async def set_job_search_kinds(self, *, tenant_context, verdicts):
        self.written = dict(verdicts)
        return len(verdicts)


def test_use_case_classifies_and_persists():
    store = _FakeStore([
        _email("m1", "x@greenhouse.io", "Your application to Acme"),
        _email("m2", "x@lever.co", "Schedule your interview"),
        _email("m3", "jobs@linkedin.com", "5 new jobs for you"),  # alert -> excluded
        _email("m4", "friend@x.example", "lunch?"),               # unrelated
    ])
    result = asyncio.run(
        classify_job_search_emails(tenant_context=object(), emails=store)
    )
    assert result.total == 4
    assert result.confirmed == 2  # m1, m2
    assert store.written == {"m1": "application", "m2": "interview", "m3": None, "m4": None}
    assert result.by_kind.get("application") == 1
    assert result.by_kind.get("interview") == 1
    assert result.by_kind.get("none") == 2


def test_use_case_persists_the_calibrated_verdict():
    # The use case is the simple per-email pass; the calibrated bar lives in
    # classify. A newsletter "offer"/"interview" from an unknown sender is
    # demoted (no corroboration); a corroborated interview and a plain
    # application survive.
    store = _FakeStore([
        _email("o1", "news@contentplatform.example", "How I landed a job offer in 8 days"),
        _email("i1", "digest@news.example", "An interview with a musician"),
        _email("i2", "talent@acme.example", "Acme – Interview Request for Lead PM"),
        _email("a1", "careers@somecompany.example", "Your application to the role"),
    ])
    result = asyncio.run(
        classify_job_search_emails(tenant_context=object(), emails=store)
    )
    assert store.written == {"o1": None, "i1": None, "i2": "interview", "a1": "application"}
    assert result.confirmed == 2
