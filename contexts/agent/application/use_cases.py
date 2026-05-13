"""Agent CRUD use cases (D75, D79, D86) plus invoke_agent (D88, S27b).

Eight policy-aware coroutines wrapping ``AgentRepositoryPort`` and the
cross-context lookup ports. Tenant-context-or-operator-context auth at
the use case layer per D75: agents are tenant-user-owned per the P7
epic note's audience definition; tenant users CRUD their own agents
through the tenant-context route. The CLI in operator-context per the
dev-shape pattern at ``apps/cli/_runtime.py`` also CRUDs agents on
behalf of a tenant; this is operator-as-platform-administrator, not
operator-as-tenant-impersonator. Unauthenticated callers (no role at
all) raise ``AuthorizationError``.

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

S27b adds ``invoke_agent`` per D88: the first runtime path for an
agent. Resolves the agent template, re-fetches the role from
``RoleLookup`` (when the agent has role lineage), fetches the
methodology's per-role overrides via ``MethodologyOverridesLookup``
(when methodology lineage is also present), composes the effective
constraint bundle per D87's resolver at ``composition.py``, builds an
``AgentInvocationContext``, and invokes the supplied ``AgentExecutor``.
The agent's own revision content acts as fallback for blank-created
agents (lineage absent); the runtime path's structural shape is
uniform: every invocation produces an effective bundle, even when
lineage is absent.

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
from typing import Any, AsyncIterator, Mapping
from uuid import UUID, uuid4

from contexts.agent.application.composition import (
    compose_effective_constraint_bundle,
)
from contexts.agent.application.ports import (
    AgentRunRecord,
    MethodologyLookup,
    MethodologyOverridesLookup,
    RoleLookup,
    RoleView,
    RunHistoryWriter,
    SourceLookup,
    ToolDefinitionsLookup,
)
from contexts.agent.domain.agent import AgentRevision, AgentTemplate
from contexts.agent.domain.events import (
    AgentEvent,
    InvariantBlocked,
    InvocationCompleted,
    InvocationFailed,
    InvocationStarted,
    IterationCompleted,
    IterationStarted,
)
from contexts.agent.ports import (
    AgentExecutor,
    AgentInvocationContext,
    AgentRepositoryPort,
)
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
from shared_kernel import TenantContext, ToolAllowlistEntry


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
    tool_allowlist: tuple[ToolAllowlistEntry, ...],
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
        "tool_allowlist": [
            {"tool_id": str(e.tool_id), "revision_id": str(e.revision_id)}
            for e in sorted(tool_allowlist)
        ],
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
    tool_allowlist: tuple[ToolAllowlistEntry, ...],
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
    tool_allowlist: tuple[ToolAllowlistEntry, ...],
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


def _revision_as_role_view(
    revision: AgentRevision,
    *,
    role_id: UUID | None,
    role_version: int | None,
    description: str | None,
) -> RoleView:
    """Build a RoleView from an agent revision's own content (D88).

    Used by ``invoke_agent`` for blank-created agents (no role lineage)
    where the agent's revision content is the source of truth for the
    constraint bundle. The composition resolver consumes this view the
    same way it consumes a RoleLookup-returned view; effectively the
    agent's revision is its own role.

    role_id and role_version are passed through unchanged so the
    AgentInvocationContext can carry sentinel zeros for blank-created
    agents — the executor's audit payload records what the lineage
    says, not synthesised values.
    """
    return RoleView(
        role_id=role_id or UUID(int=0),
        role_version=role_version or 0,
        description=description,
        system_prompt=revision.system_prompt,
        tool_allowlist=revision.tool_allowlist,
        retrieval_strategy=revision.retrieval_strategy,
        filter_tree=revision.filter_tree,
        top_k=revision.top_k,
        min_score=revision.min_score,
        model_selection=revision.model_selection,
    )


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


async def invoke_agent(
    *,
    principal: Principal,
    repository: AgentRepositoryPort,
    role_lookup: RoleLookup,
    methodology_overrides_lookup: MethodologyOverridesLookup,
    tool_definitions_lookup: ToolDefinitionsLookup,
    executor: AgentExecutor,
    writer: RunHistoryWriter,
    security_events: SecurityEventLogger,
    tenant_context: TenantContext,
    agent_template_id: UUID,
    user_input: str,
) -> AsyncIterator[AgentEvent]:
    """Run a single agent invocation end-to-end (D88, D90, D95; S27b → S29b → S31).

    S29b (D90): the use case is an async generator yielding ``AgentEvent``
    values from the executor's stream. The use case resolves lineage,
    composes the effective constraint bundle per D87, builds the
    invocation context, and streams events through. Audit emission per
    D26 happens inside the executor (the executor has the data — input
    hash, response content, cost, termination — at the right moments;
    moving audit to the use case would require threading that data
    back through the event stream, which is awkward). The two audit
    rows land at invocation start (before InvocationStarted yields) and
    at the terminal event (before the terminal AgentEvent yields).
    The terminal event carries both hashes so callers (and the
    collect_to_result helper) can deep-link into the audit chain.

    S31 (D95): the use case accumulates run-record-shaped state from
    the event stream and calls ``writer.record_run`` AFTER yielding
    the terminal event per D95's write-timing commitment (shape B).
    The runs row is the rendering projection over the canonical audit
    chain. Mapping per terminal event class per D95's audit-chain
    partial-state shape:

    - ``InvocationCompleted``: termination_reason from event enum
      value; both audit hashes from event.audit_chain_hashes;
      output_content from event.final_result; total_cost_usd from
      event.total_cost_usd.
    - ``InvariantBlocked``: termination_reason='invariant_blocked';
      both audit hashes from event.audit_chain_hashes; output_content
      empty; total_cost_usd from accumulated IterationCompleted.cost_usd.
    - ``InvocationFailed`` with 0-hash ``partial_audit_chain_state``
      (pre-start-audit failure): skip the writer call entirely. No
      runs row exists because no audit evidence exists; consistent
      with the projection-over-recorded-activity framing.
    - ``InvocationFailed`` with 1-hash ``partial_audit_chain_state``
      (post-start-audit failure, the loop-body-exception and
      end-audit-emission-failure sites in agent_loop_executor.py):
      termination_reason='failed'; audit_start_hash from
      partial[0]; audit_end_hash=None (signalling chain-incomplete);
      output_content empty.
    - ``InvocationFailed`` with 2-hash ``partial_audit_chain_state``
      (forward-affordance, currently not fired by the executor):
      termination_reason='failed'; both audit hashes from partial;
      output_content empty.

    Three lineage paths land here as parallel flows:

    - Both pairs NULL (blank-created agent): the agent's own revision
      content acts as the role view; no methodology overrides apply;
      the composition resolver returns the role view unchanged.
    - Only role pair populated (role-cloned): re-fetch the role's
      current content via ``RoleLookup``; no methodology overrides;
      composition returns the role view unchanged.
    - Both pairs populated (methodology-cloned): re-fetch the role via
      ``RoleLookup``; fetch the methodology revision's per-role
      overrides for this role via ``MethodologyOverridesLookup``;
      compose per D87.

    Auth posture matches the other agent CRUD use cases per D75:
    tenant-context-or-operator-context. The auth check fires on the
    first ``__anext__()`` call on the returned async generator (Python
    async-generator-function semantics); unauthenticated callers see
    the AuthorizationError on first iteration, not on call.

    Per D90's tool_classifications field on AgentInvocationContext,
    the use case populates an empty mapping at Phase 1. Surfacing
    classification through the consumer ports happens when a real
    consumer evidence emerges (Phase 2 when non-retrieval tools ship);
    the executor falls back to ``"unknown"`` for any tool not in the
    map. The integration test against the McKinsey ProblemFramer at
    commit 9 exercises a content-only invocation where the empty map
    is unobserved.
    """
    if not _is_authenticated(principal):
        raise _deny(
            principal=principal,
            action="agent.invoke_agent",
            resource_ref=f"agent_template:{agent_template_id}",
            security_events=security_events,
        )

    template, revision = await repository.get_template(
        agent_template_id, tenant_context
    )

    role_view = await _resolve_role_view(
        template=template,
        revision=revision,
        role_lookup=role_lookup,
        principal=principal,
    )

    methodology_overrides: dict[str, dict[str, Any]] = {}
    if (
        template.source_methodology_template_id is not None
        and template.source_role_id is not None
    ):
        methodology_overrides = await methodology_overrides_lookup(
            methodology_template_id=template.source_methodology_template_id,
            methodology_version=template.source_methodology_template_version,
            role_id=template.source_role_id,
            principal=principal,
        )

    bundle = compose_effective_constraint_bundle(
        role=role_view,
        methodology_overrides=methodology_overrides,
    )
    tool_definitions = await tool_definitions_lookup(
        allowlist=bundle.tool_allowlist,
    )

    context = AgentInvocationContext(
        tenant_context=tenant_context,
        agent_template_id=template.id,
        agent_revision_version=revision.version,
        role_template_id=role_view.role_id,
        role_revision_version=role_view.role_version,
        methodology_template_id=template.source_methodology_template_id,
        methodology_version=template.source_methodology_template_version,
        effective_bundle=bundle,
        user_input=user_input,
        tool_definitions=tool_definitions,
        # tool_classifications stays empty at Phase 1 per D90; the
        # executor falls back to "unknown" for any tool not in the
        # map. See use-case docstring above for the deferral rationale.
        tool_classifications={},
    )

    # Accumulators for the run record (D95 shape-B write-timing).
    invocation_id: UUID | None = None
    started_at: datetime | None = None
    iteration_count: int = 0
    cost_accumulator: Decimal = Decimal("0")

    async for event in executor.execute(context):
        # Update accumulators per event type before yielding.
        if isinstance(event, InvocationStarted):
            invocation_id = event.invocation_id
            started_at = event.started_at
        elif isinstance(event, IterationStarted):
            # iteration_index is 1-based per D90; iteration_count
            # tracks the highest started iteration so partial-state
            # failures still record the count attempted.
            iteration_count = max(iteration_count, event.iteration_index)
        elif isinstance(event, IterationCompleted):
            cost_accumulator += event.cost_usd

        yield event

        # After yielding the terminal event, assemble the run record
        # and write per D95 shape B (terminal yield first, then write,
        # then generator returns).
        if isinstance(event, (InvocationCompleted, InvocationFailed, InvariantBlocked)):
            run_record = _assemble_agent_run_record(
                terminal_event=event,
                invocation_id=invocation_id,
                started_at=started_at,
                iteration_count=iteration_count,
                cost_accumulator=cost_accumulator,
                template=template,
                revision=revision,
                tenant_context=tenant_context,
                user_input=user_input,
            )
            if run_record is not None:
                await writer.record_run(run_record, principal=principal)
            return


def _assemble_agent_run_record(
    *,
    terminal_event: InvocationCompleted | InvocationFailed | InvariantBlocked,
    invocation_id: UUID | None,
    started_at: datetime | None,
    iteration_count: int,
    cost_accumulator: Decimal,
    template: AgentTemplate,
    revision: AgentRevision,
    tenant_context: TenantContext,
    user_input: str,
) -> AgentRunRecord | None:
    """Assemble the run record from accumulator state + terminal event (D95).

    Returns ``None`` when the terminal event is ``InvocationFailed``
    with empty ``partial_audit_chain_state`` (pre-start-audit
    failure); the caller skips the writer call. Returns an
    ``AgentRunRecord`` otherwise.

    Mapping per terminal event class follows D95's audit-chain
    partial-state shape. See ``invoke_agent`` docstring for details.
    """
    # InvocationFailed with 0-hash partial state: no projection target.
    if isinstance(terminal_event, InvocationFailed):
        if len(terminal_event.partial_audit_chain_state) == 0:
            return None

    # InvocationStarted should have set these; assert defensively.
    if invocation_id is None or started_at is None:
        return None

    if isinstance(terminal_event, InvocationCompleted):
        audit_start_hash = terminal_event.audit_chain_hashes[0]
        audit_end_hash: str | None = terminal_event.audit_chain_hashes[1]
        termination_reason = terminal_event.termination_reason.value
        output_content = terminal_event.final_result
        total_cost_usd = terminal_event.total_cost_usd
    elif isinstance(terminal_event, InvariantBlocked):
        audit_start_hash = terminal_event.audit_chain_hashes[0]
        audit_end_hash = terminal_event.audit_chain_hashes[1]
        termination_reason = "invariant_blocked"
        output_content = ""
        total_cost_usd = cost_accumulator
    else:
        # InvocationFailed with 1-hash (currently fired) or 2-hash
        # (forward-affordance) partial_audit_chain_state.
        partial = terminal_event.partial_audit_chain_state
        audit_start_hash = partial[0]
        audit_end_hash = partial[1] if len(partial) >= 2 else None
        termination_reason = "failed"
        output_content = ""
        total_cost_usd = cost_accumulator

    now = datetime.now(timezone.utc)
    return AgentRunRecord(
        id=invocation_id,
        tenant_id=str(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        agent_template_id=template.id,
        agent_template_version=revision.version,
        input_message=user_input,
        output_content=output_content,
        started_at=started_at,
        completed_at=now,
        termination_reason=termination_reason,
        iteration_count=iteration_count,
        total_cost_usd=total_cost_usd,
        trace_id=None,
        audit_start_hash=audit_start_hash,
        audit_end_hash=audit_end_hash,
        created_at=now,
    )


async def _resolve_role_view(
    *,
    template: AgentTemplate,
    revision: AgentRevision,
    role_lookup: RoleLookup,
    principal: Principal,
) -> RoleView:
    """Re-fetch the role's current content when lineage is set, else
    project the agent's own revision content as a RoleView (D88)."""
    if template.source_role_id is not None:
        return await role_lookup(
            role_id=template.source_role_id,
            version=template.source_role_version,
            principal=principal,
        )
    return _revision_as_role_view(
        revision,
        role_id=None,
        role_version=None,
        description=template.description,
    )
