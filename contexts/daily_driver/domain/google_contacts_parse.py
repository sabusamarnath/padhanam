"""Pure parser for Google People API `connections` (S103x, D230). Stdlib only (D16);
no vendor SDK, no I/O — the adapter fetches, this parses.

Reconciled against the People API (`people.connections.list`, current Google docs):
a connection carries ``names`` (``[{displayName}]``), ``emailAddresses``, and
``organizations`` (``[{name, title}]``). The **company comes from the organisations
field directly** (no extraction, unlike the email seed where ATS domains hid it), and
the seed **filters to organisation-carrying contacts** — a company-less personal
contact (family, friends) cannot link to a lead and would flood the proof queue.
"""

from __future__ import annotations

from contexts.daily_driver.ports.contact_source import SourcedContact


def _display_name(person: dict) -> str:
    names = person.get("names") or []
    if names:
        n = names[0]
        return (n.get("displayName") or
                f"{n.get('givenName', '')} {n.get('familyName', '')}").strip()
    return ""


def _company(person: dict) -> str | None:
    orgs = person.get("organizations") or []
    for o in orgs:
        name = (o.get("name") or "").strip()
        if name:
            return name
    return None


def parse_people_connections(
    connections: list[dict],
) -> tuple[SourcedContact, ...]:
    """Map People API connections to SourcedContacts, **filtered to those carrying an
    organisation** (D230). Company-less contacts are dropped."""
    out: list[SourcedContact] = []
    for person in connections or []:
        company = _company(person)
        if not company:
            continue  # the organisation filter — personal contacts don't seed
        name = _display_name(person)
        if not name:
            continue
        out.append(SourcedContact(name=name, company=company))
    return tuple(out)


__all__ = ["parse_people_connections"]
