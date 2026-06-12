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

# Applicant-tracking / recruiter sender domains (the spike's allowlist).
_SENDERS = (
    "greenhouse.io", "hire.lever.co", "lever.co", "myworkday.com", "workday.com",
    "ashbyhq.com", "smartrecruiters.com", "linkedin.com", "indeed.com",
    "ziprecruiter.com", "jobvite.com", "icims.com", "taleo.net", "breezy.hr",
    "workable.com", "teamtailor.com", "recruitee.com", "wellfound.com",
    "otta.com", "hired.com",
)
# Subject tokens that signal application-shaped activity (the spike's set).
_SUBJECT_HITS = (
    "application", "applied", "interview", "offer", "recruiter", "assessment",
    "screening", "your candidacy", "next step",
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


def classify(from_address: str | None, subject: str | None) -> tuple[bool, str | None]:
    """Return ``(is_job_search, kind)``. ``kind`` is None when not job-search."""
    subj = (subject or "").lower()
    if any(x in subj for x in _ALERT_EXCLUSIONS):
        return (False, None)
    sender_hit = any(s in _domain(from_address) for s in _SENDERS)
    subj_hit = any(w in subj for w in _SUBJECT_HITS)
    if not (sender_hit or subj_hit):
        return (False, None)
    for kind, patterns in _KIND_PATTERNS:
        if any(p in subj for p in patterns):
            return (True, kind)
    return (True, "application")


__all__ = ["classify"]
