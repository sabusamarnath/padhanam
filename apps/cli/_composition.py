"""CLI composition root per D100.

The CLI mirrors ``apps/api``'s composition discipline: settings are
constructed once at typer-app initialisation (via the
``@app.callback()`` at ``apps/cli/main.py``) and consumed from this
shared module wherever needed. Before D100 the CLI constructed
``ControlPlaneSettings()`` fresh at five named sites
(``_methodology.py``, ``_role.py``, ``_tool.py``, two sites in
``_agent.py``); the per-command construction defeated test-fixture
overrides since environment variable changes set after the fixture
opened did not propagate into the freshly-constructed settings used
by the CliRunner-invoked command. D100 commits the composition-root
pattern as the structurally honest fix.

The active ``CliCompositions`` instance is held at module scope. The
typer callback at ``apps/cli/main.py`` populates it on first
invocation; ``_build_repository`` helpers across the CLI sub-modules
read from ``get_compositions()`` rather than constructing settings
fresh. Integration tests override via ``set_compositions(...)`` in a
fixture; the fixture resets to ``None`` on teardown so subsequent
tests reconstruct defaults.

Test isolation note: pytest runs CliRunner invocations in the same
Python process, so the module-level state is shared across tests in
the same session. The fixture pattern (set + yield + reset) keeps
state strictly scoped to the test that depends on the override.
"""

from __future__ import annotations

from dataclasses import dataclass

from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import (
    SecurityEventLogger,
    file_security_event_logger,
)


@dataclass(frozen=True)
class CliCompositions:
    """Shared cross-command state constructed once per CLI invocation.

    Mirrors ``apps/api/main.py``'s ``AppCompositions`` shape: the
    fields are the seams that test fixtures substitute when overriding
    against loopback Postgres or against a collecting security event
    logger.
    """

    control_plane_settings: ControlPlaneSettings
    security_events: SecurityEventLogger


_active: CliCompositions | None = None


def build_default_compositions() -> CliCompositions:
    """Construct the production-shaped compositions for a CLI run.

    Reads ``ControlPlaneSettings`` from the environment per the
    Pydantic Settings convention (env_prefix ``POSTGRES_CONTROL_PLANE_``)
    and builds the file-backed security event logger. Both are
    cheap to construct; the discipline is to construct ONCE rather
    than per-command.
    """
    return CliCompositions(
        control_plane_settings=ControlPlaneSettings(),
        security_events=file_security_event_logger(),
    )


def get_compositions() -> CliCompositions:
    """Return the active compositions; raise if not yet initialised.

    The typer callback at ``apps/cli/main.py`` guarantees that
    initialisation happens before any command body runs. The runtime
    error here surfaces test setups that bypass the callback.
    """
    if _active is None:
        raise RuntimeError(
            "CLI compositions not initialised; call set_compositions() "
            "or invoke the CLI through the typer app so the @app.callback() "
            "runs first."
        )
    return _active


def set_compositions(compositions: CliCompositions | None) -> None:
    """Replace the active compositions; pass ``None`` to reset.

    Used by the typer callback for first-invocation default
    construction, and by integration test fixtures to override with
    loopback-shaped settings + collecting security events. Tests
    reset to ``None`` on teardown so subsequent tests reconstruct
    defaults via the callback.
    """
    global _active
    _active = compositions
