"""Methodology aggregates (D74, D86).

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

S26a-1 (D86) refactor: ``MethodologyRevision`` loses the constraint
bundle (system_prompt, source_ids, tool_allowlist, retrieval_strategy,
filter_tree, top_k, min_score, model_selection) which moves to the
role aggregate; ``MethodologyRevision`` gains ``role_refs`` carrying
references to role templates plus optional per-role overrides. The
methodology aggregate becomes a playbook composing roles; the role
aggregate carries the constraint bundle.

Domain code is framework-free per D16 — stdlib dataclasses, no
Pydantic, no SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class RoleRef:
    """Reference from a methodology revision to a role revision (D86, D87).

    Carries the role identity (role_id), the pinned role version
    (role_version), and methodology-context-specific overrides
    (overrides).

    Per D87 (S26b), ``overrides`` is ``dict[str, dict[str, Any]]``
    keyed by role-bundle field name; each value is the canonical
    ``{"mode": <str>, "value": <any>}`` shape with mode drawn from
    ``{augment, replace, tighten}``. Authoring goes through
    ``contexts/methodology/domain/overrides.py:project_overrides``
    which projects flat values to the structured form using the
    per-field default-mode table and validates admissibility.

    Empty overrides (``{}``) is the trivial no-op and represents an
    unmodified role reference. The canonical-JSON encoder at the
    methodology hash payload helper maps empty overrides to ``null``
    for byte-stability with pre-D87 LVT methodology hashes.
    """

    role_id: UUID
    role_version: int
    overrides: dict[str, dict[str, Any]] = field(default_factory=dict)


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
    """Methodology revision aggregate (D74, refactored per D86 at S26a-1).

    Immutable per D31. ``previous_revision_hash`` chains forward from
    the genesis sentinel (``GENESIS_REVISION_HASH``) per template;
    ``this_revision_hash`` is the SHA-256 of the canonical-JSON
    content payload (including the parent template's name plus the
    previous hash as a payload key) per D26 mirroring the audit-chain
    pattern at ``contexts/audit/domain/events.py:67-81``.

    Per D86, the revision's content surface is ``role_refs`` rather
    than the prior constraint bundle. Each ``RoleRef`` resolves to a
    role revision at clone time (see the agent context's
    ``MethodologyLookupAdapter`` at ``apps/cli/_cross_context.py``);
    the methodology's hash payload spans the sorted role_refs (by
    role_id for determinism) without resolving them.
    """

    id: UUID
    methodology_template_id: UUID
    version: int
    role_refs: tuple[RoleRef, ...]
    created_by_user_id: str
    created_at: datetime
    previous_revision_hash: str
    this_revision_hash: str
