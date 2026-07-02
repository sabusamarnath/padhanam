"""The contact graph domain — warm access derived from proofed contacts (S103u,
D222). Pure (D16, stdlib only).

A :Contact is a person in the operator's network, linked to a company by a
normalized company string (the S103o signature — no :Company node). A lead's warm
access derives from whether a **usable** contact links to its company; the S103t
manual tag is the override. The operator authors degree/strength/reachability
(D200), so an unproofed contact carries no path yet — the graph is evidence only
once proofed, which is what turns the self-reported tag into evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

# The authored vocabularies (D222). None until the operator proofs (D200).
DEGREES = ("first", "second")
STRENGTHS = ("close", "medium", "weak")
REACHABILITIES = ("easy", "hard")
CAPTURE_SOURCES = ("email", "linkedin", "manual")

_STRENGTH_RANK = {"close": 0, "medium": 1, "weak": 2}
_DEGREE_RANK = {"first": 0, "second": 1}


@dataclass(frozen=True)
class ContactView:
    """One contact as read for the surface + the derive (D222)."""

    contact_id: UUID
    name: str
    email: str | None
    company: str | None
    degree: str | None
    strength: str | None
    reachability: str | None
    capture_source: str
    provenance_origin: str


def normalize_company(name: str | None) -> str:
    """The company match key — lower-cased, trimmed (the S103o signature precedent).
    A lead's company is its opportunity name before ' — '; a contact's is its
    ``company`` field. Both normalize through here so the join is symmetric."""
    return (name or "").strip().lower()


def lead_company(opportunity_name: str) -> str:
    """A lead's company is its opportunity name before ' — ' (S103t)."""
    return opportunity_name.split(" — ", 1)[0].strip()


def is_usable(contact: ContactView) -> bool:
    """A contact offers a warm path when it is proofed strong-enough or easily
    reachable (D222): ``strength`` close/medium, or ``reachability`` easy. An
    unproofed contact (all None) is not yet usable — the operator must author the
    relationship first (D200)."""
    return contact.strength in ("close", "medium") or contact.reachability == "easy"


def contacts_for_company(
    company: str, contacts: tuple[ContactView, ...]
) -> tuple[ContactView, ...]:
    """The contacts linking to ``company`` by normalized match."""
    nc = normalize_company(company)
    if not nc:
        return ()
    return tuple(c for c in contacts if normalize_company(c.company) == nc)


def derive_warm(company: str, contacts: tuple[ContactView, ...]) -> str:
    """Derive a lead's warm access from its company's contacts (D222): ``warm`` when
    at least one usable contact links to the company, else ``cold``."""
    return "warm" if any(is_usable(c) for c in contacts_for_company(company, contacts)) else "cold"


def effective_warm(
    override: str | None, company: str, contacts: tuple[ContactView, ...]
) -> str:
    """The effective warm access: the manual override when set, else the derived
    value (the D217 manual-over-computed precedent)."""
    if override in ("warm", "cold"):
        return override
    return derive_warm(company, contacts)


def _best(contacts: tuple[ContactView, ...]) -> ContactView:
    """The strongest usable contact — first-degree before second, close before weak."""
    return min(
        contacts,
        key=lambda c: (
            _DEGREE_RANK.get(c.degree or "", 9),
            _STRENGTH_RANK.get(c.strength or "", 9),
            0 if c.reachability == "easy" else 1,
        ),
    )


_STEP_LABELS = {
    "intro_requested": "intro requested", "follow_up_sent": "follow-up sent",
    "referral_asked": "referral asked", "message_sent": "message sent",
}


def warming_action(
    company: str,
    contacts: tuple[ContactView, ...],
    last_step: tuple[str, int] | None = None,
) -> str:
    """The contact-specific warming next-best-action (D222) — names the real
    contact and the act (referral vs intro), or nudges to proof / add a contact.

    When a warming step has been logged against the lead (D224), the action advances
    to reflect it ("intro requested 6 days ago — follow up"), reading ``last_step``
    as ``(kind, days_ago)``."""
    if last_step is not None:
        kind, days_ago = last_step
        label = _STEP_LABELS.get(kind, kind.replace("_", " "))
        when = "today" if days_ago <= 0 else (
            "yesterday" if days_ago == 1 else f"{days_ago} days ago"
        )
        if kind == "intro_requested":
            return f"Intro requested {when} — follow up if there is no reply."
        if kind == "referral_asked":
            return f"Referral asked {when} — follow up or thank them."
        return f"Last warming: {label} {when} — keep the thread warm."
    matches = contacts_for_company(company, contacts)
    usable = tuple(c for c in matches if is_usable(c))
    if usable:
        c = _best(usable)
        if c.degree == "second":
            return f"You know {c.name}, who can reach someone at {company} — ask for a warm intro."
        if c.strength == "close":
            return f"You know {c.name} here — first-degree, close. Ask for a referral."
        return f"You know {c.name} here — ask for a referral or a warm intro."
    if matches:
        n = len(matches)
        s = "" if n == 1 else "s"
        return f"You have {n} unproofed contact{s} at {company} — proof their strength to confirm the path."
    return f"No path yet at {company} — find or add a contact who can introduce you."


__all__ = [
    "CAPTURE_SOURCES", "ContactView", "DEGREES", "REACHABILITIES", "STRENGTHS",
    "contacts_for_company", "derive_warm", "effective_warm", "is_usable",
    "lead_company", "normalize_company", "warming_action",
]
