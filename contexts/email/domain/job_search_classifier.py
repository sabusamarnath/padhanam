"""Rules-only job-search classifier over email metadata (D183, S89).

Keys on **sender + subject** only — never the body, never embeddings (the S87
spike rejected a local-model tier: zero recall gain, only disagreement). Given
an email's from-address and subject, returns whether it is job-search activity
and, if so, its kind (application / acknowledgement / interview / offer /
rejection). The patterns are lifted verbatim from the spike
(`/tmp/s87_spike/spike.py`) plus an **alert-exclusion boundary** — obvious
job-board *alert/digest* noise (matching a recruiter sender or an "application"
subject but being a recommendation feed, not the operator's own activity) is
excluded so the folded count reflects real job-search work (D171 honesty).

Pure domain (D16): stdlib only, no I/O. The caller supplies the decrypted
metadata; the verdict is persisted on the store (S89) so `correlate_goal_facets`
re-reads it on every recompute and the SERVES edges stay durable.
"""

from __future__ import annotations

import re

# Transactional applicant-tracking senders: the email itself IS a job-search
# action (application receipt, interview invite, status change), so the sender
# alone qualifies it. (The spike's allowlist, minus the noisy network/aggregator
# senders split out below.)
_ATS_SENDERS = (
    "greenhouse.io", "hire.lever.co", "lever.co", "myworkday.com", "workday.com",
    "ashbyhq.com", "smartrecruiters.com", "jobvite.com", "icims.com", "taleo.net",
    "breezy.hr", "workable.com", "teamtailor.com", "recruitee.com",
)
# Noisy network / aggregator senders: high-volume recommendation, alert, and
# network traffic alongside genuine application-status mail. The sender alone is
# NOT enough — a subject signal is required (S89 precision pass: LinkedIn sent
# 236 emails, ~158 of them recommendation digests with no application signal).
# Listed for documentation; functionally they qualify only via a subject hit,
# the same path as any unrecognised sender.
_NOISY_SENDERS = (
    "linkedin.com", "indeed.com", "ziprecruiter.com", "wellfound.com",
    "otta.com", "hired.com",
)
# Subject tokens that signal application-shaped activity (the spike's set, minus
# "next step" — S89 precision pass: a generic phrase that means nothing without a
# job-context sender, it caught an entire property-purchase thread and every real
# "next steps" job email in the corpus also carries application/interview, so its
# removal is pure inflation removal at zero recall cost).
_SUBJECT_HITS = (
    "application", "applied", "interview", "offer", "recruiter", "assessment",
    "screening", "your candidacy",
)

# Kinds that carry the moat's highest signal weight (D171 honesty): an offer or
# an interview is a strong positive on the goal. The calibrated evidence bar
# (D184) requires that these never be minted by an unknown, contextless sender on
# a bare subject keyword.
HIGH_SIGNAL_KINDS = frozenset({"offer", "interview"})

# Job-process phrases that corroborate a high-signal verdict (D184 mechanism, S89
# correction). When a high-signal kind comes from an *unknown* sender, the email
# must carry job-process context in its own subject — the email's self-evident
# context standing in for the thread context the scoped store cannot provide
# (whole-thread corroboration is the post-week upgrade). This is job-process
# vocabulary — bounded and stable — never the bare high-signal keyword itself
# ("offer"/"interview" alone do not corroborate; a newsletter mentioning either
# carries no process context). The set excludes "next step" deliberately: it is a
# corroborator, not a trigger, so it can never resurrect the property thread that
# fix #2 stripped of any trigger (the gate is trigger-first, corroborate-second).
_CORROBORATING_PHRASES = (
    "interview request", "interview invitation", "interview scheduled",
    "interview confirmation", "invitation to interview", "schedule your interview",
    "schedule an interview", "schedule a call", "screening", "phone screen",
    "technical screen", "assessment", "next steps", "applied", "your application",
    "your candidacy", "recruiter", "we'd like to", "we would like to",
)
# Alert/digest noise: a recommendation feed, not the operator's own activity.
# Excluded even when a sender/subject otherwise matches (the precision boundary).
_ALERT_EXCLUSIONS = (
    "job alert", "jobs you may", "new jobs", "jobs for you", "recommended jobs",
    "job recommendations", "set up job alert", "jobs in", "people you may know",
    "who's hiring", "job digest", "based on your profile", "new opportunities",
    "is hiring", "are hiring", "view jobs", "saved search",
)

_KIND_PATTERNS = (
    ("offer", ("offer extended", "job offer", "your offer", "offer of employment")),
    ("rejection", ("unfortunately", "not moving forward", "we regret", "other candidates",
                   "not be moving", "not selected", "decided not to", "no longer under consideration")),
    ("interview", ("interview", "assessment", "screening", "schedule a", "schedule your",
                   "next steps", "phone screen", "technical screen")),
    ("acknowledgement", ("received your application", "thank you for applying",
                         "application received", "we have received", "thanks for applying")),
)


def _domain(from_address: str | None) -> str:
    m = re.search(r"@([\w.-]+)", from_address or "")
    return m.group(1).lower() if m else ""


def is_known_sender(from_address: str | None) -> bool:
    """Whether the sender is in a maintained job-context set (ATS or aggregator).

    A *known* sender is the allowlist the platform maintains — finite and
    bounded. The calibrated evidence bar (D184) keys on this: a high-signal kind
    from an *unknown* sender must corroborate in its own subject; a known sender
    need not. The bounded thing is this allowlist; a sender denylist would be the
    unbounded thing (an infinite supply of content platforms), so it is not used.
    """
    domain = _domain(from_address)
    return any(s in domain for s in _ATS_SENDERS) or any(
        s in domain for s in _NOISY_SENDERS
    )


def _kind_for(subj: str) -> str:
    """The kind a qualifying subject triggers — the first matching pattern."""
    for kind, patterns in _KIND_PATTERNS:
        if any(p in subj for p in patterns):
            return kind
    return "application"


def classify(from_address: str | None, subject: str | None) -> tuple[bool, str | None]:
    """Return ``(is_job_search, kind)``. ``kind`` is None when not job-search.

    Trigger-first, corroborate-second (D184). A subject must first *trigger* —
    an ATS sender, or a subject-hit keyword — to be job-search at all; only then
    is the kind read. The calibrated evidence bar then applies: a high-signal
    kind (offer/interview) minted from an *unknown* sender is demoted unless its
    subject carries corroborating job-process context. Corroboration only ever
    *demotes*; it never promotes, so a phrase like "next steps" can never
    resurrect a fake (e.g. a property thread) that carried no trigger.
    """
    subj = (subject or "").lower()
    if any(x in subj for x in _ALERT_EXCLUSIONS):
        return (False, None)
    domain = _domain(from_address)
    # Trigger: an ATS sender qualifies on its own; a noisy/aggregator or unknown
    # sender qualifies only with a subject keyword — sender alone is not enough.
    ats_hit = any(s in domain for s in _ATS_SENDERS)
    subj_hit = any(w in subj for w in _SUBJECT_HITS)
    if not (ats_hit or subj_hit):
        return (False, None)
    kind = _kind_for(subj)
    # Corroborate: an unknown sender cannot mint the moat's highest cells on a
    # bare keyword — the subject must show self-evident job-process context.
    if kind in HIGH_SIGNAL_KINDS and not is_known_sender(from_address):
        if not any(p in subj for p in _CORROBORATING_PHRASES):
            return (False, None)
    return (True, kind)


__all__ = ["HIGH_SIGNAL_KINDS", "classify", "is_known_sender"]
