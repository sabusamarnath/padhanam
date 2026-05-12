"""Tenant-isolation contract tests for the methodology context (D74).

Control-plane-shape inversion of the per-tenant pattern (see README):
methodology data is platform-managed and visible across tenants by
design; mutation requires operator-context. Tenant-context reads
succeed across tenants; tenant-context writes fail with
AuthorizationError; operator-context reads and writes succeed;
tenant_id has no semantic role in the data.

Skip-on-unreachable mirrors the registry isolation test pattern.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from contexts.methodology.adapters.outbound.postgres import (
    MethodologyPostgresRepository,
    methodology_revisions,
    methodology_templates,
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
    MethodologyTemplate,
)
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security import (
    OPERATOR_ROLE,
    AuthorizationError,
    Principal,
)
from shared_kernel import TenantId


TENANT_A_UUID = "00000000-0000-4000-8000-000000000a01"
TENANT_B_UUID = "00000000-0000-4000-8000-000000000b02"


def _operator_principal() -> Principal:
    return Principal(
        subject="system:control_plane",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op",
    )


def _tenant_a_principal() -> Principal:
    return Principal(
        subject="alice",
        tenant_id=TenantId(TENANT_A_UUID),
        roles=frozenset({"audit.read", "audit.write"}),
        credential_ref="dev-token-a",
    )


def _tenant_b_principal() -> Principal:
    return Principal(
        subject="bob",
        tenant_id=TenantId(TENANT_B_UUID),
        roles=frozenset({"audit.read"}),
        credential_ref="dev-token-b",
    )


class _CollectingSecurityEvents:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def _create_kwargs(name: str = "PlatformMethodology", **overrides) -> dict:
    defaults = {
        "name": name,
        "description": "Platform-managed test methodology",
        "role_refs": (
            RoleRef(role_id=uuid4(), role_version=1),
        ),
        "actor_user_id": "operator",
    }
    defaults.update(overrides)
    return defaults


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture
def repo_with_template(
    event_loop: asyncio.AbstractEventLoop,
) -> Iterator[
    tuple[MethodologyPostgresRepository, _CollectingSecurityEvents, MethodologyTemplate]
]:
    base = ControlPlaneSettings()
    settings = ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1"),
        port=int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433")),
    )
    sec = _CollectingSecurityEvents()
    repo = MethodologyPostgresRepository.from_settings(
        settings=settings, security_events=sec
    )

    async def setup() -> MethodologyTemplate:
        async with repo._sessionmaker() as session:
            await session.execute(sa.delete(methodology_revisions))
            await session.execute(sa.delete(methodology_templates))
            await session.commit()
        # Seed one template by the operator so tenant-context reads
        # have something to fetch.
        template, _ = await create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
        sec.events.clear()
        return template

    try:
        seeded_template = event_loop.run_until_complete(setup())
    except Exception as e:
        event_loop.run_until_complete(repo.dispose())
        pytest.skip(f"control-plane Postgres unreachable: {e}")
    try:
        yield repo, sec, seeded_template
    finally:
        async def teardown() -> None:
            async with repo._sessionmaker() as session:
                await session.execute(sa.delete(methodology_revisions))
                await session.execute(sa.delete(methodology_templates))
                await session.commit()
            await repo.dispose()
        event_loop.run_until_complete(teardown())


# ---------------------------------------------------------------------
# Tenant-context reads succeed across tenants (control-plane visibility).
# ---------------------------------------------------------------------


def test_tenant_a_can_read_platform_methodology_template(
    event_loop, repo_with_template,
) -> None:
    repo, sec, template = repo_with_template
    fetched_template, fetched_rev = event_loop.run_until_complete(
        get_methodology_template(
            principal=_tenant_a_principal(),
            repository=repo,
            template_id=template.id,
        )
    )
    assert fetched_template.id == template.id
    assert fetched_rev.version == 1


def test_tenant_b_can_read_platform_methodology_template(
    event_loop, repo_with_template,
) -> None:
    """Tenant B reads the same platform-managed template as tenant A."""
    repo, sec, template = repo_with_template
    fetched_template, _ = event_loop.run_until_complete(
        get_methodology_template(
            principal=_tenant_b_principal(),
            repository=repo,
            template_id=template.id,
        )
    )
    assert fetched_template.id == template.id


def test_tenant_a_can_list_methodology_templates(
    event_loop, repo_with_template,
) -> None:
    repo, _, template = repo_with_template
    listed = event_loop.run_until_complete(
        list_methodology_templates(
            principal=_tenant_a_principal(),
            repository=repo,
        )
    )
    assert any(t.id == template.id for t in listed)


# ---------------------------------------------------------------------
# Tenant-context writes are rejected with AuthorizationError.
# ---------------------------------------------------------------------


def test_tenant_a_cannot_create_methodology_template(
    event_loop, repo_with_template,
) -> None:
    repo, sec, _ = repo_with_template
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            create_methodology_template(
                principal=_tenant_a_principal(),
                repository=repo,
                security_events=sec,
                **_create_kwargs(name="ShouldNotPersist"),
            )
        )
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "methodology.create_template"
        for e in sec.events
    )


def test_tenant_a_cannot_update_methodology_template(
    event_loop, repo_with_template,
) -> None:
    repo, sec, template = repo_with_template
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            update_methodology_template(
                principal=_tenant_a_principal(),
                repository=repo,
                security_events=sec,
                template_id=template.id,
                role_refs=(
                    RoleRef(role_id=uuid4(), role_version=1),
                ),
                actor_user_id="alice",
            )
        )
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "methodology.update_template"
        for e in sec.events
    )


def test_tenant_a_cannot_retire_methodology_template(
    event_loop, repo_with_template,
) -> None:
    repo, sec, template = repo_with_template
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            retire_methodology_template(
                principal=_tenant_a_principal(),
                repository=repo,
                security_events=sec,
                template_id=template.id,
            )
        )
    # Template still active.
    fetched, _ = event_loop.run_until_complete(
        get_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            template_id=template.id,
        )
    )
    assert fetched.archived_at is None
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "methodology.retire_template"
        for e in sec.events
    )


# ---------------------------------------------------------------------
# Operator-context reads and writes succeed.
# ---------------------------------------------------------------------


def test_operator_can_create_update_and_retire_methodology_template(
    event_loop, repo_with_template,
) -> None:
    repo, sec, _ = repo_with_template

    # create
    template, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(name="OperatorTest"),
        )
    )

    # update (creates revision 2)
    rev2 = event_loop.run_until_complete(
        update_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=template.id,
            role_refs=(
                RoleRef(role_id=uuid4(), role_version=2),
            ),
            actor_user_id="operator",
        )
    )
    assert rev2.version == 2

    # retire
    archived = event_loop.run_until_complete(
        retire_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=template.id,
        )
    )
    assert archived.archived_at is not None


# ---------------------------------------------------------------------
# Schema-shape inversion: methodology_revisions has no tenant_id column.
# ---------------------------------------------------------------------


def test_methodology_revisions_table_has_no_tenant_id_column(
    event_loop, repo_with_template,
) -> None:
    """tenant_id has no semantic role in methodology data (D74).

    The per-tenant tables (e.g. tenant_audit, scoring_sheets) carry
    tenant_id either as a CHECK-constrained column or implicit-via-
    placement on the per-tenant DB. The methodology tables on the
    control plane do neither — there is no tenant_id column at all,
    proof that methodology data is tenant-agnostic.
    """
    repo, _, _ = repo_with_template

    async def column_names(table_name: str) -> set[str]:
        async with repo._engine.connect() as conn:
            result = await conn.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :tn"
                ),
                {"tn": table_name},
            )
            return {row[0] for row in result}

    template_cols = event_loop.run_until_complete(column_names("methodology_templates"))
    revision_cols = event_loop.run_until_complete(column_names("methodology_revisions"))
    assert "tenant_id" not in template_cols
    assert "tenant_id" not in revision_cols
