"""Methodology CRUD use cases (D74).

Five policy-aware coroutines wrapping ``MethodologyRepositoryPort``.
Operator-context enforcement at the use case layer per D34, mirroring
``register_tenant`` / ``update_tenant_status`` /
``reveal_connection_config``. ``OPERATOR_ROLE`` and ``is_operator``
imported from ``padhanam.security.policy`` (promoted from the tenancy
context at S23 commit 8 so the methodology context can consume the
predicate without a cross-context application-to-application import
forbidden by D17).

Policy boundary:

- ``create_methodology_template``, ``update_methodology_template``,
  ``retire_methodology_template``: operator-context only. Tenant-
  context callers raise ``AuthorizationError`` and emit
  ``authz_denial`` security events.
- ``get_methodology_template``, ``list_methodology_templates``:
  any authenticated context (operator or tenant). Methodology
  templates are platform-managed and visible across tenants by
  design per the P7 epic note's inverse-of-agent-isolation
  principle.

Hash chain: ``create`` and ``update`` compute the new revision's
hash inside the use case via ``compute_revision_hash``; the
repository persists the precomputed hash without recomputation.
This keeps hash logic in the domain (``contexts/methodology/domain/
hash_chain.py``) and the repository purely persistence-shaped.

Description and name immutability per the structural-honesty
interpretation of D74 at S23: both fields are set at template
creation and not modified by ``update_methodology_template`` (which
only adds revisions). The hash payload pulls the template's name and
description from the parent template at hash-computation time,
keeping the chain integrity check valid for all revisions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID, uuid4

from contexts.methodology.domain.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)
from contexts.methodology.domain.methodology import (
    MethodologyRevision,
    MethodologyTemplate,
)
from contexts.methodology.ports import MethodologyRepositoryPort
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)
from padhanam.security import (
    AuthorizationError,
    Principal,
    is_operator,
)


def _deny(
    *,
    principal: Principal,
    action: str,
    resource_ref: str,
    security_events: SecurityEventLogger,
) -> AuthorizationError:
    security_events.emit(
        SecurityEvent(
            category=SecurityEventCategory.AUTHZ_DENIAL,
            principal_ref=principal.subject,
            tenant_id=str(principal.tenant_id),
            action=action,
            resource_ref=resource_ref,
            outcome="deny",
        )
    )
    return AuthorizationError(
        f"{action} requires operator context; "
        f"principal {principal.subject!r} denied"
    )


def _content_payload(
    *,
    name: str,
    description: str | None,
    system_prompt: str,
    source_ids: tuple[UUID, ...],
    tool_allowlist: tuple[str, ...],
    retrieval_strategy: Mapping[str, Any],
    filter_tree: Mapping[str, Any],
    top_k: int,
    min_score: Decimal,
    model_selection: str,
) -> dict[str, Any]:
    """Construct the canonical hash content payload per D74.

    The description's null is normalised to the empty string so the
    canonical-JSON encoding is identical for ``description=None`` and
    ``description=""`` (both are absence-of-description and should
    not produce hash divergence). All list-shaped fields convert to
    plain Python lists; the hash helper applies the canonical sort
    inside ``compute_revision_hash``.
    """
    return {
        "name": name,
        "description": description or "",
        "system_prompt": system_prompt,
        "source_ids": [str(s) for s in source_ids],
        "tool_allowlist": list(tool_allowlist),
        "retrieval_strategy": dict(retrieval_strategy),
        "filter_tree": dict(filter_tree),
        "top_k": top_k,
        "min_score": min_score,
        "model_selection": model_selection,
    }


async def create_methodology_template(
    *,
    principal: Principal,
    repository: MethodologyRepositoryPort,
    security_events: SecurityEventLogger,
    name: str,
    description: str | None,
    system_prompt: str,
    source_ids: tuple[UUID, ...],
    tool_allowlist: tuple[str, ...],
    retrieval_strategy: Mapping[str, Any],
    filter_tree: Mapping[str, Any],
    top_k: int,
    min_score: Decimal,
    model_selection: str,
    actor_user_id: str,
) -> tuple[MethodologyTemplate, MethodologyRevision]:
    """Create a new methodology template with revision 1 (D74).

    Operator-context only. The template's id and the revision's id
    are generated server-side; both timestamps are set to
    ``datetime.now(timezone.utc)``. Revision 1's
    ``previous_revision_hash`` is the genesis sentinel.
    """
    if not is_operator(principal):
        raise _deny(
            principal=principal,
            action="methodology.create_template",
            resource_ref=f"methodology_template:new[{name}]",
            security_events=security_events,
        )

    now = datetime.now(timezone.utc)
    template_id = uuid4()
    template = MethodologyTemplate(
        id=template_id,
        name=name,
        description=description,
        created_by_user_id=actor_user_id,
        created_at=now,
    )

    payload = _content_payload(
        name=name,
        description=description,
        system_prompt=system_prompt,
        source_ids=source_ids,
        tool_allowlist=tool_allowlist,
        retrieval_strategy=retrieval_strategy,
        filter_tree=filter_tree,
        top_k=top_k,
        min_score=min_score,
        model_selection=model_selection,
    )
    initial_hash = compute_revision_hash(
        content_payload=payload,
        previous_hash=GENESIS_REVISION_HASH,
    )

    revision = MethodologyRevision(
        id=uuid4(),
        methodology_template_id=template_id,
        version=1,
        system_prompt=system_prompt,
        source_ids=source_ids,
        tool_allowlist=tool_allowlist,
        retrieval_strategy=retrieval_strategy,
        filter_tree=filter_tree,
        top_k=top_k,
        min_score=min_score,
        model_selection=model_selection,
        created_by_user_id=actor_user_id,
        created_at=now,
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash=initial_hash,
    )

    await repository.create_template(template, revision)
    return template, revision


async def get_methodology_template(
    *,
    principal: Principal,
    repository: MethodologyRepositoryPort,
    template_id: UUID,
    version: int | None = None,
) -> tuple[MethodologyTemplate, MethodologyRevision]:
    """Retrieve a template plus the named or latest revision (D74).

    Accepts any authenticated context per the platform-managed-
    templates-visible-across-tenants principle. ``LookupError``
    propagates from the repository on unknown id or version.
    """
    return await repository.get_template(template_id, version)


async def list_methodology_templates(
    *,
    principal: Principal,
    repository: MethodologyRepositoryPort,
) -> list[MethodologyTemplate]:
    """List non-archived methodology templates (D74).

    Accepts any authenticated context per the platform-managed-
    templates-visible-across-tenants principle.
    """
    return await repository.list_templates()


async def update_methodology_template(
    *,
    principal: Principal,
    repository: MethodologyRepositoryPort,
    security_events: SecurityEventLogger,
    template_id: UUID,
    system_prompt: str,
    source_ids: tuple[UUID, ...],
    tool_allowlist: tuple[str, ...],
    retrieval_strategy: Mapping[str, Any],
    filter_tree: Mapping[str, Any],
    top_k: int,
    min_score: Decimal,
    model_selection: str,
    actor_user_id: str,
) -> MethodologyRevision:
    """Add a new revision to an existing template (D74).

    Operator-context only. Pulls the template's name and description
    (immutable per the template aggregate) plus the latest revision
    (for the chain pointer) and constructs the next revision with
    incremented version and the chained hash.
    """
    if not is_operator(principal):
        raise _deny(
            principal=principal,
            action="methodology.update_template",
            resource_ref=f"methodology_template:{template_id}",
            security_events=security_events,
        )

    template, latest = await repository.get_template(template_id)

    payload = _content_payload(
        name=template.name,
        description=template.description,
        system_prompt=system_prompt,
        source_ids=source_ids,
        tool_allowlist=tool_allowlist,
        retrieval_strategy=retrieval_strategy,
        filter_tree=filter_tree,
        top_k=top_k,
        min_score=min_score,
        model_selection=model_selection,
    )
    new_hash = compute_revision_hash(
        content_payload=payload,
        previous_hash=latest.this_revision_hash,
    )

    now = datetime.now(timezone.utc)
    revision = MethodologyRevision(
        id=uuid4(),
        methodology_template_id=template_id,
        version=latest.version + 1,
        system_prompt=system_prompt,
        source_ids=source_ids,
        tool_allowlist=tool_allowlist,
        retrieval_strategy=retrieval_strategy,
        filter_tree=filter_tree,
        top_k=top_k,
        min_score=min_score,
        model_selection=model_selection,
        created_by_user_id=actor_user_id,
        created_at=now,
        previous_revision_hash=latest.this_revision_hash,
        this_revision_hash=new_hash,
    )

    return await repository.add_revision(template_id, revision)


async def retire_methodology_template(
    *,
    principal: Principal,
    repository: MethodologyRepositoryPort,
    security_events: SecurityEventLogger,
    template_id: UUID,
) -> MethodologyTemplate:
    """Mark a template as archived (D74).

    Operator-context only. Existing clones unaffected per D68;
    revisions remain queryable via ``get_methodology_template`` for
    audit purposes per D31's append-only-at-version-level
    discipline.
    """
    if not is_operator(principal):
        raise _deny(
            principal=principal,
            action="methodology.retire_template",
            resource_ref=f"methodology_template:{template_id}",
            security_events=security_events,
        )

    return await repository.archive_template(template_id)
