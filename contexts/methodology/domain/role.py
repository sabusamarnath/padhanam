"""Role aggregates (D86).

Two frozen dataclasses inheriting D74's revision-shape precedent from
``MethodologyTemplate`` / ``MethodologyRevision``. The role aggregate
lives within ``contexts/methodology/`` per D86's Y2 sub-choice (Phase 1
co-locates role with methodology context; promotion to its own bounded
context defers to Phase 2 if evidence demands).

The role aggregate is the structural home for the constraint bundle
(system_prompt, source_ids, tool_allowlist, retrieval_strategy,
filter_tree, top_k, min_score, model_selection) that previously lived
on ``methodology_revisions`` per D74. D86 refactors methodology to a
playbook composing role references via ``role_refs`` (S26a-1 commit 3);
this module is the role half of that refactor.

Per D74's chain-self-containment reasoning, the parent template's
``name`` and ``description`` appear in the hash content payload at
hash-computation time even though they are not persisted columns on
``role_revisions``. Chain integrity verification reconstructs the
payload by reading the parent template's metadata (immutable per the
template aggregate) and the revision's persisted content fields. The
canonical-JSON pattern mirrors D74 / D75 exactly so the hash-chain
primitive at ``padhanam/security/hash_chain.py`` handles role chains
without modification.

Per D86's idealization-versus-implementation reconciliation, the role
bundle uses ``source_ids`` (matching the prior methodology shape) and
omits ``cost_ceiling``; D86's wording named ``source_filter`` and
``cost_ceiling`` but Phase 1 implements with existing field names to
avoid introducing schema concepts without consumers. Cost-ceiling
forward-affordance already exists at the tenant-registry level per D41
and is unread until Phase 2 enforcement consumes it.

Domain code is framework-free per D16 — stdlib dataclasses, no
Pydantic, no SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID

from shared_kernel import ToolAllowlistEntry


@dataclass(frozen=True)
class RoleTemplate:
    """Role template aggregate (D86).

    Immutable identity for a role. Retirement marks ``archived_at``
    while leaving revisions intact for existing methodology-references
    per D31's append-only-at-version-level discipline. The methodology
    aggregate references this role by id (and version pinning at the
    revision level) via ``role_refs``; existing references survive
    archival of the parent template, mirroring D68's clone independence
    pattern.
    """

    id: UUID
    name: str
    description: str | None
    created_by_user_id: str
    created_at: datetime
    archived_at: datetime | None = None


@dataclass(frozen=True)
class RoleRevision:
    """Role revision aggregate (D86).

    Immutable per D31. ``previous_revision_hash`` chains forward from
    the genesis sentinel (``GENESIS_REVISION_HASH``) per template;
    ``this_revision_hash`` is the SHA-256 of the canonical-JSON content
    payload (including the parent template's name and description plus
    the previous hash as a payload key) per D26 inheriting the audit-
    mirror shape from D74 / S23.

    JSONB-backed fields (``retrieval_strategy``, ``filter_tree``) carry
    their wire shapes per D66 and D67; the methodology context treats
    them as opaque payload, with consumer interpretation landing at the
    agent runtime in P8.
    """

    id: UUID
    role_template_id: UUID
    version: int
    system_prompt: str
    source_ids: tuple[UUID, ...]
    tool_allowlist: tuple[ToolAllowlistEntry, ...]
    retrieval_strategy: Mapping[str, Any]
    filter_tree: Mapping[str, Any]
    top_k: int
    min_score: Decimal
    model_selection: str
    created_by_user_id: str
    created_at: datetime
    previous_revision_hash: str
    this_revision_hash: str
