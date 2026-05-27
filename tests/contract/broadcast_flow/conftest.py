"""Conformance harness for the BroadcastFlow Protocol (D142, S53).

``shared_kernel/broadcast_flow.py`` declares ``BroadcastFlow`` as the
cross-context platform-initiated outbound contract.
``@runtime_checkable`` verifies method *names* only; this harness
verifies what it does not — the minimum callable signature plus
``BroadcastResponse`` structural conformance plus tenant-scoping at the
fire boundary.

Implementers register via ``register_broadcast_flow_implementer()`` at
module import. ``test_broadcast_flow_conformance.py`` carries the
parametrised scenarios; each ``test_<implementer>_broadcast_flow.py``
registers one implementer. The ``pytest_generate_tests`` hook below
loads every registration module before parametrising.

No real implementer registers at S53 — daily-briefing lands at S54,
threshold-briefing plus ThresholdEvaluator at S57. The registry is
empty at S53 (or carries only the synthetic harness implementer
registered through ``test_synthetic_broadcast_flow.py``); the
parametrised scenarios skip when the registry is empty. The harness
machinery is in place so a P15+ implementer adds a registration
module and needs no harness change.

Mirrors the S45 ConversationFlow harness pattern at
``tests/contract/conversation_flow/conftest.py``.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from shared_kernel.broadcast_flow import (
    BroadcastTriggerType,
    TriggerContext,
)

_PACKAGE = __name__.rpartition(".")[0]


@dataclass(frozen=True)
class BroadcastFlowImplementerFixture:
    """One BroadcastFlow implementer registered against the harness.

    - ``name`` — short label for the parametrised test id.
    - ``implementer_cls`` — the class claiming to satisfy BroadcastFlow.
    - ``make_instance`` — a zero-argument factory returning a fresh
      implementer instance.
    - ``handled_trigger_type`` — the BroadcastTriggerType the implementer
      registers for (the harness uses this to construct a representative
      TriggerContext at the conformance scenarios).
    - ``sample_trigger_context_factory`` — a callable returning a fresh
      TriggerContext carrying the handled trigger type plus
      implementer-appropriate metadata; the conformance scenarios pass
      the produced context to ``fire``.
    """

    name: str
    implementer_cls: type
    make_instance: Callable[[], Any]
    handled_trigger_type: BroadcastTriggerType
    sample_trigger_context_factory: Callable[[], TriggerContext]


_REGISTRY: list[BroadcastFlowImplementerFixture] = []


def register_broadcast_flow_implementer(
    fixture: BroadcastFlowImplementerFixture,
) -> None:
    """Register a BroadcastFlow implementer; idempotent on ``name``."""
    if any(f.name == fixture.name for f in _REGISTRY):
        return
    _REGISTRY.append(fixture)


def _load_registration_modules() -> None:
    """Import every ``test_*_broadcast_flow.py`` in this directory so
    each implementer's module-level registration call runs before the
    contract scenarios parametrise. Imports are cached. At S53 only
    the synthetic harness implementer registers; S54+ implementers add
    their own registration modules."""
    for path in sorted(
        Path(__file__).parent.glob("test_*_broadcast_flow.py")
    ):
        importlib.import_module(f"{_PACKAGE}.{path.stem}")


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrise ``broadcast_flow_implementer`` over the registered set."""
    if "broadcast_flow_implementer" not in metafunc.fixturenames:
        return
    _load_registration_modules()
    metafunc.parametrize(
        "broadcast_flow_implementer",
        _REGISTRY,
        ids=[f.name for f in _REGISTRY],
    )


__all__ = [
    "BroadcastFlowImplementerFixture",
    "register_broadcast_flow_implementer",
]
