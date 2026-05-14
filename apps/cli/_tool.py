"""Tool CLI orchestration (S28b commit 8, D89).

Three subcommands at the ``padhanam tool`` namespace: ``create``,
``get``, ``list``. The CLI is operator-facing (control-plane scoped
per D89's storage-location resolution). Authoring uses a config
file (YAML or JSON) mirroring the methodology / role CLI pattern.

Config file shape for ``create``:

  name: str
  description: str | null
  classification: str  # one of: read-only, drafting,
                       #         user-affecting-with-consent,
                       #         financial, communication, legal
  parameters_schema: dict  # JSON-schema for the tool's input
  returns_schema: dict     # JSON-schema for the tool's result

Per D89's Phase 1 authoring prohibition, the create command rejects
classifications ``financial``, ``communication``, and ``legal`` with
``ClassificationProhibitedError``. The error message names the
per-invocation confirmation pathway deferred-decisions entry so
operators see the forward trajectory.

Async lifecycle per the established pattern (S23 methodology, S26a-2
role): each command builds a fresh ``ToolPostgresRepository`` against
control-plane Postgres plus a security event logger, runs the use
case via ``asyncio.run``, disposes the engine in ``finally``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated, Any, Optional
from uuid import UUID

import typer
import yaml

from contexts.tools.adapters.outbound.postgres import ToolPostgresRepository
from contexts.tools.application import (
    create_tool,
    get_tool,
    list_tools,
)
from contexts.tools.domain.exceptions import (
    ClassificationProhibitedError,
    ToolNotFoundError,
)
from contexts.tools.domain.tool import Classification, Tool, ToolRevision
from padhanam.observability.security_events import SecurityEventLogger

from apps.cli._composition import get_compositions
from apps.cli._runtime import build_operator_principal


tool_app = typer.Typer(
    name="tool",
    help="Tool registry authoring (S28b / D89).",
    no_args_is_help=True,
)


_CREATE_REQUIRED_FIELDS = (
    "name",
    "classification",
    "parameters_schema",
    "returns_schema",
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


def _build_repository() -> tuple[ToolPostgresRepository, SecurityEventLogger]:
    # D100: settings + security_events come from the composition root,
    # not from per-command construction. Tests override via
    # `apps.cli._composition.set_compositions(...)` in a fixture.
    compositions = get_compositions()
    repo = ToolPostgresRepository.from_settings(
        settings=compositions.control_plane_settings,
        security_events=compositions.security_events,
    )
    return repo, compositions.security_events


def _render_template_human(
    template: Tool,
    revision: Optional[ToolRevision] = None,
) -> str:
    lines = [
        f"# Tool",
        "",
        f"id:                  {template.id}",
        f"name:                {template.name}",
        f"description:         {template.description or '(none)'}",
        f"classification:      {template.classification.value}",
        f"created_by_user_id:  {template.created_by_user_id}",
        f"created_at:          {template.created_at.isoformat()}",
    ]
    if template.archived_at is not None:
        lines.append(
            f"archived_at:         {template.archived_at.isoformat()}"
        )
    if revision is not None:
        lines.extend(
            [
                "",
                f"## Revision {revision.version}",
                "",
                f"id:                       {revision.id}",
                f"parameters_schema:        {dict(revision.parameters_schema)}",
                f"returns_schema:           {dict(revision.returns_schema)}",
                f"bc_result:                {dict(revision.bc_result)}",
                f"previous_revision_hash:   {revision.previous_revision_hash}",
                f"this_revision_hash:       {revision.this_revision_hash}",
            ]
        )
    return "\n".join(lines) + "\n"


def _render_template_json(
    template: Tool,
    revision: Optional[ToolRevision] = None,
) -> str:
    payload: dict[str, Any] = {
        "id": str(template.id),
        "name": template.name,
        "description": template.description,
        "classification": template.classification.value,
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
            "parameters_schema": dict(revision.parameters_schema),
            "returns_schema": dict(revision.returns_schema),
            "bc_result": dict(revision.bc_result),
            "created_by_user_id": revision.created_by_user_id,
            "created_at": revision.created_at.isoformat(),
            "previous_revision_hash": revision.previous_revision_hash,
            "this_revision_hash": revision.this_revision_hash,
        }
    return json.dumps(payload, indent=2) + "\n"


async def _run_create(config_path: Path) -> tuple[Tool, ToolRevision]:
    config = _load_config(config_path)
    _validate_required(config, _CREATE_REQUIRED_FIELDS)
    try:
        classification = Classification(config["classification"])
    except ValueError as exc:
        raise typer.BadParameter(
            f"classification {config['classification']!r} is not one of "
            f"the six D89 categories: "
            f"{[c.value for c in Classification]!r}"
        ) from exc

    repo, sec = _build_repository()
    try:
        return await create_tool(
            principal=build_operator_principal(),
            repository=repo,
            security_events=sec,
            name=config["name"],
            description=config.get("description"),
            classification=classification,
            parameters_schema=config["parameters_schema"],
            returns_schema=config["returns_schema"],
            actor_user_id="cli-operator",
        )
    finally:
        await repo.dispose()


async def _run_get(tool_id: UUID) -> tuple[Tool, ToolRevision]:
    repo, _ = _build_repository()
    try:
        return await get_tool(
            principal=build_operator_principal(),
            repository=repo,
            template_id=tool_id,
        )
    finally:
        await repo.dispose()


async def _run_list() -> list[Tool]:
    repo, _ = _build_repository()
    try:
        return await list_tools(
            principal=build_operator_principal(),
            repository=repo,
        )
    finally:
        await repo.dispose()


@tool_app.command("create")
def create_command(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to YAML or JSON config (name, classification, schemas).",
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emit JSON instead of human-readable output.",
        ),
    ] = False,
) -> None:
    """Author a new tool with revision 1.

    Phase 1 authoring is prohibited for classifications financial,
    communication, and legal per D89. The command exits non-zero with
    an error message naming the per-invocation confirmation pathway
    deferred-decisions entry when the prohibited path is taken.
    """
    try:
        template, revision = asyncio.run(_run_create(config))
    except ClassificationProhibitedError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=2)
    output = (
        _render_template_json(template, revision)
        if json_output
        else _render_template_human(template, revision)
    )
    sys.stdout.write(output)


@tool_app.command("get")
def get_command(
    tool_id: Annotated[
        str,
        typer.Option(
            "--id",
            help="Tool UUID to fetch.",
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emit JSON instead of human-readable output.",
        ),
    ] = False,
) -> None:
    """Read a tool plus its latest revision."""
    try:
        template, revision = asyncio.run(_run_get(UUID(tool_id)))
    except ToolNotFoundError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1)
    output = (
        _render_template_json(template, revision)
        if json_output
        else _render_template_human(template, revision)
    )
    sys.stdout.write(output)


@tool_app.command("list")
def list_command(
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emit JSON instead of human-readable output.",
        ),
    ] = False,
) -> None:
    """List all non-archived tools."""
    templates = asyncio.run(_run_list())
    if json_output:
        payload = [
            {
                "id": str(t.id),
                "name": t.name,
                "classification": t.classification.value,
                "description": t.description,
            }
            for t in templates
        ]
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return
    if not templates:
        sys.stdout.write("(no tools registered)\n")
        return
    lines = [
        f"{t.classification.value:30s}  {t.id}  {t.name}"
        for t in templates
    ]
    sys.stdout.write("\n".join(lines) + "\n")
