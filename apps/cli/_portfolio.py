"""Portfolio CLI orchestration (S43 / D124; S44a / D126; S44b / D127, D128).

One typer sub-app — ``portfolio`` — with five action commands:
create-case, create-data-point, revise-data-point, list-cases,
get-case.

S44b (D127/D128): the three write commands invoke the
intake-canonical orchestrations rather than the standalone portfolio
use cases — every CLI write records an IntakeRecord first. The CLI
synthesises the ActorContext (S44a dual-surface posture) and a
``ManualEntryPayload`` describing the command invocation. The
portfolio side of each orchestration is driven through a CLI-local
``_CliPortfolioWriter`` implementing the intake context's
``PortfolioWriter`` port against the single tenant-bound session
factory (the S40 CLI-inline-wiring-helper precedent).
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

from contexts.intake.adapters.outbound.postgres.intake_repository import (
    PostgresIntakeRepository,
)
from contexts.intake.application import (
    record_intake_and_create_case,
    record_intake_and_create_data_point,
    record_intake_and_revise_data_point,
)
from contexts.intake.application.ports.portfolio_writer import (
    CaseWriteResult,
    DataPointWriteResult,
)
from contexts.intake.domain import ManualEntryPayload
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
from shared_kernel import ActorContext, TenantId
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

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
    "--actor", help="Acting actor id (the CLI synthesises an ActorContext, D126)."
)


class _CliPortfolioWriter:
    """CLI-local PortfolioWriter port implementation (D127, S44b).

    Drives the portfolio use cases against the CLI's single
    tenant-bound repository and reader, translating the returned
    domain aggregates into the intake-owned result DTOs — the same
    contract the apps/api PortfolioWriterAdapter provides, inline
    per the S40 CLI-wiring-helper precedent.
    """

    def __init__(self, *, repository, reader, audit_port) -> None:
        self._repository = repository
        self._reader = reader
        self._audit_port = audit_port

    async def create_case(
        self, *, actor: ActorContext, title: str, intake_id: UUID
    ) -> CaseWriteResult:
        case = await create_case(
            repository=self._repository,
            audit_port=self._audit_port,
            actor=actor,
            title=title,
            intake_id=intake_id,
        )
        return CaseWriteResult(
            case_id=case.id,
            tenant_id=case.tenant_id,
            jurisdiction=case.jurisdiction,
            title=case.title,
            case_type=case.case_type.value,
            status=case.status.value,
            created_at=case.created_at,
            updated_at=case.updated_at,
            intake_id=intake_id,
        )

    async def create_data_point(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        data_point_type: str,
        value: dict[str, Any],
        intake_id: UUID,
    ) -> DataPointWriteResult:
        data_point = await create_data_point(
            repository=self._repository,
            audit_port=self._audit_port,
            actor=actor,
            case_id=case_id,
            data_point_type=DataPointType(data_point_type),
            value=value,
            intake_id=intake_id,
        )
        return _data_point_result(data_point, intake_id)

    async def revise_data_point(
        self,
        *,
        actor: ActorContext,
        data_point_id: UUID,
        value: dict[str, Any],
        intake_id: UUID,
    ) -> DataPointWriteResult:
        data_point = await revise_data_point(
            repository=self._repository,
            reader=self._reader,
            audit_port=self._audit_port,
            actor=actor,
            data_point_id=data_point_id,
            value=value,
            intake_id=intake_id,
        )
        return _data_point_result(data_point, intake_id)


def _data_point_result(data_point, intake_id: UUID) -> DataPointWriteResult:
    return DataPointWriteResult(
        data_point_id=data_point.id,
        case_id=data_point.case_id,
        data_point_type=data_point.data_point_type.value,
        current_value=data_point.current_value,
        assertion_ids=tuple(a.id for a in data_point.assertions),
        intake_id=intake_id,
    )


def _build_dependencies(wiring):
    """Construct the portfolio + intake repositories, reader, audit adapter."""
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
    intake_repository = PostgresIntakeRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    audit_adapter = PostgresAuditAdapter.from_settings(
        control_plane_settings=ControlPlaneSettings(),
        per_tenant_sessionmaker_resolver=_resolver,
    )
    return repository, reader, intake_repository, audit_adapter


def _actor_context(wiring, actor_id: str) -> ActorContext:
    """Synthesise the request-scoped ActorContext for the CLI (D126)."""
    role_list = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=wiring.tenant_context,
        actor_id=actor_id,
        role_list=role_list,
        authorisation_set=authorisations_for_roles(role_list),
    )


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
    actor: Annotated[str, _ACTOR_OPTION] = "operator",
) -> None:
    """Create a portfolio Case via the intake-canonical orchestration."""
    wiring = build_tenant_wiring(tenant_id)
    repo, reader, intake_repo, audit_adapter = _build_dependencies(wiring)
    writer = _CliPortfolioWriter(
        repository=repo, reader=reader, audit_port=audit_adapter
    )

    async def _go() -> None:
        try:
            result = await record_intake_and_create_case(
                intake_repository=intake_repo,
                audit_port=audit_adapter,
                portfolio_writer=writer,
                actor=_actor_context(wiring, actor),
                payload=ManualEntryPayload(raw_text=title),
                title=title,
            )
            typer.echo(f"case_id={result.case_id}")
            typer.echo(f"intake_id={result.intake_id}")
            typer.echo(f"title={result.title}")
            typer.echo(f"status={result.status}")
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
    """Create a DataPoint via the intake-canonical orchestration."""
    parsed = _parse_json_value(value)
    wiring = build_tenant_wiring(tenant_id)
    repo, reader, intake_repo, audit_adapter = _build_dependencies(wiring)
    writer = _CliPortfolioWriter(
        repository=repo, reader=reader, audit_port=audit_adapter
    )

    async def _go() -> None:
        try:
            result = await record_intake_and_create_data_point(
                intake_repository=intake_repo,
                audit_port=audit_adapter,
                portfolio_writer=writer,
                actor=_actor_context(wiring, actor),
                payload=ManualEntryPayload(
                    raw_text=f"create-data-point {data_point_type.value}"
                ),
                case_id=case_id,
                data_point_type=data_point_type.value,
                value=parsed,
            )
            typer.echo(f"data_point_id={result.data_point_id}")
            typer.echo(f"intake_id={result.intake_id}")
            typer.echo(f"data_point_type={result.data_point_type}")
            typer.echo(f"initial_assertion_id={result.assertion_ids[0]}")
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
    """Revise a DataPoint via the intake-canonical orchestration."""
    parsed = _parse_json_value(value)
    wiring = build_tenant_wiring(tenant_id)
    repo, reader, intake_repo, audit_adapter = _build_dependencies(wiring)
    writer = _CliPortfolioWriter(
        repository=repo, reader=reader, audit_port=audit_adapter
    )

    async def _go() -> None:
        try:
            result = await record_intake_and_revise_data_point(
                intake_repository=intake_repo,
                audit_port=audit_adapter,
                portfolio_writer=writer,
                actor=_actor_context(wiring, actor),
                payload=ManualEntryPayload(
                    raw_text=f"revise-data-point {data_point_id}"
                ),
                data_point_id=data_point_id,
                value=parsed,
            )
            typer.echo(f"data_point_id={result.data_point_id}")
            typer.echo(f"intake_id={result.intake_id}")
            typer.echo(f"revision_count={len(result.assertion_ids)}")
            typer.echo(f"latest_assertion_id={result.assertion_ids[-1]}")
            typer.echo(f"current_value={result.current_value}")
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
    actor: Annotated[str, _ACTOR_OPTION] = "operator",
) -> None:
    """List the tenant's cases, newest first."""
    wiring = build_tenant_wiring(tenant_id)
    _repo, reader, _intake_repo, audit_adapter = _build_dependencies(wiring)
    filters = CaseListFilters(
        case_types=(case_type,) if case_type is not None else None,
        statuses=(status,) if status is not None else None,
    )

    async def _go() -> None:
        try:
            page = await list_cases(
                reader=reader,
                actor=_actor_context(wiring, actor),
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
    actor: Annotated[str, _ACTOR_OPTION] = "operator",
) -> None:
    """Get a Case with its DataPoints and their current values."""
    wiring = build_tenant_wiring(tenant_id)
    _repo, reader, _intake_repo, audit_adapter = _build_dependencies(wiring)

    async def _go() -> None:
        try:
            detail = await get_case_detail(
                reader=reader,
                actor=_actor_context(wiring, actor),
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
            typer.echo(f"intake_id={case.intake_id}")
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
