"""Agent CRUD use cases (D75, D79, D86).

Seven policy-aware coroutines wrapping ``AgentRepositoryPort``.
Tenant-context-or-operator-context auth at the use case layer per
D75: agents are tenant-user-owned per the P7 epic note's audience
definition; tenant users CRUD their own agents through the tenant-
context route. The CLI in operator-context per the dev-shape
pattern at ``apps/cli/_runtime.py`` also CRUDs agents on behalf of a
tenant; this is operator-as-platform-administrator, not operator-
as-tenant-impersonator. Unauthenticated callers (no role at all)
raise ``AuthorizationError``.

Two cross-context create paths per D79 (S25) and D86 (S26a-2):
``create_agent_from_methodology`` clones a methodology playbook into
an agent (resolving methodology + first role_ref through the
MethodologyLookup port); ``create_agent_from_role`` clones a role
directly into an agent without a methodology playbook above it
(through the RoleLookup port). Both paths share the SourceLookup
port for source-existence validation. The agent context's
application layer takes zero imports from contexts.methodology or
contexts.ingestion; the apps/cli wiring layer translates each
producer context's application-layer use cases into the consumer-
shaped Protocol calls.

Hash chain: ``create_blank_agent``, ``update_agent``,
``create_agent_from_methodology``, and ``create_agent_from_role``
all compute the new revision's hash inside the use case via
``compute_revision_hash`` imported from
``padhanam.security.hash_chain`` (promoted from the methodology
context at S24 commit 8 per D75); the repository persists the
precomputed hash without recomputation. List-sort responsibility
lives in ``_content_payload`` here, not in the helper, per D75's
field-set-agnostic API.

Per D75, ``name`` and ``description`` are read from the parent
template at hash-compute time and included in the canonical-JSON
payload as the ``name`` and ``description`` keys. Both are
template-level and immutable post-creation, so their inclusion is
deterministic across the chain. The clone-from-methodology and
clone-from-role flows preserve byte-equivalence with blank-create:
a cloned revision 1 with the same content fields produces an
identical hash, because all three paths invoke the same
``_content_payload`` helper followed by the same
``compute_revision_hash`` call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID, uuid4

from contexts.agent.application.ports import (
    MethodologyLookup,
    RoleLookup,
    SourceLookup,
)
from contexts.agent.domain.agent import AgentRevision, AgentTemplate
from contexts.agent.ports import AgentRepositoryPort
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
from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)
from shared_kernel import TenantContext


def _is_authenticated(principal: Principal) -> bool:
    """Tenant-context-or-operator-context auth posture (D75).

    Authentication is satisfied by any role on the principal:
    operator-context (carries OPERATOR_ROLE) or tenant-context
    (carries tenant-scoped roles). Unauthenticated callers (empty
    role set) are denied at the use case boundary.
    """
    return is_operator(principal) or len(principal.roles) > 0


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
        f"{action} requires an authenticated principal "
        f"(tenant-context or operator-context); "
        f"principal {principal.subject!r} has no roles"
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
    """Construct the canonical hash content payload per D75.

    Description's null is normalised to the empty string so the
    canonical-JSON encoding is identical for ``description=None`` and
    ``description=""`` (both are absence-of-description and should
    not produce hash divergence).

    Per D75's field-set-agnostic helper API, list-shaped field
    sorting is the use case's responsibility. ``source_ids`` and
    ``tool_allowlist`` are sorted lexically here so callers cannot
    accidentally produce hash drift through list-order variation.
    Symmetric to the methodology context's _content_payload at
    ``contexts/methodology/application/use_cases.py``.
    """
    return {
        "name": name,
        "description": description or "",
        "system_prompt": system_prompt,
        "source_ids": sorted(str(s) for s in source_ids),
        "tool_allowlist": sorted(str(t) for t in tool_allowlist),
        "retrieval_strategy": dict(retrieval_strategy),
        "filter_tree": dict(filter_tree),
        "top_k": top_k,
        "min_score": min_score,
        "model_selection": model_selection,
    }


async def create_blank_agent(
    *,
    principal: Principal,
    repository: AgentRepositoryPort,
    security_events: SecurityEventLogger,
    tenant_context: TenantContext,
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
) -> tuple[AgentTemplate, AgentRevision]:
    """Create a new blank agent template with revision 1 (D75).

    Both ``source_methodology_template_id`` and
    ``source_methodology_template_version`` are NULL because this is
    blank-created. The cross-context flow at S25 surfaces a separate
    use case (``create_agent_from_methodology``) for clone-created
    agents. The template's id and the revision's id are generated
    server-side; both timestamps are set to
    ``datetime.now(timezone.utc)``. Revision 1's
    ``previous_revision_hash`` is the genesis sentinel.
    """
    if not _is_authenticated(principal):
        raise _deny(
            principal=principal,
            action="agent.create_blank_agent",
            resource_ref=f"agent_template:new[{name}]",
            security_events=security_events,
        )

    now = datetime.now(timezone.utc)
    template_id = uuid4()
    template = AgentTemplate(
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

    revision = AgentRevision(
        id=uuid4(),
        agent_template_id=template_id,
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

    await repository.create_template(template, revision, tenant_context)
    return template, revision


async def get_agent(
    *,
    principal: Principal,
    repository: AgentRepositoryPort,
    security_events: SecurityEventLogger,
    tenant_context: TenantContext,
    template_id: UUID,
    version: int | None = None,
) -> tuple[AgentTemplate, AgentRevision]:
    """Retrieve an agent template plus the named or latest revision (D75).

    Tenant-context-or-operator-context auth. ``LookupError``
    propagates from the repository on unknown id or version.
    """
    if not _is_authenticated(principal):
        raise _deny(
            principal=principal,
            action="agent.get_agent",
            resource_ref=f"agent_template:{template_id}",
            security_events=security_events,
        )
    return await repository.get_template(
        template_id, tenant_context, version
    )


async def list_agents(
    *,
    principal: Principal,
    repository: AgentRepositoryPort,
    security_events: SecurityEventLogger,
    tenant_context: TenantContext,
    include_archived: bool = False,
) -> list[AgentTemplate]:
    """List agent templates within the tenant (D75).

    Tenant-context-or-operator-context auth. Defaults to active
    templates only; pass ``include_archived=True`` for audit views.
    """
    if not _is_authenticated(principal):
        raise _deny(
            principal=principal,
            action="agent.list_agents",
            resource_ref="agent_template:*",
            security_events=security_events,
        )
    return await repository.list_templates(
        tenant_context, include_archived=include_archived
    )


async def update_agent(
    *,
    principal: Principal,
    repository: AgentRepositoryPort,
    security_events: SecurityEventLogger,
    tenant_context: TenantContext,
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
) -> AgentRevision:
    """Add a new revision to an existing agent template (D75).

    Tenant-context-or-operator-context auth. Pulls the template's
    name and description (immutable per the template aggregate) plus
    the latest revision (for the chain pointer) and constructs the
    next revision with incremented version and the chained hash.
    """
    if not _is_authenticated(principal):
        raise _deny(
            principal=principal,
            action="agent.update_agent",
            resource_ref=f"agent_template:{template_id}",
            security_events=security_events,
        )

    template, latest = await repository.get_template(
        template_id, tenant_context
    )

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
    revision = AgentRevision(
        id=uuid4(),
        agent_template_id=template_id,
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

    return await repository.add_revision(template_id, revision, tenant_context)


async def archive_agent(
    *,
    principal: Principal,
    repository: AgentRepositoryPort,
    security_events: SecurityEventLogger,
    tenant_context: TenantContext,
    template_id: UUID,
) -> AgentTemplate:
    """Mark an agent template as archived (D75).

    Tenant-context-or-operator-context auth. Revisions remain
    queryable through ``get_agent`` for audit purposes per D31's
    append-only-at-version-level discipline.
    """
    if not _is_authenticated(principal):
        raise _deny(
            principal=principal,
            action="agent.archive_agent",
            resource_ref=f"agent_template:{template_id}",
            security_events=security_events,
        )

    return await repository.archive_template(template_id, tenant_context)


async def create_agent_from_methodology(
    *,
    principal: Principal,
    repository: AgentRepositoryPort,
    methodology_lookup: MethodologyLookup,
    source_lookup: SourceLookup,
    security_events: SecurityEventLogger,
    tenant_context: TenantContext,
    methodology_template_id: UUID,
    methodology_version: int | None,
    name: str,
    source_ids: tuple[UUID, ...],
    actor_user_id: str,
) -> tuple[AgentTemplate, AgentRevision]:
    """Clone a methodology template into a new agent (D79, D86).

    The cross-context flow: read the methodology template through the
    consumer-side MethodologyLookup port (apps/cli adapter wraps
    contexts.methodology.application.get_methodology_template and
    get_role_template, joining methodology to its first role_ref per
    S26a-1 / D86), validate every requested source id exists for the
    tenant through the SourceLookup port (apps/cli adapter wraps the
    ingestion get_source use case), construct an AgentTemplate with
    both lineage pairs populated (methodology + role per D75 / D86),
    and construct AgentRevision version 1 with content cloned verbatim
    from the methodology view except for source_ids (which come from
    the request, not from the methodology) and name (which comes from
    the request).

    The resolved methodology_version and role_version returned by the
    lookup are what persists in the lineage; the use case never
    records None even when the caller requests version=None.
    version=None resolution happens at the adapter, not here.

    Source existence validation runs before AgentTemplate
    construction so a missing-source error doesn't leave the use
    case with a half-built aggregate to roll back. SourceNotFoundError
    propagates from the adapter; the use case lets it surface to the
    caller for precise operator-facing error rendering.

    Hash chain: revision 1's previous_revision_hash is the genesis
    sentinel; the payload's hash inputs are byte-equivalent to a
    create_blank_agent call with the same content fields. This
    invariant is exercised by a dedicated unit test below; preserving
    it lets the chain integrity check at audit time treat clone-
    created and blank-created agents uniformly.
    """
    if not _is_authenticated(principal):
        raise _deny(
            principal=principal,
            action="agent.create_agent_from_methodology",
            resource_ref=(
                f"agent_template:new[from_methodology={methodology_template_id}]"
            ),
            security_events=security_events,
        )

    view = await methodology_lookup(
        template_id=methodology_template_id,
        version=methodology_version,
        principal=principal,
    )

    await source_lookup.assert_sources_exist(
        source_ids=source_ids,
        tenant_context=tenant_context,
        principal=principal,
    )

    now = datetime.now(timezone.utc)
    template_id = uuid4()
    template = AgentTemplate(
        id=template_id,
        name=name,
        description=view.description,
        created_by_user_id=actor_user_id,
        created_at=now,
        source_methodology_template_id=view.methodology_template_id,
        source_methodology_template_version=view.methodology_version,
        source_role_id=view.role_id,
        source_role_version=view.role_version,
    )

    payload = _content_payload(
        name=name,
        description=view.description,
        system_prompt=view.system_prompt,
        source_ids=source_ids,
        tool_allowlist=view.tool_allowlist,
        retrieval_strategy=view.retrieval_strategy,
        filter_tree=view.filter_tree,
        top_k=view.top_k,
        min_score=view.min_score,
        model_selection=view.model_selection,
    )
    initial_hash = compute_revision_hash(
        content_payload=payload,
        previous_hash=GENESIS_REVISION_HASH,
    )

    revision = AgentRevision(
        id=uuid4(),
        agent_template_id=template_id,
        version=1,
        system_prompt=view.system_prompt,
        source_ids=source_ids,
        tool_allowlist=view.tool_allowlist,
        retrieval_strategy=view.retrieval_strategy,
        filter_tree=view.filter_tree,
        top_k=view.top_k,
        min_score=view.min_score,
        model_selection=view.model_selection,
        created_by_user_id=actor_user_id,
        created_at=now,
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash=initial_hash,
    )

    await repository.create_template(template, revision, tenant_context)
    return template, revision


async def create_agent_from_role(
    *,
    principal: Principal,
    repository: AgentRepositoryPort,
    role_lookup: RoleLookup,
    source_lookup: SourceLookup,
    security_events: SecurityEventLogger,
    tenant_context: TenantContext,
    role_id: UUID,
    role_version: int | None,
    name: str,
    source_ids: tuple[UUID, ...],
    actor_user_id: str,
) -> tuple[AgentTemplate, AgentRevision]:
    """Clone a role template into a new agent (S26a-2 / D86).

    The role-first cousin of create_agent_from_methodology per D86's
    first-class-role posture: agents can occupy a role directly
    without a methodology playbook above them. The cloned agent's
    methodology lineage stays NULL (the third valid lineage state
    from charter/schema.md); role lineage records the resolved
    (role_id, role_version) pair.

    The cross-context flow: read the role template through the
    consumer-side RoleLookup port (apps/cli adapter wraps
    contexts.methodology.application.get_role_template), validate
    every requested source id exists for the tenant through the
    SourceLookup port, construct an AgentTemplate with the role
    lineage pair populated (D86 paired-NULL invariant) and the
    methodology lineage pair NULL, and construct AgentRevision
    version 1 with content cloned verbatim from the role view except
    for source_ids (from the request) and name (from the request).

    The resolved role_version returned by the lookup is what persists
    in the lineage; the use case never records None even when the
    caller requests version=None. version=None resolution happens at
    the adapter, not here.

    Source existence validation runs before AgentTemplate
    construction so a missing-source error doesn't leave the use
    case with a half-built aggregate to roll back. SourceNotFoundError
    propagates from the adapter.

    Hash chain: revision 1's previous_revision_hash is the genesis
    sentinel; the payload's hash inputs are byte-equivalent to a
    create_blank_agent or create_agent_from_methodology call with the
    same content fields. All three create paths share the same
    _content_payload helper so chain integrity verification treats
    blank-created, methodology-cloned, and role-cloned agents
    uniformly per D75's chain-self-containment.
    """
    if not _is_authenticated(principal):
        raise _deny(
            principal=principal,
            action="agent.create_agent_from_role",
            resource_ref=(
                f"agent_template:new[from_role={role_id}]"
            ),
            security_events=security_events,
        )

    view = await role_lookup(
        role_id=role_id,
        version=role_version,
        principal=principal,
    )

    await source_lookup.assert_sources_exist(
        source_ids=source_ids,
        tenant_context=tenant_context,
        principal=principal,
    )

    now = datetime.now(timezone.utc)
    template_id = uuid4()
    template = AgentTemplate(
        id=template_id,
        name=name,
        description=view.description,
        created_by_user_id=actor_user_id,
        created_at=now,
        source_role_id=view.role_id,
        source_role_version=view.role_version,
    )

    payload = _content_payload(
        name=name,
        description=view.description,
        system_prompt=view.system_prompt,
        source_ids=source_ids,
        tool_allowlist=view.tool_allowlist,
        retrieval_strategy=view.retrieval_strategy,
        filter_tree=view.filter_tree,
        top_k=view.top_k,
        min_score=view.min_score,
        model_selection=view.model_selection,
    )
    initial_hash = compute_revision_hash(
        content_payload=payload,
        previous_hash=GENESIS_REVISION_HASH,
    )

    revision = AgentRevision(
        id=uuid4(),
        agent_template_id=template_id,
        version=1,
        system_prompt=view.system_prompt,
        source_ids=source_ids,
        tool_allowlist=view.tool_allowlist,
        retrieval_strategy=view.retrieval_strategy,
        filter_tree=view.filter_tree,
        top_k=view.top_k,
        min_score=view.min_score,
        model_selection=view.model_selection,
        created_by_user_id=actor_user_id,
        created_at=now,
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash=initial_hash,
    )

    await repository.create_template(template, revision, tenant_context)
    return template, revision
