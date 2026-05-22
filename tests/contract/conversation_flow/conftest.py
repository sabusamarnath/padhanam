"""Conformance harness for the ConversationFlow Protocol (D115).

``shared_kernel/conversation_flow.py`` declares ``ConversationFlow``
as the cross-context multi-turn-interaction contract.
``@runtime_checkable`` verifies method *names* only; this harness
verifies what it does not — the minimum callable signatures and the
open / turn / close lifecycle semantics the Protocol docstring
commits.

Implementers register via ``register_conversation_flow_implementer()``
at module import. ``test_conversation_flow_contract.py`` carries the
parametrised scenarios; each ``test_<implementer>_conversation_flow.py``
registers one implementer. The ``pytest_generate_tests`` hook below
loads every registration module before parametrising.

No implementer registers at S45 — the audit-conversation (5.1) and
portfolio mirror-conversation (4.1) implementers land at P14. The
registry is empty at S45 and the parametrised scenarios skip; the
harness machinery is in place so a P14 implementer adds a
registration module and needs no harness change.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from shared_kernel.conversation_flow import (
    ConversationClosure,
    ConversationInput,
    ConversationInvocation,
)

_PACKAGE = __name__.rpartition(".")[0]


@dataclass(frozen=True)
class ConversationFlowImplementerFixture:
    """One ConversationFlow implementer registered against the harness.

    - ``name`` — short label for the parametrised test id.
    - ``implementer_cls`` — the class claiming to satisfy ConversationFlow.
    - ``make_instance`` — a zero-argument factory returning a fresh
      implementer instance.
    - ``sample_invocation`` / ``sample_input`` / ``sample_closure`` —
      representative value objects the scenarios pass to open / turn /
      close.
    """

    name: str
    implementer_cls: type
    make_instance: Callable[[], Any]
    sample_invocation: ConversationInvocation
    sample_input: ConversationInput
    sample_closure: ConversationClosure


_REGISTRY: list[ConversationFlowImplementerFixture] = []


def register_conversation_flow_implementer(
    fixture: ConversationFlowImplementerFixture,
) -> None:
    """Register a ConversationFlow implementer; idempotent on ``name``."""
    if any(f.name == fixture.name for f in _REGISTRY):
        return
    _REGISTRY.append(fixture)


def _load_registration_modules() -> None:
    """Import every ``test_*_conversation_flow.py`` in this directory so
    each implementer's module-level registration call runs before the
    contract scenarios parametrise. Imports are cached. At S45 there
    are no registration modules and the registry stays empty."""
    for path in sorted(
        Path(__file__).parent.glob("test_*_conversation_flow.py")
    ):
        importlib.import_module(f"{_PACKAGE}.{path.stem}")


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrise ``conversation_flow_implementer`` over the registered set."""
    if "conversation_flow_implementer" not in metafunc.fixturenames:
        return
    _load_registration_modules()
    metafunc.parametrize(
        "conversation_flow_implementer",
        _REGISTRY,
        ids=[f.name for f in _REGISTRY],
    )
