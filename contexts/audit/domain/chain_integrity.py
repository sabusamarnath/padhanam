"""Chain integrity status types for the read-side verifier (D102, S36).

Page-granularity chain verification per D102 surfaces three
states for a returned page:

- ``verified``: every row's stored ``this_event_hash`` recomputes
  from payload plus stored ``previous_event_hash`` via
  ``compute_event_hash``, and consecutive rows within the page
  link correctly (row N's ``this_event_hash`` equals row N+1's
  ``previous_event_hash``).
- ``broken_at_row``: a specific row failed verification.
  ``broken_at_id`` carries the offending event's ``id``.
- ``partial``: the page does not cover a chain segment large
  enough to verify deterministically. Surfaces when the page
  has fewer than two rows OR when the filter vocabulary's
  selectivity returned non-contiguous rows.

The status is purely a property of the returned page; full-chain
verification across the entire chain is out of scope per D102
and deferred to Phase 2 or operator-evidence-triggered. The
reusable primitives ``compute_event_hash`` and ``GENESIS_HASH``
at ``contexts.audit.domain.events`` are the building blocks; the
existing ``verify_chain`` walker is NOT reused per D102
alternative (h) — it walks from genesis and a mid-chain page
defeats its head-equals-GENESIS assertion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


ChainIntegrityStatus = Literal["verified", "broken_at_row", "partial"]


@dataclass(frozen=True)
class ChainIntegrityVerification:
    """Result of verifying chain integrity on a returned page.

    ``broken_at_id`` is required when ``status == 'broken_at_row'``
    and prohibited otherwise; the invariant fires at construction
    time so consumers cannot read a status that the
    ``broken_at_id`` shape contradicts.
    """

    status: ChainIntegrityStatus
    broken_at_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.status == "broken_at_row" and self.broken_at_id is None:
            raise ValueError(
                "ChainIntegrityVerification.broken_at_id is required when "
                "status == 'broken_at_row'"
            )
        if self.status != "broken_at_row" and self.broken_at_id is not None:
            raise ValueError(
                "ChainIntegrityVerification.broken_at_id must be None when "
                f"status == {self.status!r}; got {self.broken_at_id!r}"
            )


__all__ = ["ChainIntegrityStatus", "ChainIntegrityVerification"]
