"""Tool CRUD use cases (D89).

Mirror the methodology / role use case pattern from S23 / S26a-1:
operator-context auth at writes per D34, content-payload helper for
hash chaining via ``padhanam.security.hash_chain`` per D75's
promotion, security events on authz denials and privileged actions.

Phase 1 authoring prohibition per D89: ``create_tool`` rejects
classifications ``financial``, ``communication``, ``legal`` with
``ClassificationProhibitedError``. The error message names the
per-invocation confirmation pathway deferred-decisions entry so the
operator sees the forward trajectory.

The BC stub computation at ``create_tool_revision`` is wired here as
a no-op default (``bc_result = {}``); commit 6 lands the schema-diff
stub at ``backward_compatibility.py`` and threads it through this
use case so each new revision records its BC result against the
prior revision before persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID, uuid4

from contexts.tools.domain.exceptions import (
    ClassificationProhibitedError,
    RevisionNotFoundError,
    ToolNotFoundError,
)
from contexts.tools.domain.tool import (
    Classification,
    PHASE_1_PROHIBITED_CLASSIFICATIONS,
    Tool,
    ToolRevision,
)
from contexts.tools.ports import ToolRepositoryPort
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


# Reference name for the deferred-decisions entry that, when its
# corresponding D-entry lands, will lift the Phase 1 authoring
# prohibition. Surfaced verbatim in the error message so operators
# discover the forward trajectory by reading the failure.
_CONFIRMATION_PATHWAY_REFERENCE = (
    "Per-invocation human-in-the-loop confirmation pathway for "
    "high-classification tools (see charter/deferred-decisions.md)"
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


def _tool_content_payload(
    *,
    name: str,
    description: str | None,
    classification: Classification,
    parameters_schema: Mapping[str, Any],
    returns_schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Canonical hash content payload for a tool revision (D89, D74).

    The payload spans the parent template's name, description, and
    classification (denormalised at hash-compute time per D74's
    chain-self-containment pattern) plus the revision's parameters
    and returns schemas. ``bc_result`` and chain metadata
    (template_id, version, timestamps) are excluded so the hash
    surface stays content-only.

    The Postgres adapter's ``verify_chain_integrity`` reconstructs
    this payload byte-equivalent when verifying chain integrity;
    keep this helper and that verification logic in sync.
    """
    return {
        "name": name,
        "description": description,
        "classification": classification.value,
        "parameters_schema": dict(parameters_schema),
        "returns_schema": dict(returns_schema),
    }


async def create_tool(
    *,
    principal: Principal,
    repository: ToolRepositoryPort,
    security_events: SecurityEventLogger,
    name: str,
    description: str | None,
    classification: Classification,
    parameters_schema: Mapping[str, Any],
    returns_schema: Mapping[str, Any],
    actor_user_id: str,
) -> tuple[Tool, ToolRevision]:
    """Create a new tool template with revision 1 (D89).

    Rejects classifications ``financial``, ``communication``, ``legal``
    with ``ClassificationProhibitedError`` per D89's Phase 1
    authoring prohibition. The error message names the per-invocation
    confirmation pathway deferred-decisions entry so the operator
    discovers the forward trajectory.
    """
    if not is_operator(principal):
        raise _deny(
            principal=principal,
            action="tool.create",
            resource_ref=f"tool:new[{name}]",
            security_events=security_events,
        )

    if classification in PHASE_1_PROHIBITED_CLASSIFICATIONS:
        raise ClassificationProhibitedError(
            f"Phase 1 prohibits authoring tools with classification "
            f"{classification.value!r}. The prohibition lifts when "
            f"the confirmation pathway lands. {_CONFIRMATION_PATHWAY_REFERENCE}."
        )

    now = datetime.now(timezone.utc)
    template_id = uuid4()
    template = Tool(
        id=template_id,
        name=name,
        description=description,
        classification=classification,
        created_by_user_id=actor_user_id,
        created_at=now,
    )

    payload = _tool_content_payload(
        name=name,
        description=description,
        classification=classification,
        parameters_schema=parameters_schema,
        returns_schema=returns_schema,
    )
    this_hash = compute_revision_hash(
        content_payload=payload,
        previous_hash=GENESIS_REVISION_HASH,
    )

    revision = ToolRevision(
        id=uuid4(),
        tool_id=template_id,
        version=1,
        parameters_schema=parameters_schema,
        returns_schema=returns_schema,
        bc_result={},
        created_by_user_id=actor_user_id,
        created_at=now,
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash=this_hash,
    )

    await repository.create_template(template, revision)
    return template, revision


async def get_tool(
    *,
    principal: Principal,
    repository: ToolRepositoryPort,
    template_id: UUID,
    version: int | None = None,
) -> tuple[Tool, ToolRevision]:
    """Retrieve a tool plus the named or latest revision (D89)."""
    return await repository.get_template(template_id, version)


async def list_tools(
    *,
    principal: Principal,
    repository: ToolRepositoryPort,
) -> list[Tool]:
    """List non-archived tool templates (D89)."""
    return await repository.list_templates()


async def create_tool_revision(
    *,
    principal: Principal,
    repository: ToolRepositoryPort,
    security_events: SecurityEventLogger,
    template_id: UUID,
    parameters_schema: Mapping[str, Any],
    returns_schema: Mapping[str, Any],
    actor_user_id: str,
) -> ToolRevision:
    """Append a new revision to an existing tool (D89).

    Reads the latest revision (to chain from), composes the new
    revision's content payload, computes the hash, and persists. The
    BC stub computation lands at commit 6 and stores its result on
    ``ToolRevision.bc_result``; until then, ``bc_result`` is an
    empty dict.

    The tool's classification cannot change across revisions per D89
    alternative (g) — the parent template owns classification. This
    use case reads classification from the template and includes it
    in the new revision's hash payload accordingly.
    """
    if not is_operator(principal):
        raise _deny(
            principal=principal,
            action="tool.add_revision",
            resource_ref=f"tool:{template_id}",
            security_events=security_events,
        )

    template, latest_revision = await repository.get_template(template_id)
    next_version = latest_revision.version + 1

    payload = _tool_content_payload(
        name=template.name,
        description=template.description,
        classification=template.classification,
        parameters_schema=parameters_schema,
        returns_schema=returns_schema,
    )
    this_hash = compute_revision_hash(
        content_payload=payload,
        previous_hash=latest_revision.this_revision_hash,
    )

    now = datetime.now(timezone.utc)
    revision = ToolRevision(
        id=uuid4(),
        tool_id=template_id,
        version=next_version,
        parameters_schema=parameters_schema,
        returns_schema=returns_schema,
        bc_result={},
        created_by_user_id=actor_user_id,
        created_at=now,
        previous_revision_hash=latest_revision.this_revision_hash,
        this_revision_hash=this_hash,
    )

    await repository.add_revision(template_id, revision)
    return revision


async def archive_tool(
    *,
    principal: Principal,
    repository: ToolRepositoryPort,
    security_events: SecurityEventLogger,
    template_id: UUID,
) -> Tool:
    """Archive a tool template (D89, D31).

    Marks the parent template's ``archived_at``; revisions are
    unaffected so existing role-references survive archival
    (mirrors the methodology / role pattern).
    """
    if not is_operator(principal):
        raise _deny(
            principal=principal,
            action="tool.archive",
            resource_ref=f"tool:{template_id}",
            security_events=security_events,
        )
    return await repository.archive_template(template_id)


__all__ = [
    "_tool_content_payload",
    "archive_tool",
    "create_tool",
    "create_tool_revision",
    "get_tool",
    "list_tools",
]
