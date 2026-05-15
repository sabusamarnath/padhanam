"""Gold-set revision value object (D109 commitment 2).

The revision is the append-only unit of gold-set authoring. Status
transitions from ``draft`` to ``finalized``; finalized revisions
never mutate per D31. Corrections happen as new revisions opened by
the ``finalize_revision`` use case, never as in-place edits.

Per D109 commitment 4, hash-chain audit at finalization computes
``this_event_hash`` over the revision's canonical payload via
``contexts.retrieval_evaluation.domain.hash_chain.compute_revision_hash``,
which delegates to ``padhanam.security.hash_chain.compute_revision_hash``
(the field-set-agnostic primitive promoted at S24 per D75). The
genesis revision uses ``GENESIS_REVISION_HASH`` from the same
platform module as ``previous_event_hash``.

Naming note: the field names ``this_event_hash`` and
``previous_event_hash`` follow D109 commitment 2's audit-mirror
convention. The platform hash-chain primitive's payload encodes the
predecessor's hash under the key ``previous_revision_hash``; the
field-name-versus-payload-key divergence is a small cosmetic point
recorded for the P12 audit but is not load-bearing because the
canonical payload encoding stays internal to the platform helper.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class GoldSetRevisionStatus(str, Enum):
    """Revision lifecycle (D109 commitment 2).

    ``draft`` revisions accept entry appends and re-edits. The
    ``finalize_revision`` use case at the application layer transitions
    ``draft`` to ``finalized`` and computes ``this_event_hash`` at the
    transition; ``finalized`` revisions are immutable per D31.
    """

    DRAFT = "draft"
    FINALIZED = "finalized"


@dataclass(frozen=True)
class GoldSetRevision:
    """One revision of a gold set.

    Append-only per D31. ``previous_event_hash`` chains forward from
    ``GENESIS_REVISION_HASH`` per gold-set; ``this_event_hash`` is the
    SHA-256 of the canonical-JSON revision payload computed at
    finalization via the platform hash-chain primitive.
    """

    id: UUID
    gold_set_id: UUID
    revision_number: int
    status: GoldSetRevisionStatus
    created_by_user_id: str
    created_at: datetime
    finalized_at: datetime | None
    this_event_hash: str | None
    previous_event_hash: str | None

    def __post_init__(self) -> None:
        if self.revision_number < 1:
            raise ValueError(
                f"revision_number must be >= 1, got {self.revision_number}"
            )
        if self.status is GoldSetRevisionStatus.FINALIZED:
            if self.finalized_at is None:
                raise ValueError(
                    "finalized_at must be set on a finalized revision"
                )
            if self.this_event_hash is None:
                raise ValueError(
                    "this_event_hash must be set on a finalized revision"
                )
            if self.previous_event_hash is None:
                raise ValueError(
                    "previous_event_hash must be set on a finalized revision"
                )
        else:
            if self.finalized_at is not None:
                raise ValueError(
                    "finalized_at must be None on a draft revision"
                )
            if self.this_event_hash is not None:
                raise ValueError(
                    "this_event_hash must be None on a draft revision"
                )

    @property
    def is_finalized(self) -> bool:
        return self.status is GoldSetRevisionStatus.FINALIZED
