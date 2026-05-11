"""Contract tests for RoleRepositoryPort (D86).

Mirrors the MethodologyRepositoryPort contract test exactly. The
role port carries the contractual statement that role data is
control-plane-scoped per D33 and the port methods take no
``TenantContext`` parameter. Behaviour-level assertions for the
repository live in the integration tests against the
PostgresRoleRepository adapter.
"""

from __future__ import annotations

import inspect
import sys

import pytest

from contexts.methodology.ports import RoleRepositoryPort


def test_port_is_a_protocol_with_five_methods() -> None:
    """The port shape: create_template, get_template, list_templates, add_revision, archive_template."""
    expected = {
        "create_template",
        "get_template",
        "list_templates",
        "add_revision",
        "archive_template",
    }
    actual = {
        name
        for name, member in inspect.getmembers(RoleRepositoryPort)
        if callable(member) and not name.startswith("_")
    }
    assert expected == actual


def test_port_methods_take_no_tenant_context_parameter() -> None:
    """D86 invariant: role data is control-plane-scoped; port carries no TenantContext."""
    for method_name in (
        "create_template",
        "get_template",
        "list_templates",
        "add_revision",
        "archive_template",
    ):
        method = getattr(RoleRepositoryPort, method_name)
        sig = inspect.signature(method)
        for param in sig.parameters.values():
            assert "tenant_context" not in param.name.lower(), (
                f"{method_name} unexpectedly has parameter {param.name!r} "
                f"shaped like TenantContext"
            )
            anno = param.annotation
            if anno is not inspect.Parameter.empty:
                assert "TenantContext" not in str(anno), (
                    f"{method_name} parameter {param.name!r} types as "
                    f"{anno!r} which references TenantContext"
                )


def test_port_methods_are_async() -> None:
    """All methods are coroutines (consistent with the methodology port)."""
    for method_name in (
        "create_template",
        "get_template",
        "list_templates",
        "add_revision",
        "archive_template",
    ):
        method = getattr(RoleRepositoryPort, method_name)
        assert inspect.iscoroutinefunction(method), (
            f"{method_name} is not declared as async; the role "
            f"adapter implements it as a coroutine"
        )


def test_port_import_does_not_pull_in_sqlalchemy_alembic_asyncpg() -> None:
    """Runtime tripwire (D74/D86): port layer is framework-free."""
    for mod_name in list(sys.modules):
        if mod_name.startswith("contexts.methodology.ports"):
            del sys.modules[mod_name]
    forbidden = {"sqlalchemy", "alembic", "asyncpg"}
    pre_import_present = forbidden & set(sys.modules)

    from contexts.methodology.ports import RoleRepositoryPort as _  # noqa: F401

    post_import_present = forbidden & set(sys.modules)
    accidentally_pulled_in = post_import_present - pre_import_present
    assert not accidentally_pulled_in, (
        f"contexts.methodology.ports import accidentally pulls in "
        f"{accidentally_pulled_in}; the port layer must stay framework-free"
    )


@pytest.mark.skip(reason="behaviour assertion lives in role integration tests")
def test_create_template_persists_template_and_initial_revision_atomically() -> None: ...


@pytest.mark.skip(reason="behaviour assertion lives in role integration tests")
def test_add_revision_increments_version_and_chains_hash() -> None: ...


@pytest.mark.skip(reason="behaviour assertion lives in role integration tests")
def test_get_template_returns_latest_revision_when_version_omitted() -> None: ...


@pytest.mark.skip(reason="behaviour assertion lives in role integration tests")
def test_archive_template_marks_archived_at_and_leaves_revisions_intact() -> None: ...
