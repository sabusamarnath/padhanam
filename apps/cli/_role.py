"""Role CLI orchestration (S26a-2 / D86).

Five subcommands at the ``padhanam role`` namespace: ``create``,
``get``, ``list``, ``update``, ``archive``. Operator-context
resolution at the command boundary mirrors the methodology CLI
pattern from S23; production CLI auth lands at Phase 2.

The role aggregate lives within ``contexts/methodology/`` per D86's
Y2 sub-choice (Phase 1 co-locates role with methodology context) but
the role CLI is a sibling namespace to the methodology CLI because
role authoring is an operator-facing concept distinct from
methodology authoring. The methodology CLI references roles by id;
the role CLI authors the role's content bundle that methodology
revisions reference.

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
  per the template-level identity convention from D74 / D75):
    system_prompt, source_ids, tool_allowlist, retrieval_strategy,
    filter_tree, top_k, min_score, model_selection.

Auth posture: role mutations require operator-context (the role
context's create / update / retire use cases gate on is_operator);
role reads are any-authenticated per the methodology shape. The CLI
binds the operator principal at the command boundary by reusing
``build_operator_principal`` from ``apps/cli/_runtime.py``.

Async lifecycle: each command builds a fresh repository (control-
plane Postgres via ControlPlaneSettings) plus a security event
logger, runs the use case via ``asyncio.run``, disposes the engine
in ``finally``.
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

from contexts.methodology.adapters.outbound.postgres import (
    RolePostgresRepository,
)
from contexts.methodology.application import (
    create_role_template,
    get_role_template,
    list_role_templates,
    retire_role_template,
    update_role_template,
)
from contexts.methodology.domain.role import RoleRevision, RoleTemplate
from padhanam.observability.security_events import SecurityEventLogger

from apps.cli._composition import get_compositions
from apps.cli._runtime import build_operator_principal


role_app = typer.Typer(
    name="role",
    help="Role template authoring (S26a-2 / D86).",
    no_args_is_help=True,
)


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


# Well-known UUIDs for platform-managed tools seeded by Alembic
# 0009_create_tools_tables per D89. The CLI resolves legacy string-
# shaped allowlist entries by name; richer tool authoring lands at
# the padhanam tool CLI at S28b commit 8.
_RETRIEVAL_TOOL_ID = UUID("00000000-0000-0000-0000-000000000001")
_RETRIEVAL_REVISION_ID = UUID("00000000-0000-0000-0000-000000000002")
_NAMED_TOOL_PINS: dict[str, tuple[UUID, UUID]] = {
    "retrieval": (_RETRIEVAL_TOOL_ID, _RETRIEVAL_REVISION_ID),
}


def _to_tool_allowlist(values: list[Any] | None) -> tuple[Any, ...]:
    """Parse a tool_allowlist config entry to a tuple of pinned entries (D89).

    Accepts two shapes per the commit-4 migration story:

    - **String entries**: legacy shape. Each name resolves to the
      well-known UUID for the platform-managed tool. Phase 1 has one
      name (``retrieval``); unknown names raise.

    - **Dict entries**: explicit pin. Keys ``tool_id`` and
      ``revision_id`` (both UUID strings). The dict form is what the
      ``padhanam tool list`` output produces for round-tripping at
      S28b commit 8.

    Lazy import of ``ToolAllowlistEntry`` from ``shared_kernel`` keeps
    the helper independent of the type if the caller imports it
    elsewhere (avoids circular import in some test paths).
    """
    from shared_kernel import ToolAllowlistEntry

    if not values:
        return ()
    out: list[ToolAllowlistEntry] = []
    for entry in values:
        if isinstance(entry, str):
            pin = _NAMED_TOOL_PINS.get(entry)
            if pin is None:
                raise typer.BadParameter(
                    f"tool_allowlist entry {entry!r} is not a known "
                    f"platform-managed tool; pass {{tool_id, revision_id}} "
                    f"explicitly or use one of: "
                    f"{sorted(_NAMED_TOOL_PINS.keys())!r}"
                )
            tool_id, revision_id = pin
            out.append(
                ToolAllowlistEntry(tool_id=tool_id, revision_id=revision_id)
            )
        elif isinstance(entry, dict):
            try:
                tool_id = UUID(str(entry["tool_id"]))
                revision_id = UUID(str(entry["revision_id"]))
            except (KeyError, ValueError, TypeError) as exc:
                raise typer.BadParameter(
                    f"tool_allowlist entry {entry!r} malformed; "
                    f"expected {{tool_id, revision_id}}: {exc}"
                ) from exc
            out.append(
                ToolAllowlistEntry(tool_id=tool_id, revision_id=revision_id)
            )
        else:
            raise typer.BadParameter(
                f"tool_allowlist entry {entry!r} has unexpected "
                f"type {type(entry).__name__!r}"
            )
    return tuple(out)


def _allowlist_to_json(allowlist: tuple[Any, ...]) -> list[dict[str, str]]:
    """Serialise a tool_allowlist tuple to JSON-renderer-friendly dicts (D89)."""
    return [
        {"tool_id": str(e.tool_id), "revision_id": str(e.revision_id)}
        for e in allowlist
    ]


def _to_decimal(value: Any) -> Decimal:
    """Parse a numeric value into Decimal without float-precision loss."""
    return Decimal(str(value))


def _build_repository() -> tuple[RolePostgresRepository, SecurityEventLogger]:
    # D100: settings + security_events come from the composition root,
    # not from per-command construction. Tests override via
    # `apps.cli._composition.set_compositions(...)` in a fixture.
    compositions = get_compositions()
    repo = RolePostgresRepository.from_settings(
        settings=compositions.control_plane_settings,
        security_events=compositions.security_events,
    )
    return repo, compositions.security_events


# ---------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------


def _render_template_human(
    template: RoleTemplate,
    revision: Optional[RoleRevision] = None,
) -> str:
    lines = [
        f"# Role template",
        "",
        f"id:                  {template.id}",
        f"name:                {template.name}",
        f"description:         {template.description or '(none)'}",
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
    template: RoleTemplate,
    revision: Optional[RoleRevision] = None,
) -> str:
    payload: dict[str, Any] = {
        "id": str(template.id),
        "name": template.name,
        "description": template.description,
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


async def _run_create(config_path: Path) -> tuple[RoleTemplate, RoleRevision]:
    config = _load_config(config_path)
    _validate_required(config, _CREATE_REQUIRED_FIELDS)
    repo, sec = _build_repository()
    try:
        return await create_role_template(
            principal=build_operator_principal(),
            repository=repo,
            security_events=sec,
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
        await repo.dispose()


async def _run_get(
    template_id: UUID, version: int | None
) -> tuple[RoleTemplate, RoleRevision]:
    repo, _ = _build_repository()
    try:
        return await get_role_template(
            principal=build_operator_principal(),
            repository=repo,
            template_id=template_id,
            version=version,
        )
    finally:
        await repo.dispose()


async def _run_list() -> list[RoleTemplate]:
    repo, _ = _build_repository()
    try:
        return await list_role_templates(
            principal=build_operator_principal(),
            repository=repo,
        )
    finally:
        await repo.dispose()


async def _run_update(template_id: UUID, config_path: Path) -> RoleRevision:
    config = _load_config(config_path)
    _validate_required(config, _UPDATE_REQUIRED_FIELDS)
    repo, sec = _build_repository()
    try:
        return await update_role_template(
            principal=build_operator_principal(),
            repository=repo,
            security_events=sec,
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
        await repo.dispose()


async def _run_archive(template_id: UUID) -> RoleTemplate:
    repo, sec = _build_repository()
    try:
        return await retire_role_template(
            principal=build_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=template_id,
        )
    finally:
        await repo.dispose()


# ---------------------------------------------------------------------
# Typer command surface
# ---------------------------------------------------------------------


@role_app.command("create")
def role_create(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            help="Path to the role config (.yaml, .yml, or .json).",
        ),
    ],
) -> None:
    """Create a new role template with revision 1."""
    template, revision = asyncio.run(_run_create(config))
    sys.stdout.write(
        f"created role_template_id={template.id} "
        f"revision_id={revision.id} version={revision.version}\n"
    )


@role_app.command("get")
def role_get(
    template_id: Annotated[
        UUID,
        typer.Argument(help="The role template id."),
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
    """Retrieve a role template plus its named or latest revision."""
    template, revision = asyncio.run(_run_get(template_id, version))
    if output_json:
        sys.stdout.write(_render_template_json(template, revision))
    else:
        sys.stdout.write(_render_template_human(template, revision))


@role_app.command("list")
def role_list(
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON instead of human-readable text."),
    ] = False,
) -> None:
    """List all non-archived role templates."""
    templates = asyncio.run(_run_list())
    if output_json:
        payload = [
            {
                "id": str(t.id),
                "name": t.name,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
            }
            for t in templates
        ]
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return
    if not templates:
        sys.stdout.write("(no role templates)\n")
        return
    for t in templates:
        sys.stdout.write(
            f"{t.id}  {t.name}  (created {t.created_at.isoformat()})\n"
        )


@role_app.command("update")
def role_update(
    template_id: Annotated[
        UUID,
        typer.Argument(help="The role template id."),
    ],
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            help="Path to the revision config (.yaml, .yml, or .json).",
        ),
    ],
) -> None:
    """Add a new revision to an existing role template."""
    revision = asyncio.run(_run_update(template_id, config))
    sys.stdout.write(
        f"created revision_id={revision.id} version={revision.version}\n"
    )


@role_app.command("archive")
def role_archive(
    template_id: Annotated[
        UUID,
        typer.Argument(help="The role template id."),
    ],
) -> None:
    """Mark a role template as archived."""
    template = asyncio.run(_run_archive(template_id))
    sys.stdout.write(
        f"archived role_template_id={template.id} "
        f"archived_at={template.archived_at.isoformat()}\n"
    )
