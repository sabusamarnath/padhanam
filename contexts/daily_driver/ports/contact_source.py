"""The contact source port (S103x, D230) — the general "give me contacts"
abstraction the Google Contacts adapter implements.

The S103v LinkedIn adapter predates this and uses its own `LinkedInSource`/
`LinkedInContact`; folding it into this general port is a deferred tidy. A
`ContactSource` yields `SourcedContact`s (name + company); the seed sets the
channel (`capture_source`) and does the dedup, so the port stays channel-agnostic.
"""

from __future__ import annotations

from typing import Protocol

# ``SourcedContact`` is a pure value object, so it lives in the domain; the port
# re-exports it for the adapters/seed (S103z hexagonal-contract fix — a domain
# module such as ``google_contacts_parse`` must not import from ``ports``).
from contexts.daily_driver.domain.contacts import SourcedContact


class ContactSource(Protocol):
    async def load(self) -> tuple[SourcedContact, ...]:
        """The contacts from this source. Empty when the source yields nothing."""
        ...


__all__ = ["ContactSource", "SourcedContact"]
