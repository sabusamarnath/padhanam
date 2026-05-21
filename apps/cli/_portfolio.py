"""Portfolio CLI orchestration (S43 / D124).

One typer sub-app — ``portfolio`` — with five action commands:
create-case, create-data-point, revise-data-point, list-cases,
get-case. The CLI is the operator-facing write path for the S43
live-stack smoke: without it, criterion 14 has no honest way to
produce Cases short of raw SQL fixture seeding, which would bypass
the audit-events port and compromise the audit-trail discipline.

Tenant context resolution uses ``build_tenant_wiring`` per the
dev-only label-or-UUID convention. The audit adapter mirrors the
optimization CLI's control-plane-anchored construction. The
authoring actor is the ``ActorReference`` placeholder per D124 —
``--actor`` defaults to ``operator``; the full ActorContext lands
at S44.
"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any, Optional
from uuid import UUID

import typer

from contexts.audit.adapters.outbound.postgres.audit import (
    PostgresAuditAdapter,
)

from contexts.portfolio.adapters.outbound.postgres.portfolio_reader import (
    PostgresPortfolioReader,
)
from contexts.portfolio.adapters.outbound.postgres.portfolio_repository import (
    PostgresPortfolioRepository,
)
from contexts.portfolio.application import (
    DataPointNotFoundError,
    create_case,
    create_data_point,
    get_case_detail,
    list_cases,
    revise_data_point,
)
from contexts.portfolio.application.cursor import encode_case_cursor
from contexts.portfolio.domain import CaseStatus, CaseType, DataPointType
from contexts.portfolio.domain.query_filters import CaseListFilters
from padhanam.config import ControlPlaneSettings
from shared_kernel import ActorReference, TenantId

from apps.cli._runtime import build_tenant_wiring

portfolio_app = typer.Typer(
    name="portfolio",
    help="Portfolio context — Case / DataPoint / Assertion (S43 / D124).",
    no_args_is_help=True,
)

_TENANT_OPTION = typer.Option(
    "--tenant-id", help="Tenant short label or UUID."
)
_ACTOR_OPTION = typer.Option(
    "--actor", help="Authoring actor (ActorReference placeholder, D124)."
)


def _build_dependencies(wiring):
    """Construct the portfolio repository, reader, and audit adapter."""
    bound_tenant_id = TenantId(str(wiring.tenant_context.tenant_id))

    async def _resolver(_tid):
        return wiring.session_factory

    repository = PostgresPortfolioRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    reader = PostgresPortfolioReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    audit_adapter = PostgresAuditAdapter.from_settings(
        control_plane_settings=ControlPlaneSettings(),
        per_tenant_sessionmaker_resolver=_resolver,
    )
    return repository, reader, audit_adapter


def _parse_json_value(raw: str) -> dict[str, Any]:
    """Parse a ``--value`` JSON-object argument or exit with code 2."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        typer.echo(f"--value is not valid JSON: {exc}", err=True)
        raise typer.Exit(code=2)
    if not isinstance(parsed, dict):
        typer.echo("--value must be a JSON object", err=True)
        raise typer.Exit(code=2)
    return parsed


@portfolio_app.command("create-case")
def cmd_create_case(
    tenant_id: Annotated[str, _TENANT_OPTION],
    title: Annotated[str, typer.Option("--title", help="Case title.")],
    case_type: Annotated[
        CaseType, typer.Option("--case-type", help="Case type.")
    ] = CaseType.PORTFOLIO_ITEM,
    status: Annotated[
        CaseStatus, typer.Option("--status", help="Initial status.")
    ] = CaseStatus.OPEN,
    actor: Annotated[str, _ACTOR_OPTION] = "operator",
) -> None:
    """Create a portfolio Case."""
    wiring = build_tenant_wiring(tenant_id)
    repository, _reader, audit_adapter = _build_dependencies(wiring)

    async def _go() -> None:
        try:
            case = await create_case(
                tenant_context=wiring.tenant_context,
                repository=repository,
                audit_port=audit_adapter,
                actor=ActorReference(user_id=actor),
                title=title,
                case_type=case_type,
                status=status,
            )
            typer.echo(f"case_id={case.id}")
            typer.echo(f"title={case.title}")
            typer.echo(f"case_type={case.case_type.value}")
            typer.echo(f"status={case.status.value}")
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@portfolio_app.command("create-data-point")
def cmd_create_data_point(
    tenant_id: Annotated[str, _TENANT_OPTION],
    case_id: Annotated[
        UUID, typer.Option("--case-id", help="Parent Case UUID.")
    ],
    data_point_type: Annotated[
        DataPointType,
        typer.Option("--data-point-type", help="DataPoint type."),
    ],
    value: Annotated[
        str, typer.Option("--value", help="DataPoint value as a JSON object.")
    ],
    actor: Annotated[str, _ACTOR_OPTION] = "operator",
) -> None:
    """Create a DataPoint with its INITIAL assertion."""
    parsed = _parse_json_value(value)
    wiring = build_tenant_wiring(tenant_id)
    repository, _reader, audit_adapter = _build_dependencies(wiring)

    async def _go() -> None:
        try:
            data_point = await create_data_point(
                tenant_context=wiring.tenant_context,
                repository=repository,
                audit_port=audit_adapter,
                actor=ActorReference(user_id=actor),
                case_id=case_id,
                data_point_type=data_point_type,
                value=parsed,
            )
            typer.echo(f"data_point_id={data_point.id}")
            typer.echo(f"case_id={data_point.case_id}")
            typer.echo(f"data_point_type={data_point.data_point_type.value}")
            typer.echo(
                f"initial_assertion_id={data_point.assertions[0].id}"
            )
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@portfolio_app.command("revise-data-point")
def cmd_revise_data_point(
    tenant_id: Annotated[str, _TENANT_OPTION],
    data_point_id: Annotated[
        UUID, typer.Option("--data-point-id", help="DataPoint UUID.")
    ],
    value: Annotated[
        str,
        typer.Option("--value", help="New value as a JSON object."),
    ],
    actor: Annotated[str, _ACTOR_OPTION] = "operator",
) -> None:
    """Revise a DataPoint — append a REVISION assertion."""
    parsed = _parse_json_value(value)
    wiring = build_tenant_wiring(tenant_id)
    repository, reader, audit_adapter = _build_dependencies(wiring)

    async def _go() -> None:
        try:
            revised = await revise_data_point(
                tenant_context=wiring.tenant_context,
                repository=repository,
                reader=reader,
                audit_port=audit_adapter,
                actor=ActorReference(user_id=actor),
                data_point_id=data_point_id,
                value=parsed,
            )
            typer.echo(f"data_point_id={revised.id}")
            typer.echo(f"revision_count={len(revised.assertions)}")
            typer.echo(f"latest_assertion_id={revised.assertions[-1].id}")
            typer.echo(f"current_value={revised.current_value}")
        except DataPointNotFoundError:
            typer.echo(
                f"data point {data_point_id} not found", err=True
            )
            raise typer.Exit(code=2)
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@portfolio_app.command("list-cases")
def cmd_list_cases(
    tenant_id: Annotated[str, _TENANT_OPTION],
    case_type: Annotated[
        Optional[CaseType],
        typer.Option("--case-type", help="Filter by case type."),
    ] = None,
    status: Annotated[
        Optional[CaseStatus],
        typer.Option("--status", help="Filter by status."),
    ] = None,
    page_size: Annotated[
        int, typer.Option("--page-size", help="Page size (1-50).")
    ] = 20,
) -> None:
    """List the tenant's cases, newest first."""
    wiring = build_tenant_wiring(tenant_id)
    _repository, reader, audit_adapter = _build_dependencies(wiring)
    filters = CaseListFilters(
        case_types=(case_type,) if case_type is not None else None,
        statuses=(status,) if status is not None else None,
    )

    async def _go() -> None:
        try:
            page = await list_cases(
                tenant_context=wiring.tenant_context,
                reader=reader,
                filters=filters,
                cursor=None,
                page_size=page_size,
            )
            typer.echo(f"cases={len(page.cases)}")
            for case in page.cases:
                typer.echo(
                    f"  {case.id}  [{case.status.value}]  {case.title}"
                )
            if page.next_cursor is not None:
                typer.echo(
                    f"next_cursor={encode_case_cursor(page.next_cursor)}"
                )
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


@portfolio_app.command("get-case")
def cmd_get_case(
    tenant_id: Annotated[str, _TENANT_OPTION],
    case_id: Annotated[
        UUID, typer.Option("--case-id", help="Case UUID to fetch.")
    ],
) -> None:
    """Get a Case with its DataPoints and their current values."""
    wiring = build_tenant_wiring(tenant_id)
    _repository, reader, audit_adapter = _build_dependencies(wiring)

    async def _go() -> None:
        try:
            detail = await get_case_detail(
                tenant_context=wiring.tenant_context,
                reader=reader,
                case_id=case_id,
            )
            if detail is None:
                typer.echo(f"case {case_id} not found", err=True)
                raise typer.Exit(code=2)
            case = detail.case
            typer.echo(f"case_id={case.id}")
            typer.echo(f"title={case.title}")
            typer.echo(f"case_type={case.case_type.value}")
            typer.echo(f"status={case.status.value}")
            typer.echo(f"data_points={len(detail.data_points)}")
            for data_point in detail.data_points:
                typer.echo(
                    f"  {data_point.id}  "
                    f"[{data_point.data_point_type.value}]  "
                    f"revisions={len(data_point.assertions)}  "
                    f"current={data_point.current_value}"
                )
        finally:
            await audit_adapter.dispose()
            await wiring.engine.dispose()

    asyncio.run(_go())


__all__ = ["portfolio_app"]
