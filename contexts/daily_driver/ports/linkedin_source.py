"""The LinkedIn source port (S103v, D223).

"Give me the member's LinkedIn contacts." The sole **built** adapter parses the
member's **self-export archive** (``ops/linkedin_archive_source.py``,
``SelfExportArchiveSource``) — the route available to every member globally
including the UK, the operator's own consented data, no API and no scraping.

**Deferred adapter (documented, not built): the DMA Member Data Portability API.**
The EU Digital Markets Act forces large platforms to release user data via the
LinkedIn Member Snapshot API (CONNECTIONS and INBOX domains). Token generation is
restricted to members in the **EEA and Switzerland**; the operator is **UK-based**
(the UK left the EEA after Brexit), so the API is closed to this operator today. A
``DmaSnapshotApiSource`` adapter would implement this same port and slot in behind
it if UK eligibility opens under its own Digital Markets, Competition and Consumers
regime — the port exists precisely so that later drop-in requires no change to the
seed or the proof loop. It is **not stubbed**; only named here.

Read-only: the adapter reads the archive, it never writes to any LinkedIn surface.
No vendor SDK in domain — the CSV parse (``domain/linkedin_parse.py``) is stdlib.
"""

from __future__ import annotations

from typing import Protocol

from contexts.daily_driver.domain.linkedin_parse import LinkedInContact


class LinkedInSource(Protocol):
    def load(self) -> tuple[LinkedInContact, ...]:
        """The member's LinkedIn contacts (connections + message senders), parsed
        from the source. Empty when the source yields nothing."""
        ...


__all__ = ["LinkedInSource"]
