"""Agent aggregates (D75, D86).

Two frozen dataclasses inheriting D74's revision-shape pattern from
the methodology context. The template carries human-stable identity
plus two independent lineage pairs (methodology and role); the
revision carries per-version content plus the hash-chain pointers per
D26. Revisions are immutable; updates create new revision rows.

Per D75's chain-self-containment reasoning, the parent template's
``name`` and ``description`` appear in the hash content payload at
hash-computation time even though they are not persisted columns on
``agent_revisions``. Chain integrity verification reconstructs the
payload by reading the parent template's metadata (immutable per the
template aggregate) and the revision's persisted content fields. This
mirrors the methodology context's actual implementation from S23
rather than D74's text; the literal-denormalisation alternative
(persisting name and description as columns on the revisions table)
was rejected at D75 alternative (h)'s discussion because the second-
consumer moment is the cheapest moment to settle the helper API
shape, and chain-self-containment is satisfied at the canonical-JSON
payload-key level without column duplication.

Lineage fields (``source_methodology_template_id``,
``source_methodology_template_version``, ``source_role_id``,
``source_role_version``) live on AgentTemplate per D75 / D86:
lineage is template-level identity (origin), not revision-level
content (what changes between versions). Placement on the template
structurally enforces D68's "set immutably on revision 1, preserved
across all later revisions" because the template never changes after
creation; the lineage cannot drift across revisions because it does
not exist on the revision. The four fields form two independent
paired-NULL pairs (methodology and role); see the paired-NULL
invariant section below for the three valid combinations.

The paired-NULL invariant is enforced at the domain layer via
``__post_init__`` validation on the frozen dataclass: instantiation
with exactly one of a pair's two fields populated raises
``ValueError``. The same invariant is enforced at the schema layer
via the CHECK constraints ``agent_templates_lineage_paired_null``
(methodology pair) and ``agent_templates_role_lineage_paired_null``
(role pair); the two-layer enforcement matches the audit-context
precedent of domain-layer validation backed by schema-layer
constraint.

Three valid lineage states match charter/schema.md's "Agent tables"
section: both pairs NULL (blank-created); both pairs populated
(methodology-cloned, with role lineage resolved from the methodology
revision's first role_ref per S25's D79 cross-context flow extended
at S26a-2); only role pair populated (role-cloned directly without a
methodology playbook per S26a-2's create_agent_from_role).

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
class AgentTemplate:
    """Agent template aggregate (D75).

    Immutable identity for an agent. Archive marks ``archived_at``
    while leaving revisions intact for audit purposes per D31's
    append-only-at-version-level discipline.
    """

    id: UUID
    name: str
    description: str | None
    created_by_user_id: str
    created_at: datetime
    source_methodology_template_id: UUID | None = None
    source_methodology_template_version: int | None = None
    source_role_id: UUID | None = None
    source_role_version: int | None = None
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        # D75 paired-NULL invariant: methodology lineage fields move
        # together. Either both NULL (blank-created agent at S24 or
        # role-created agent at S26a-2) or both populated (clone-
        # created from a methodology template at S25's cross-context
        # flow). Never one without the other.
        m_id_set = self.source_methodology_template_id is not None
        m_version_set = self.source_methodology_template_version is not None
        if m_id_set != m_version_set:
            raise ValueError(
                "AgentTemplate methodology lineage fields must move "
                "together (D75 paired-NULL invariant): both NULL or "
                "both populated; got "
                f"source_methodology_template_id={self.source_methodology_template_id!r}, "
                f"source_methodology_template_version={self.source_methodology_template_version!r}"
            )

        # D86 paired-NULL invariant on the role lineage pair,
        # independent of the methodology pair. Three valid
        # combinations across both pairs per charter/schema.md:
        # both pairs NULL (blank-created); both pairs populated
        # (methodology-cloned, role resolved from role_refs[0]);
        # only role pair populated (role-cloned directly).
        r_id_set = self.source_role_id is not None
        r_version_set = self.source_role_version is not None
        if r_id_set != r_version_set:
            raise ValueError(
                "AgentTemplate role lineage fields must move "
                "together (D86 paired-NULL invariant): both NULL or "
                "both populated; got "
                f"source_role_id={self.source_role_id!r}, "
                f"source_role_version={self.source_role_version!r}"
            )


@dataclass(frozen=True)
class AgentRevision:
    """Agent revision aggregate (D75).

    Immutable per D31. ``previous_revision_hash`` chains forward
    from the genesis sentinel (``"0" * 64``) per template;
    ``this_revision_hash`` is the SHA-256 of the canonical-JSON
    content payload (including the parent template's name and
    description plus the previous hash as a payload key) per D26
    inheriting the audit-mirror shape from D74 / S23.

    JSONB-backed fields (``retrieval_strategy``, ``filter_tree``)
    carry their wire shapes per D66 and D67; the agent context
    treats them as opaque payload, with consumer interpretation
    landing at the agent runtime in P8.
    """

    id: UUID
    agent_template_id: UUID
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
