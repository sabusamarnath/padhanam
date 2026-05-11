"""Methodology CLI orchestration (S23 / D74, S26a-1 / D86 refactor).

Five subcommands at the ``padhanam methodology`` namespace: ``create``,
``get``, ``list``, ``update``, ``retire``. Operator-context resolution
at the command boundary mirrors the P5 dev-shape pattern; production
CLI auth lands at Phase 2.

S26a-1 refactor per D86: the methodology aggregate becomes a playbook
composing roles via ``role_refs`` rather than carrying the constraint
bundle directly. The bundle moves to the role aggregate; the CLI's
methodology surface now operates on ``role_refs`` references rather
than the prior nine bundle fields. Methodology authoring at S26a-1
is followed by a new ``padhanam role`` CLI namespace at S26a-2 for
role authoring.

Config file shape (YAML or JSON, auto-detected by extension):

  create — methodology template + revision-1 payload:
    name: str
    description: str | null
    role_refs:
      - role_id: <uuid string>
        role_version: int
        overrides: optional dict (Phase 1 ignored; reserved for D86 Phase 2)

  update — revision content only (name and description immutable):
    role_refs: same shape as create

The CLI parses the config, validates required fields, converts the
``role_refs`` list into a tuple of ``RoleRef`` frozen dataclasses,
then invokes the use case. Output is human-readable by default;
``--json`` produces machine-readable shapes.
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

from contexts.methodology.adapters.outbound.postgres import (
    MethodologyPostgresRepository,
)
from contexts.methodology.application import (
    RoleRef,
    create_methodology_template,
    get_methodology_template,
    list_methodology_templates,
    retire_methodology_template,
    update_methodology_template,
)
from contexts.methodology.domain.methodology import (
    MethodologyRevision,
    MethodologyTemplate,
)
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import (
    SecurityEventLogger,
    file_security_event_logger,
)

from apps.cli._runtime import build_operator_principal


methodology_app = typer.Typer(
    name="methodology",
    help="Methodology template authoring (S23 / D74; refactored at S26a-1 per D86).",
    no_args_is_help=True,
)


_CREATE_REQUIRED_FIELDS = ("name", "role_refs")
_UPDATE_REQUIRED_FIELDS = ("role_refs",)


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


def _to_role_refs(values: list[Any] | None) -> tuple[RoleRef, ...]:
    if not values:
        raise typer.BadParameter(
            "role_refs cannot be empty; the methodology must compose at "
            "least one role per D86"
        )
    refs: list[RoleRef] = []
    for entry in values:
        if not isinstance(entry, dict):
            raise typer.BadParameter(
                f"each role_refs entry must be an object with role_id and "
                f"role_version keys; got {entry!r}"
            )
        if "role_id" not in entry or "role_version" not in entry:
            raise typer.BadParameter(
                f"role_refs entry missing role_id or role_version: {entry!r}"
            )
        refs.append(
            RoleRef(
                role_id=UUID(str(entry["role_id"])),
                role_version=int(entry["role_version"]),
                overrides=entry.get("overrides"),
            )
        )
    return tuple(refs)


# ---------------------------------------------------------------------
# Repository wiring
# ---------------------------------------------------------------------


def _build_repository() -> tuple[MethodologyPostgresRepository, SecurityEventLogger]:
    settings = ControlPlaneSettings()
    sec = file_security_event_logger()
    repo = MethodologyPostgresRepository.from_settings(
        settings=settings, security_events=sec
    )
    return repo, sec


# ---------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------


def _render_template_human(
    template: MethodologyTemplate,
    revision: Optional[MethodologyRevision] = None,
) -> str:
    lines = [
        f"# Methodology template",
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
                f"role_refs:",
            ]
        )
        for ref in revision.role_refs:
            lines.append(
                f"  - role_id={ref.role_id} "
                f"role_version={ref.role_version} "
                f"overrides={ref.overrides if ref.overrides is not None else '(none)'}"
            )
        lines.extend(
            [
                f"previous_revision_hash:   {revision.previous_revision_hash}",
                f"this_revision_hash:       {revision.this_revision_hash}",
            ]
        )
    return "\n".join(lines) + "\n"


def _render_template_json(
    template: MethodologyTemplate,
    revision: Optional[MethodologyRevision] = None,
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
            "role_refs": [
                {
                    "role_id": str(r.role_id),
                    "role_version": r.role_version,
                    "overrides": (
                        None if r.overrides is None else dict(r.overrides)
                    ),
                }
                for r in revision.role_refs
            ],
            "created_by_user_id": revision.created_by_user_id,
            "created_at": revision.created_at.isoformat(),
            "previous_revision_hash": revision.previous_revision_hash,
            "this_revision_hash": revision.this_revision_hash,
        }
    return json.dumps(payload, indent=2) + "\n"


# ---------------------------------------------------------------------
# Async coroutines for each command
# ---------------------------------------------------------------------


async def _run_create(config_path: Path) -> tuple[MethodologyTemplate, MethodologyRevision]:
    config = _load_config(config_path)
    _validate_required(config, _CREATE_REQUIRED_FIELDS)
    repo, sec = _build_repository()
    try:
        return await create_methodology_template(
            principal=build_operator_principal(),
            repository=repo,
            security_events=sec,
            name=config["name"],
            description=config.get("description"),
            role_refs=_to_role_refs(config["role_refs"]),
            actor_user_id="cli-operator",
        )
    finally:
        await repo.dispose()


async def _run_get(
    template_id: UUID, version: int | None
) -> tuple[MethodologyTemplate, MethodologyRevision]:
    repo, _ = _build_repository()
    try:
        return await get_methodology_template(
            principal=build_operator_principal(),
            repository=repo,
            template_id=template_id,
            version=version,
        )
    finally:
        await repo.dispose()


async def _run_list() -> list[MethodologyTemplate]:
    repo, _ = _build_repository()
    try:
        return await list_methodology_templates(
            principal=build_operator_principal(),
            repository=repo,
        )
    finally:
        await repo.dispose()


async def _run_update(template_id: UUID, config_path: Path) -> MethodologyRevision:
    config = _load_config(config_path)
    _validate_required(config, _UPDATE_REQUIRED_FIELDS)
    repo, sec = _build_repository()
    try:
        return await update_methodology_template(
            principal=build_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=template_id,
            role_refs=_to_role_refs(config["role_refs"]),
            actor_user_id="cli-operator",
        )
    finally:
        await repo.dispose()


async def _run_retire(template_id: UUID) -> MethodologyTemplate:
    repo, sec = _build_repository()
    try:
        return await retire_methodology_template(
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


@methodology_app.command("create")
def methodology_create(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            help="Path to the methodology config (.yaml, .yml, or .json).",
        ),
    ],
) -> None:
    """Create a new methodology template with revision 1."""
    template, revision = asyncio.run(_run_create(config))
    sys.stdout.write(
        f"created methodology_template_id={template.id} "
        f"revision_id={revision.id} version={revision.version}\n"
    )


@methodology_app.command("get")
def methodology_get(
    template_id: Annotated[
        UUID,
        typer.Argument(help="The methodology template id."),
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
    """Retrieve a methodology template plus its named or latest revision."""
    template, revision = asyncio.run(_run_get(template_id, version))
    if output_json:
        sys.stdout.write(_render_template_json(template, revision))
    else:
        sys.stdout.write(_render_template_human(template, revision))


@methodology_app.command("list")
def methodology_list(
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON instead of human-readable text."),
    ] = False,
) -> None:
    """List all non-archived methodology templates."""
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
        sys.stdout.write("(no methodology templates)\n")
        return
    for t in templates:
        sys.stdout.write(
            f"{t.id}  {t.name}  (created {t.created_at.isoformat()})\n"
        )


@methodology_app.command("update")
def methodology_update(
    template_id: Annotated[
        UUID,
        typer.Argument(help="The methodology template id."),
    ],
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            help="Path to the revision config (.yaml, .yml, or .json).",
        ),
    ],
) -> None:
    """Add a new revision to an existing methodology template."""
    revision = asyncio.run(_run_update(template_id, config))
    sys.stdout.write(
        f"created revision_id={revision.id} version={revision.version}\n"
    )


@methodology_app.command("retire")
def methodology_retire(
    template_id: Annotated[
        UUID,
        typer.Argument(help="The methodology template id."),
    ],
) -> None:
    """Mark a methodology template as archived."""
    template = asyncio.run(_run_retire(template_id))
    sys.stdout.write(
        f"retired methodology_template_id={template.id} "
        f"archived_at={template.archived_at.isoformat()}\n"
    )
