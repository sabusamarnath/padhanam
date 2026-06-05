"""Calendar-to-domain mapping (D159).

A connected calendar carries a domain tag (work / personal / family) set
when the calendar is included, and its events inherit it (design-language
§9). At single-personal-calendar scale the tag is one connection-level
default resolved here; per-calendar persisted tags are deferred to the
second-calendar threshold (the two-threshold rule).

Pure domain logic — stdlib only, framework-free per D16.
"""

from __future__ import annotations

# The domain tags the Today surface types a row by (design-language §2).
KNOWN_CALENDAR_DOMAINS: frozenset[str] = frozenset(
    {"work", "personal", "family"}
)

DEFAULT_CALENDAR_DOMAIN = "work"


def resolve_calendar_domain(
    tag: str | None, *, default: str = DEFAULT_CALENDAR_DOMAIN
) -> str:
    """Resolve a calendar's domain tag to a known domain.

    An unset or unrecognised tag falls back to ``default`` (itself a known
    domain) so a calendar always types its events; the surface never
    renders an unknown domain. The mapping is fixed at connection time
    (D159): the calendar holds the tag, the event inherits it.
    """
    normalised = (tag or "").strip().lower()
    if normalised in KNOWN_CALENDAR_DOMAINS:
        return normalised
    if default in KNOWN_CALENDAR_DOMAINS:
        return default
    return DEFAULT_CALENDAR_DOMAIN


__all__ = [
    "DEFAULT_CALENDAR_DOMAIN",
    "KNOWN_CALENDAR_DOMAINS",
    "resolve_calendar_domain",
]
