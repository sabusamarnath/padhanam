"""Content-extraction clustering — extract company/role, cluster, classify (S103o, D215).

Domain clustering fails for a job search because ATS platforms hide the company
(one ``ashbyhq.com`` carries several real companies; ``linkedin.com`` is a board),
so the company and role are read from unit **content** (subject + body), not the
sender domain (D184, the use-case-sees-context pattern). This module is pure (D16,
stdlib only): the JSON Schema the structured-output port constrains the model to,
the prompt builder, the defensive parse, and the pure cluster-and-classify that
groups multi-touch signatures into candidate opportunities and labels each live or
closed. The LLM call itself lives behind the structured-output seam in an adapter.

The classification is conservative (the S103n ground-truth rule): a closed reason is
asserted only where the content signal (rejection/decline/withdrawal/offer) or
genuine staleness supports it; uncertain processes default to ``live`` for the
operator to confirm or close. Everything instantiated is ``system_suggested`` (D200);
the operator proofs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

# A multi-touch signature (>=2 units on the same company-and-role) is a candidate
# opportunity; a single touch stays pipeline volume, not a tracked process (S103i).
_MIN_TOUCHES = 2
# No close signal and no touch newer than this many days reads as went-cold — the
# absence of a response over a long gap is what "went cold" means (S103n).
STALE_DAYS = 90

# The content signals the extraction may report, strongest-outcome first when a
# cluster carries several. Mapped to S103n's closed reasons in ``_classify``.
_SIGNALS = ("offer", "rejected", "declined", "withdrawn", "ongoing", "none")


@dataclass(frozen=True)
class UnitExtraction:
    """One unit's extracted company/role + outcome signal (pre-clustering)."""

    unit_id: UUID
    company: str
    role: str
    signal: str  # one of _SIGNALS


@dataclass(frozen=True)
class CandidateOpportunity:
    """A clustered candidate opportunity, system-suggested for the operator (D215).

    ``status`` is ``live`` or ``closed``; ``closed_reason`` (one of S103n's five) is
    set only when ``closed`` and the content/staleness supports it."""

    name: str
    company: str
    role: str
    unit_ids: tuple[UUID, ...]
    status: str
    closed_reason: str | None


EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "company": {"type": "string"},
                    "role": {"type": "string"},
                    "outcome_signal": {"type": "string", "enum": list(_SIGNALS)},
                },
                "required": ["index", "company", "role", "outcome_signal"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def build_extraction_prompt(
    items: tuple[tuple[str, str], ...]
) -> str:
    """Build the extraction prompt over a batch of units (S103o, D215).

    ``items`` is an ordered tuple of (subject, body_snippet); the model returns one
    row per ``index`` (1-based), so the caller maps index back to unit id without
    the model echoing a UUID. The prompt teaches it to read the *real hiring
    company* from the content, not the ATS or job-board sender.
    """
    lines = []
    for i, (subject, body) in enumerate(items, start=1):
        snippet = (body or "")[:600].replace("\n", " ").strip()
        lines.append(f"[{i}] subject: {subject or '(none)'}\n    body: {snippet}")
    listing = "\n".join(lines)
    return (
        "You read job-search emails and extract, for each, the real hiring company, "
        "the role, and any outcome signal. The sender is often an applicant-tracking "
        "system (e.g. Ashby, Greenhouse, Lever) or a job board (LinkedIn) — the real "
        "company is named in the subject or body, not the sender, so read the "
        "content.\n\n"
        "For each numbered item return:\n"
        "- index: the item's number.\n"
        "- company: the real hiring company (short name, e.g. 'Acme'); empty string "
        "if it is a generic board digest or you cannot tell.\n"
        "- role: the role/title if present, else empty string.\n"
        "- outcome_signal: one of — 'offer' (an offer was made), 'rejected' (they "
        "turned you down), 'declined' (you turned them down / withdrew interest), "
        "'withdrawn' (the role was pulled or the process killed), 'ongoing' (active "
        "back-and-forth, no outcome yet), 'none' (a one-off with no outcome signal).\n"
        "Report only what the content supports; use 'ongoing' or 'none' when unsure, "
        "never invent a rejection or offer.\n\n"
        f"Items:\n{listing}"
    )


def parse_extraction(
    value: dict[str, Any], unit_ids: tuple[UUID, ...]
) -> tuple[UnitExtraction, ...]:
    """Map the model's batch response to ``UnitExtraction``s (pure, defensive).

    Rows with an out-of-range index, a non-string company/role, or an unknown
    signal are dropped; an empty company is kept (it falls out of clustering as
    un-extractable). ``unit_ids`` is the same order the prompt listed.
    """
    if not isinstance(value, dict):
        return ()
    rows = value.get("items")
    if not isinstance(rows, list):
        return ()
    out: list[UnitExtraction] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        idx = row.get("index")
        if not isinstance(idx, int) or not (1 <= idx <= len(unit_ids)):
            continue
        if idx in seen:
            continue
        seen.add(idx)
        company = row.get("company")
        role = row.get("role")
        signal = row.get("outcome_signal")
        if not isinstance(company, str) or not isinstance(role, str):
            continue
        if signal not in _SIGNALS:
            signal = "none"
        out.append(
            UnitExtraction(
                unit_id=unit_ids[idx - 1],
                company=company.strip(),
                role=role.strip(),
                signal=signal,
            )
        )
    return tuple(out)


def _signature(company: str, role: str) -> str:
    return f"{company.strip().lower()}|{role.strip().lower()}"


def _classify(
    signals: frozenset[str], latest: datetime | None, now: datetime, stale_days: int
) -> tuple[str, str | None]:
    """Status + reason for a cluster from its units' signals (and staleness).

    Content signals win (strongest-outcome first); with no close signal a stale
    cluster reads went-cold, otherwise it stays live for the operator to confirm —
    never asserting a reason the content does not support (S103n)."""
    if "offer" in signals:
        return ("closed", "won")
    if "rejected" in signals:
        return ("closed", "rejected")
    if "declined" in signals:
        return ("closed", "declined")
    if "withdrawn" in signals:
        return ("closed", "withdrawn_or_killed")
    if latest is not None and (now - latest) > timedelta(days=stale_days):
        return ("closed", "went_cold")
    return ("live", None)


def cluster_and_classify(
    extractions: tuple[UnitExtraction, ...],
    *,
    latest_by_unit: dict[UUID, datetime] | None = None,
    now: datetime,
    min_touches: int = _MIN_TOUCHES,
    stale_days: int = STALE_DAYS,
) -> tuple[CandidateOpportunity, ...]:
    """Group multi-touch company-and-role signatures into candidate opportunities,
    classified live/closed (pure, S103o/D215).

    A signature needs a non-empty company and ``min_touches`` units; single-touch or
    un-extracted (empty-company) units fall out as the honest unclustered remainder.
    The name is "Company — Role" (or just the company when the role is empty).
    """
    latest_by_unit = latest_by_unit or {}
    by_sig: dict[str, list[UnitExtraction]] = {}
    label: dict[str, tuple[str, str]] = {}
    for ex in extractions:
        if not ex.company:
            continue  # un-extractable: stays in the unclustered remainder
        sig = _signature(ex.company, ex.role)
        by_sig.setdefault(sig, []).append(ex)
        label.setdefault(sig, (ex.company, ex.role))

    out: list[CandidateOpportunity] = []
    for sig, members in by_sig.items():
        if len(members) < min_touches:
            continue
        company, role = label[sig]
        signals = frozenset(m.signal for m in members)
        times = [
            latest_by_unit[m.unit_id]
            for m in members
            if m.unit_id in latest_by_unit
        ]
        latest = max(times) if times else None
        status, reason = _classify(signals, latest, now, stale_days)
        name = f"{company} — {role}" if role else company
        out.append(
            CandidateOpportunity(
                name=name,
                company=company,
                role=role,
                unit_ids=tuple(m.unit_id for m in members),
                status=status,
                closed_reason=reason,
            )
        )
    # Deterministic order (name) so a re-run instantiates identically.
    return tuple(sorted(out, key=lambda c: c.name.lower()))


__all__ = [
    "CandidateOpportunity",
    "EXTRACTION_SCHEMA",
    "STALE_DAYS",
    "UnitExtraction",
    "build_extraction_prompt",
    "cluster_and_classify",
    "parse_extraction",
]
