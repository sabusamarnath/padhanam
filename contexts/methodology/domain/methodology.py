"""Methodology aggregates (D74).

Two frozen dataclasses follow D31's revision-shape precedent. The
template carries human-stable identity; the revision carries
per-version content plus the hash-chain pointers per D26. Revisions
are immutable; updates create new revision rows.

Per D74's "chain-self-containment" reasoning, the parent template's
name appears in the hash content payload at hash computation time
even though it is not a persisted column on ``methodology_revisions``.
Chain integrity verification reconstructs the payload by reading the
parent template's name (immutable per the template aggregate) and
the revision's persisted content fields. The simpler alternative
(denormalising name as a column on the revisions table) is deferred
until a later session demands stricter chain self-containment that
verification-without-joins would require.

Domain code is framework-free per D16 — stdlib dataclasses, no
Pydantic, no SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID


@dataclass(frozen=True)
class MethodologyTemplate:
    """Methodology template aggregate (D74).

    Immutable identity for a methodology. Retirement marks
    ``archived_at`` while leaving revisions intact for existing
    clone-references per D68.
    """

    id: UUID
    name: str
    description: str | None
    created_by_user_id: str
    created_at: datetime
    archived_at: datetime | None = None


@dataclass(frozen=True)
class MethodologyRevision:
    """Methodology revision aggregate (D74).

    Immutable per D31. ``previous_revision_hash`` chains forward from
    the genesis sentinel (``GENESIS_REVISION_HASH``) per template;
    ``this_revision_hash`` is the SHA-256 of the canonical-JSON
    content payload (including the parent template's name plus the
    previous hash as a payload key) per D26 mirroring the audit-chain
    pattern at ``contexts/audit/domain/events.py:67-81``.

    JSONB-backed fields (``retrieval_strategy``, ``filter_tree``)
    carry their wire shapes per D66 and D67; the methodology context
    treats them as opaque payload, with consumer interpretation
    landing at the agent runtime in P8.
    """

    id: UUID
    methodology_template_id: UUID
    version: int
    system_prompt: str
    source_ids: tuple[UUID, ...]
    tool_allowlist: tuple[str, ...]
    retrieval_strategy: Mapping[str, Any]
    filter_tree: Mapping[str, Any]
    top_k: int
    min_score: Decimal
    model_selection: str
    created_by_user_id: str
    created_at: datetime
    previous_revision_hash: str
    this_revision_hash: str
