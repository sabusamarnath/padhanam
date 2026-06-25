"""EmailContentSource — one email's read-only ingested content (D212).

The verification drawer's openable-source leg (D212): a linked item opens to its
read-only source — sender, date, subject, body — so reading the email to confirm a
bind is the default action. The matcher domain stays metadata-light (D16), so the
use case reads this port and the apps composition root wires it to the email store
(the ``EmailSourceMetadata``/D184 precedent). Read-only: it shows ingested content,
it never fetches or writes (design-language §9, D148/D151). ``facet_id`` is the
email facet's id (the ``Email`` row id). Pure ports layer — no SQLAlchemy here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from shared_kernel import ActorContext


@dataclass(frozen=True)
class EmailContent:
    """One email's read-only content for the drawer (D212). All content fields are
    optional — an ingested email may lack a body or a parsed sender."""

    facet_id: UUID
    sender: str | None
    received_at: datetime | None
    subject: str | None
    body: str | None


class EmailContentSource(Protocol):
    async def get_email_content(
        self, *, actor: ActorContext, facet_id: UUID
    ) -> EmailContent | None:
        """The email facet's sender, date, subject, and body — read-only ingested
        content (D212). None when the facet is not an email or is absent."""
        ...


__all__ = ["EmailContent", "EmailContentSource"]
