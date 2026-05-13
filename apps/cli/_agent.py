"""Agent CLI orchestration (S24 / D75, S25 / D79, S26a-2 / D86, S30b / D90).

Eight subcommands at the ``padhanam agent`` namespace: ``create``,
``create-from-methodology``, ``create-from-role``, ``get``,
``list``, ``update``, ``archive``, ``run``. Operator-context resolution at
the command boundary mirrors the S23 methodology CLI pattern;
production CLI auth lands at Phase 2.

S30b adds ``run`` as the first product-form transport consumer of the
SSE endpoint at ``POST /agents/{agent_id}/invoke`` per D90. The
consumer posts to the endpoint, parses the SSE event stream from
``apps/api/adapters/sse_event_translator.py``, and renders each of the
eleven D90 event types to terminal. Exit-code mapping per the three
terminal events: ``InvocationCompleted`` → 0, ``InvariantBlocked`` → 2,
``InvocationFailed`` (or protocol failure) → 1. Wire-side work lives
at ``apps/cli/_agent_run.py``.

S25 adds ``create-from-methodology``, the cross-context clone flow
per D79. The command resolves three engines — control-plane
Postgres (methodology + role repositories), per-tenant Postgres
(source repository), per-tenant Postgres (agent repository) — and
constructs the cross-context adapters from
``apps/cli/_cross_context.py`` to satisfy the agent use case's
MethodologyLookup and SourceLookup ports. All engines dispose in
``finally`` per the established resource-management pattern.

S26a-2 adds ``create-from-role`` per D86's first-class-role posture.
The command wires the role repository (control plane) plus source
repository (per-tenant) plus agent repository (per-tenant) and
constructs the RoleLookupAdapter alongside SourceLookupAdapter to
satisfy the agent use case's RoleLookup and SourceLookup ports.

Per D75, agent data is per-tenant-scoped. The CLI takes a
``--tenant <label>`` argument resolved through the existing dev-
shape mapping at ``apps/cli/_runtime.py`` to a TenantContext. The
AgentPostgresRepository's per-tenant resolver is provided by the
CLI here: it converts the resolved tenant label into a bound
``async_sessionmaker`` against the tenant's data plane via
``session_factory_for_tenant``.

Config file shape (YAML or JSON, auto-detected by extension):

  create — full template + revision-1 payload:
    name: str
    description: str | null
    system_prompt: str
    source_ids: list[uuid-string]
    tool_allowlist: list[str]
    retrieval_strategy: dict (D66 strategy-name-plus-params shape)
    filter_tree: dict (D67 typed Boolean tree)
    top_k: int
    min_score: number (parsed as Decimal at the use case boundary)
    model_selection: str

  update — revision content only (name and description immutable
  per D75 — pulled from parent template at hash-compute time):
    system_prompt, source_ids, tool_allowlist, retrieval_strategy,
    filter_tree, top_k, min_score, model_selection.

The CLI parses the config, validates required fields, converts list
shapes to tuples (frozen-dataclass-friendly) and ``min_score`` to
``Decimal`` (via ``str(value)`` to avoid float→Decimal precision
loss), then invokes the use case. Output is human-readable by
default; ``--json`` produces machine-readable shapes.

Async lifecycle: each command builds a fresh repository (per-tenant
sessionmaker resolver + security event logger), runs the use case
via ``asyncio.run``, disposes the engine in ``finally``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Optional
from uuid import UUID

import typer
import yaml
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from contexts.agent.adapters.outbound.postgres import AgentPostgresRepository
from contexts.agent.application import (
    archive_agent,
    create_agent_from_methodology,
    create_agent_from_role,
    create_blank_agent,
    get_agent,
    list_agents,
    update_agent,
)
from contexts.agent.domain.agent import AgentRevision, AgentTemplate
from contexts.ingestion.adapters.outbound.postgres.source_repository import (
    PostgresSourceRepository,
)
from contexts.methodology.adapters.outbound.postgres import (
    MethodologyPostgresRepository,
    RolePostgresRepository,
)
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import (
    SecurityEventLogger,
    file_security_event_logger,
)
from shared_kernel import TenantContext, TenantId

from apps.cli._agent_run import DEFAULT_API_URL, run_invocation
from apps.cli._cross_context import (
    MethodologyLookupAdapter,
    RoleLookupAdapter,
    SourceLookupAdapter,
)
from apps.cli._runtime import (
    build_operator_principal,
    resolve_tenant_context,
    session_factory_for_tenant,
)


agent_app = typer.Typer(
    name="agent",
    help="Agent template authoring (S24 / D75).",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------
# Config-file parsing
# ---------------------------------------------------------------------


_CREATE_REQUIRED_FIELDS = (
    "name",
    "system_prompt",
    "source_ids",
    "tool_allowlist",
    "retrieval_strategy",
    "filter_tree",
    "top_k",
    "min_score",
    "model_selection",
)
_UPDATE_REQUIRED_FIELDS = (
    "system_prompt",
    "source_ids",
    "tool_allowlist",
    "retrieval_strategy",
    "filter_tree",
    "top_k",
    "min_score",
    "model_selection",
)
_CREATE_FROM_METHODOLOGY_REQUIRED_FIELDS = (
    "methodology_template_id",
    "name",
    "source_ids",
)
_CREATE_FROM_ROLE_REQUIRED_FIELDS = (
    "role_id",
    "name",
    "source_ids",
)


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise typer.BadParameter(f"config file not found: {path}")
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return yaml.safe_load(text) or {}
    if suffix == ".json":
        return json.loads(text)
    raise typer.BadParameter(
        f"unsupported config extension {suffix!r}; use .yaml, .yml, or .json"
    )


def _validate_required(config: dict[str, Any], required: tuple[str, ...]) -> None:
    missing = [f for f in required if f not in config]
    if missing:
        raise typer.BadParameter(f"config missing required fields: {missing}")


def _to_uuid_tuple(values: list[Any] | None) -> tuple[UUID, ...]:
    if not values:
        return ()
    return tuple(UUID(str(v)) for v in values)


def _to_str_tuple(values: list[Any] | None) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(str(v) for v in values)


# Reuses the parser helpers from apps.cli._role per D89 commit 4. The
# helpers handle both legacy string-shaped allowlist entries (resolved
# to well-known UUIDs for platform-managed tools) and explicit dict-
# shaped entries.
from apps.cli._role import _allowlist_to_json, _to_tool_allowlist  # noqa: E402


def _to_decimal(value: Any) -> Decimal:
    """Parse a numeric value into Decimal without float-precision loss.

    Mirrors the methodology CLI convention from S23.
    """
    return Decimal(str(value))


# ---------------------------------------------------------------------
# Repository wiring (per-tenant resolver bound to a single tenant)
# ---------------------------------------------------------------------


class _TenantBoundResolver:
    """Per-tenant sessionmaker resolver for the agent repository.

    The CLI binds the resolver to a single tenant for the lifetime of
    a command invocation. The resolver verifies the requested
    tenant_id matches the bound tenant and raises ``LookupError``
    otherwise — the CLI's dev-shape contract per
    ``apps/cli/_runtime.py``.
    """

    def __init__(
        self,
        *,
        bound_tenant_id: str,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._bound_tenant_id = bound_tenant_id
        self._sessionmaker = sessionmaker

    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]:
        if str(tenant_id) != self._bound_tenant_id:
            raise LookupError(
                f"CLI resolver bound to tenant {self._bound_tenant_id!r}; "
                f"requested {tenant_id!r}"
            )
        return self._sessionmaker


def _build_repository(
    tenant: str,
) -> tuple[
    AgentPostgresRepository,
    SecurityEventLogger,
    TenantContext,
    AsyncEngine,
]:
    """Resolve the tenant, build a tenant-bound resolver, and construct
    the AgentPostgresRepository. Returns the engine alongside so the
    caller can dispose it at command exit.
    """
    tenant_context, label = resolve_tenant_context(tenant)
    engine, sessionmaker = session_factory_for_tenant(label)
    resolver = _TenantBoundResolver(
        bound_tenant_id=str(tenant_context.tenant_id),
        sessionmaker=sessionmaker,
    )
    sec = file_security_event_logger()
    repo = AgentPostgresRepository(
        per_tenant_sessionmaker_resolver=resolver,
        security_events=sec,
    )
    return repo, sec, tenant_context, engine


# ---------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------


def _render_template_human(
    template: AgentTemplate,
    revision: Optional[AgentRevision] = None,
) -> str:
    lines = [
        f"# Agent template",
        "",
        f"id:                  {template.id}",
        f"name:                {template.name}",
        f"description:         {template.description or '(none)'}",
        f"source_methodology_template_id:      "
        f"{template.source_methodology_template_id or '(none)'}",
        f"source_methodology_template_version: "
        f"{template.source_methodology_template_version or '(none)'}",
        f"source_role_id:                      "
        f"{template.source_role_id or '(none)'}",
        f"source_role_version:                 "
        f"{template.source_role_version or '(none)'}",
        f"created_by_user_id:  {template.created_by_user_id}",
        f"created_at:          {template.created_at.isoformat()}",
    ]
    if template.archived_at is not None:
        lines.append(f"archived_at:         {template.archived_at.isoformat()}")
    if revision is not None:
        lines.extend(
            [
                "",
                f"## Revision {revision.version}",
                "",
                f"id:                       {revision.id}",
                f"system_prompt:            {revision.system_prompt}",
                f"source_ids:               {[str(s) for s in revision.source_ids]}",
                f"tool_allowlist:           {_allowlist_to_json(revision.tool_allowlist)}",
                f"retrieval_strategy:       {dict(revision.retrieval_strategy)}",
                f"filter_tree:              {dict(revision.filter_tree)}",
                f"top_k:                    {revision.top_k}",
                f"min_score:                {revision.min_score}",
                f"model_selection:          {revision.model_selection}",
                f"previous_revision_hash:   {revision.previous_revision_hash}",
                f"this_revision_hash:       {revision.this_revision_hash}",
            ]
        )
    return "\n".join(lines) + "\n"


def _render_template_json(
    template: AgentTemplate,
    revision: Optional[AgentRevision] = None,
) -> str:
    payload: dict[str, Any] = {
        "id": str(template.id),
        "name": template.name,
        "description": template.description,
        "source_methodology_template_id": (
            str(template.source_methodology_template_id)
            if template.source_methodology_template_id is not None
            else None
        ),
        "source_methodology_template_version": template.source_methodology_template_version,
        "source_role_id": (
            str(template.source_role_id)
            if template.source_role_id is not None
            else None
        ),
        "source_role_version": template.source_role_version,
        "created_by_user_id": template.created_by_user_id,
        "created_at": template.created_at.isoformat(),
        "archived_at": (
            template.archived_at.isoformat() if template.archived_at else None
        ),
    }
    if revision is not None:
        payload["revision"] = {
            "id": str(revision.id),
            "version": revision.version,
            "system_prompt": revision.system_prompt,
            "source_ids": [str(s) for s in revision.source_ids],
            "tool_allowlist": _allowlist_to_json(revision.tool_allowlist),
            "retrieval_strategy": dict(revision.retrieval_strategy),
            "filter_tree": dict(revision.filter_tree),
            "top_k": revision.top_k,
            "min_score": str(revision.min_score),
            "model_selection": revision.model_selection,
            "created_by_user_id": revision.created_by_user_id,
            "created_at": revision.created_at.isoformat(),
            "previous_revision_hash": revision.previous_revision_hash,
            "this_revision_hash": revision.this_revision_hash,
        }
    return json.dumps(payload, indent=2) + "\n"


# ---------------------------------------------------------------------
# Async coroutines for each command
# ---------------------------------------------------------------------


async def _run_create(
    tenant: str, config_path: Path
) -> tuple[AgentTemplate, AgentRevision]:
    config = _load_config(config_path)
    _validate_required(config, _CREATE_REQUIRED_FIELDS)
    repo, sec, ctx, engine = _build_repository(tenant)
    try:
        return await create_blank_agent(
            principal=build_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=ctx,
            name=config["name"],
            description=config.get("description"),
            system_prompt=config["system_prompt"],
            source_ids=_to_uuid_tuple(config["source_ids"]),
            tool_allowlist=_to_tool_allowlist(config["tool_allowlist"]),
            retrieval_strategy=config["retrieval_strategy"],
            filter_tree=config["filter_tree"],
            top_k=int(config["top_k"]),
            min_score=_to_decimal(config["min_score"]),
            model_selection=config["model_selection"],
            actor_user_id="cli-operator",
        )
    finally:
        await engine.dispose()


async def _run_get(
    tenant: str, template_id: UUID, version: int | None
) -> tuple[AgentTemplate, AgentRevision]:
    repo, sec, ctx, engine = _build_repository(tenant)
    try:
        return await get_agent(
            principal=build_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=ctx,
            template_id=template_id,
            version=version,
        )
    finally:
        await engine.dispose()


async def _run_list(
    tenant: str, include_archived: bool
) -> list[AgentTemplate]:
    repo, sec, ctx, engine = _build_repository(tenant)
    try:
        return await list_agents(
            principal=build_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=ctx,
            include_archived=include_archived,
        )
    finally:
        await engine.dispose()


async def _run_update(
    tenant: str, template_id: UUID, config_path: Path
) -> AgentRevision:
    config = _load_config(config_path)
    _validate_required(config, _UPDATE_REQUIRED_FIELDS)
    repo, sec, ctx, engine = _build_repository(tenant)
    try:
        return await update_agent(
            principal=build_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=ctx,
            template_id=template_id,
            system_prompt=config["system_prompt"],
            source_ids=_to_uuid_tuple(config["source_ids"]),
            tool_allowlist=_to_tool_allowlist(config["tool_allowlist"]),
            retrieval_strategy=config["retrieval_strategy"],
            filter_tree=config["filter_tree"],
            top_k=int(config["top_k"]),
            min_score=_to_decimal(config["min_score"]),
            model_selection=config["model_selection"],
            actor_user_id="cli-operator",
        )
    finally:
        await engine.dispose()


async def _run_archive(tenant: str, template_id: UUID) -> AgentTemplate:
    repo, sec, ctx, engine = _build_repository(tenant)
    try:
        return await archive_agent(
            principal=build_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=ctx,
            template_id=template_id,
        )
    finally:
        await engine.dispose()


async def _run_create_from_methodology(
    tenant: str, config_path: Path
) -> tuple[AgentTemplate, AgentRevision]:
    """Resolve the three repositories (control-plane methodology, per-
    tenant source, per-tenant agent), construct the cross-context
    adapters, and invoke the use case. Disposes both engines plus the
    methodology repository in ``finally`` regardless of outcome."""
    config = _load_config(config_path)
    _validate_required(config, _CREATE_FROM_METHODOLOGY_REQUIRED_FIELDS)

    tenant_context, label = resolve_tenant_context(tenant)
    tenant_engine, tenant_sessionmaker = session_factory_for_tenant(label)
    sec = file_security_event_logger()

    # Agent repository: per-tenant sessionmaker resolver, identical to
    # _build_repository's shape but constructed inline here so the
    # tenant_engine can dispose alongside the methodology engine in a
    # single finally block.
    agent_resolver = _TenantBoundResolver(
        bound_tenant_id=str(tenant_context.tenant_id),
        sessionmaker=tenant_sessionmaker,
    )
    agent_repo = AgentPostgresRepository(
        per_tenant_sessionmaker_resolver=agent_resolver,
        security_events=sec,
    )

    # Source repository: same per-tenant sessionmaker; the adapter
    # treats the sessionmaker as already-tenant-bound and routes the
    # tenant_id at the SQL predicate layer.
    source_repo = PostgresSourceRepository(session_factory=tenant_sessionmaker)
    source_lookup = SourceLookupAdapter(repository=source_repo)

    # Methodology and role repositories: control-plane Postgres, each
    # owns its own engine via from_settings; dispose both at command
    # exit. S26a-1 per D86: methodology resolution goes through both
    # repos (methodology revision carries role_refs; adapter resolves
    # to the role's content bundle for the consumer-side MethodologyView).
    control_plane_settings = ControlPlaneSettings()
    methodology_repo = MethodologyPostgresRepository.from_settings(
        settings=control_plane_settings, security_events=sec
    )
    role_repo = RolePostgresRepository.from_settings(
        settings=control_plane_settings, security_events=sec
    )
    methodology_lookup = MethodologyLookupAdapter(
        methodology_repository=methodology_repo,
        role_repository=role_repo,
    )

    try:
        return await create_agent_from_methodology(
            principal=build_operator_principal(),
            repository=agent_repo,
            methodology_lookup=methodology_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=tenant_context,
            methodology_template_id=UUID(str(config["methodology_template_id"])),
            methodology_version=(
                int(config["methodology_version"])
                if config.get("methodology_version") is not None
                else None
            ),
            name=config["name"],
            source_ids=_to_uuid_tuple(config["source_ids"]),
            actor_user_id="cli-operator",
        )
    finally:
        await methodology_repo.dispose()
        await role_repo.dispose()
        await tenant_engine.dispose()


async def _run_create_from_role(
    tenant: str, config_path: Path
) -> tuple[AgentTemplate, AgentRevision]:
    """Resolve the three repositories (control-plane role, per-tenant
    source, per-tenant agent), construct the cross-context adapters,
    and invoke the role-clone use case. Disposes both engines plus the
    role repository in ``finally`` regardless of outcome (S26a-2 /
    D86)."""
    config = _load_config(config_path)
    _validate_required(config, _CREATE_FROM_ROLE_REQUIRED_FIELDS)

    tenant_context, label = resolve_tenant_context(tenant)
    tenant_engine, tenant_sessionmaker = session_factory_for_tenant(label)
    sec = file_security_event_logger()

    agent_resolver = _TenantBoundResolver(
        bound_tenant_id=str(tenant_context.tenant_id),
        sessionmaker=tenant_sessionmaker,
    )
    agent_repo = AgentPostgresRepository(
        per_tenant_sessionmaker_resolver=agent_resolver,
        security_events=sec,
    )

    source_repo = PostgresSourceRepository(session_factory=tenant_sessionmaker)
    source_lookup = SourceLookupAdapter(repository=source_repo)

    # Role repository: control-plane Postgres; the role-clone flow
    # does not need the methodology repository because no methodology
    # is referenced.
    control_plane_settings = ControlPlaneSettings()
    role_repo = RolePostgresRepository.from_settings(
        settings=control_plane_settings, security_events=sec
    )
    role_lookup = RoleLookupAdapter(role_repository=role_repo)

    try:
        return await create_agent_from_role(
            principal=build_operator_principal(),
            repository=agent_repo,
            role_lookup=role_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=tenant_context,
            role_id=UUID(str(config["role_id"])),
            role_version=(
                int(config["role_version"])
                if config.get("role_version") is not None
                else None
            ),
            name=config["name"],
            source_ids=_to_uuid_tuple(config["source_ids"]),
            actor_user_id="cli-operator",
        )
    finally:
        await role_repo.dispose()
        await tenant_engine.dispose()


# ---------------------------------------------------------------------
# Typer command surface
# ---------------------------------------------------------------------


@agent_app.command("create")
def agent_create(
    tenant: Annotated[
        str,
        typer.Option(
            "--tenant",
            help="Tenant short label ('a', 'b') or UUID.",
        ),
    ],
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            help="Path to the agent config (.yaml, .yml, or .json).",
        ),
    ],
) -> None:
    """Create a new blank agent template with revision 1."""
    template, revision = asyncio.run(_run_create(tenant, config))
    sys.stdout.write(
        f"created agent_template_id={template.id} "
        f"revision_id={revision.id} version={revision.version}\n"
    )


@agent_app.command("get")
def agent_get(
    template_id: Annotated[
        UUID,
        typer.Argument(help="The agent template id."),
    ],
    tenant: Annotated[
        str,
        typer.Option(
            "--tenant",
            help="Tenant short label ('a', 'b') or UUID.",
        ),
    ],
    version: Annotated[
        Optional[int],
        typer.Option(
            "--version",
            help="Specific revision version; default is the latest.",
        ),
    ] = None,
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON instead of human-readable text."),
    ] = False,
) -> None:
    """Retrieve an agent template plus its named or latest revision."""
    template, revision = asyncio.run(_run_get(tenant, template_id, version))
    if output_json:
        sys.stdout.write(_render_template_json(template, revision))
    else:
        sys.stdout.write(_render_template_human(template, revision))


@agent_app.command("list")
def agent_list(
    tenant: Annotated[
        str,
        typer.Option(
            "--tenant",
            help="Tenant short label ('a', 'b') or UUID.",
        ),
    ],
    include_archived: Annotated[
        bool,
        typer.Option(
            "--include-archived",
            help="Include archived templates in the listing.",
        ),
    ] = False,
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON instead of human-readable text."),
    ] = False,
) -> None:
    """List the tenant's agent templates."""
    templates = asyncio.run(_run_list(tenant, include_archived))
    if output_json:
        payload = [
            {
                "id": str(t.id),
                "name": t.name,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
                "archived_at": (
                    t.archived_at.isoformat() if t.archived_at else None
                ),
            }
            for t in templates
        ]
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return
    if not templates:
        sys.stdout.write("(no agent templates)\n")
        return
    for t in templates:
        archived_marker = " [archived]" if t.archived_at else ""
        sys.stdout.write(
            f"{t.id}  {t.name}{archived_marker}  "
            f"(created {t.created_at.isoformat()})\n"
        )


@agent_app.command("update")
def agent_update(
    template_id: Annotated[
        UUID,
        typer.Argument(help="The agent template id."),
    ],
    tenant: Annotated[
        str,
        typer.Option(
            "--tenant",
            help="Tenant short label ('a', 'b') or UUID.",
        ),
    ],
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            help="Path to the revision config (.yaml, .yml, or .json).",
        ),
    ],
) -> None:
    """Add a new revision to an existing agent template."""
    revision = asyncio.run(_run_update(tenant, template_id, config))
    sys.stdout.write(
        f"created revision_id={revision.id} version={revision.version}\n"
    )


@agent_app.command("archive")
def agent_archive(
    template_id: Annotated[
        UUID,
        typer.Argument(help="The agent template id."),
    ],
    tenant: Annotated[
        str,
        typer.Option(
            "--tenant",
            help="Tenant short label ('a', 'b') or UUID.",
        ),
    ],
) -> None:
    """Mark an agent template as archived."""
    template = asyncio.run(_run_archive(tenant, template_id))
    sys.stdout.write(
        f"archived agent_template_id={template.id} "
        f"archived_at={template.archived_at.isoformat()}\n"
    )


@agent_app.command("create-from-methodology")
def agent_create_from_methodology(
    tenant: Annotated[
        str,
        typer.Option(
            "--tenant",
            help="Tenant short label ('a', 'b') or UUID.",
        ),
    ],
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            help=(
                "Path to the clone config (.yaml, .yml, or .json) "
                "with methodology_template_id, optional methodology_version, "
                "name, and source_ids."
            ),
        ),
    ],
) -> None:
    """Clone a methodology template into a new agent (S25 / D79)."""
    template, revision = asyncio.run(_run_create_from_methodology(tenant, config))
    sys.stdout.write(
        f"created agent_template_id={template.id} "
        f"revision_id={revision.id} version={revision.version} "
        f"source_methodology_template_id={template.source_methodology_template_id} "
        f"source_methodology_template_version={template.source_methodology_template_version} "
        f"source_role_id={template.source_role_id} "
        f"source_role_version={template.source_role_version}\n"
    )


@agent_app.command("run")
def agent_run(
    tenant: Annotated[
        str,
        typer.Option(
            "--tenant",
            help="Tenant short label ('a', 'b') or UUID.",
        ),
    ],
    agent: Annotated[
        UUID,
        typer.Option(
            "--agent",
            help="The agent template id to invoke.",
        ),
    ],
    user_input: Annotated[
        str,
        typer.Option(
            "--input",
            help="The user message to send to the agent.",
        ),
    ],
    api_url: Annotated[
        str,
        typer.Option(
            "--api-url",
            help=(
                "Padhanam API base URL. Default targets the in-container "
                "uvicorn at http://localhost:8000."
            ),
        ),
    ] = DEFAULT_API_URL,
    output_file: Annotated[
        Optional[Path],
        typer.Option(
            "--output-file",
            help="Tee the rendered stream to this file (in addition to stdout).",
        ),
    ] = None,
) -> None:
    """Invoke an agent through the SSE endpoint and render the stream.

    Posts to ``POST {api-url}/agents/{agent_id}/invoke`` with a dev
    token carrying the resolved tenant UUID and the ``agent.invoke``
    role, parses the SSE event stream (D90 vocabulary), and renders
    each event to stdout. Exit code maps to the observed terminal
    event per D90:

    - ``InvocationCompleted`` → 0
    - ``InvariantBlocked`` → 2
    - ``InvocationFailed`` (or protocol failure) → 1
    """
    exit_code = asyncio.run(
        run_invocation(
            tenant_label=tenant,
            agent_id=str(agent),
            user_input=user_input,
            api_url=api_url,
            output_file=output_file,
        )
    )
    raise typer.Exit(code=exit_code)


@agent_app.command("create-from-role")
def agent_create_from_role(
    tenant: Annotated[
        str,
        typer.Option(
            "--tenant",
            help="Tenant short label ('a', 'b') or UUID.",
        ),
    ],
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            help=(
                "Path to the clone config (.yaml, .yml, or .json) "
                "with role_id, optional role_version, name, and source_ids."
            ),
        ),
    ],
) -> None:
    """Clone a role template directly into a new agent (S26a-2 / D86)."""
    template, revision = asyncio.run(_run_create_from_role(tenant, config))
    sys.stdout.write(
        f"created agent_template_id={template.id} "
        f"revision_id={revision.id} version={revision.version} "
        f"source_role_id={template.source_role_id} "
        f"source_role_version={template.source_role_version}\n"
    )
