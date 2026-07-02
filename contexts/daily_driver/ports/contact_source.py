"""The contact source port (S103x, D230) — the general "give me contacts"
abstraction the Google Contacts adapter implements.

The S103v LinkedIn adapter predates this and uses its own `LinkedInSource`/
`LinkedInContact`; folding it into this general port is a deferred tidy. A
`ContactSource` yields `SourcedContact`s (name + company); the seed sets the
channel (`capture_source`) and does the dedup, so the port stays channel-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SourcedContact:
    """One contact parsed from a source (S103x, D230). ``company`` is the linking
    key for warm access; a contact with no company is dropped by the seed's filter."""

    name: str
    company: str | None


class ContactSource(Protocol):
    async def load(self) -> tuple[SourcedContact, ...]:
        """The contacts from this source. Empty when the source yields nothing."""
        ...


__all__ = ["ContactSource", "SourcedContact"]
