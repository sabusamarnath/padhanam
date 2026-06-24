"""EmailSourceMetadataSource — per-email sender domain + thread size (D209).

The source-class taxonomy (D209, Mechanism A) needs the email's sender domain and
its thread size, which the title-only ``WorkFacet`` does not carry. The matcher
domain stays metadata-light (D16), so the use case reads this port and the apps
composition root wires it to the email store (the D184 use-case-sees-context
pattern, the ``EmailJobSearchSource`` precedent). ``facet_id`` is the email's id
(the ``:Facet`` reference). Pure ports layer — no SQLAlchemy here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from shared_kernel import ActorContext


@dataclass(frozen=True)
class EmailSourceMetadata:
    """One email's source signal: ``domain`` is the sender's domain (lower-cased,
    empty when absent); ``thread_size`` is how many of the tenant's emails share
    its ``thread_id`` (1 = one-touch, the pipeline-vs-opportunity signal)."""

    facet_id: UUID
    domain: str
    thread_size: int


class EmailSourceMetadataSource(Protocol):
    async def list_source_metadata(
        self, *, actor: ActorContext
    ) -> tuple[EmailSourceMetadata, ...]:
        """The tenant's emails' sender domain + thread size, for the source-class
        taxonomy (D209). Empty when the email cache is empty."""
        ...


__all__ = ["EmailSourceMetadata", "EmailSourceMetadataSource"]
