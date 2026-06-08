"""Contract tests for MethodologyRepositoryPort (D74).

The port carries the contractual statement that methodology data is
control-plane-scoped per D33 and the port methods take no
``TenantContext`` parameter. These tests pin those invariants at the
port-import level. Behaviour-level assertions for the repository are
deferred to the integration tests at S23 commit 7 against the
PostgresMethodologyRepository adapter.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

from contexts.methodology.ports import MethodologyRepositoryPort


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
        for name, member in inspect.getmembers(MethodologyRepositoryPort)
        if callable(member) and not name.startswith("_")
    }
    assert expected == actual


def test_port_methods_take_no_tenant_context_parameter() -> None:
    """D74 invariant: methodology data is control-plane-scoped; port carries no TenantContext."""
    for method_name in (
        "create_template",
        "get_template",
        "list_templates",
        "add_revision",
        "archive_template",
    ):
        method = getattr(MethodologyRepositoryPort, method_name)
        sig = inspect.signature(method)
        for param in sig.parameters.values():
            assert "tenant_context" not in param.name.lower(), (
                f"{method_name} unexpectedly has parameter {param.name!r} "
                f"shaped like TenantContext"
            )
            # Annotation check: defensive against renamed kwargs
            anno = param.annotation
            if anno is not inspect.Parameter.empty:
                assert "TenantContext" not in str(anno), (
                    f"{method_name} parameter {param.name!r} types as "
                    f"{anno!r} which references TenantContext"
                )


def test_port_methods_are_async() -> None:
    """All methods are coroutines (consistent with the tenancy use cases)."""
    for method_name in (
        "create_template",
        "get_template",
        "list_templates",
        "add_revision",
        "archive_template",
    ):
        method = getattr(MethodologyRepositoryPort, method_name)
        assert inspect.iscoroutinefunction(method), (
            f"{method_name} is not declared as async; the methodology "
            f"adapter at commit 7 implements it as a coroutine"
        )


def test_port_import_does_not_pull_in_sqlalchemy_alembic_asyncpg() -> None:
    """Runtime tripwire (D74): port layer is framework-free.

    Importing ``contexts.methodology.ports`` must not transitively
    pull in ``sqlalchemy``, ``alembic``, or ``asyncpg``. The hexagonal
    layer contract requires the port to remain a pure abstraction;
    this test catches accidental adapter leakage at the port layer.
    """
    # Force a clean import of the port module
    for mod_name in list(sys.modules):
        if mod_name.startswith("contexts.methodology.ports"):
            del sys.modules[mod_name]
    # Snapshot vendor-module presence before re-import
    forbidden = {"sqlalchemy", "alembic", "asyncpg"}
    pre_import_present = forbidden & set(sys.modules)

    from contexts.methodology.ports import (
        MethodologyRepositoryPort as _,  # noqa: F401
    )

    # If a forbidden module is now present and was not before, the
    # port import path pulled it in.
    post_import_present = forbidden & set(sys.modules)
    accidentally_pulled_in = post_import_present - pre_import_present
    assert not accidentally_pulled_in, (
        f"contexts.methodology.ports import accidentally pulls in "
        f"{accidentally_pulled_in}; the port layer must stay framework-free"
    )


# ----------------------------------------------------------------------
# Behaviour-level assertions for the PostgresMethodologyRepository live in
# the integration home below. The four placeholders that used to sit here
# as empty `@pytest.mark.skip` tests asserted nothing and pointed at prose
# ("S23 commit 7 integration tests") that could rot silently. S64 replaces
# them with the guard below: it reads the named home and fails if any
# deferred behaviour is renamed or dropped, so the deferral is verified, not
# decorative.
# ----------------------------------------------------------------------

_BEHAVIOUR_HOME = (
    "tests/integration/contexts/methodology/adapters/outbound/postgres/"
    "test_repository.py"
)
_DEFERRED_BEHAVIOURS = (
    "test_create_template_persists_template_and_initial_revision_atomically",
    "test_add_revision_increments_version_and_chains_hash",
    "test_get_template_returns_latest_revision_when_version_omitted",
    "test_archive_template_marks_archived_at_and_leaves_revisions_intact",
)


def test_deferred_behaviour_homes_exist() -> None:
    """The four deferred PostgresMethodologyRepository behaviours have a home (S64).

    Replaces the prior empty skip placeholders. Reads the integration home and
    asserts every deferred behaviour is defined there; a rename or deletion
    fails this test, so the port-contract deferral can never decay into a
    silent gap.
    """
    repo_root = Path(__file__).resolve().parents[5]
    home = repo_root / _BEHAVIOUR_HOME
    assert home.is_file(), f"deferred behaviour home missing: {_BEHAVIOUR_HOME}"
    text = home.read_text()
    missing = [n for n in _DEFERRED_BEHAVIOURS if f"def {n}(" not in text]
    assert not missing, (
        f"{_BEHAVIOUR_HOME} no longer defines deferred behaviours: {missing}"
    )
