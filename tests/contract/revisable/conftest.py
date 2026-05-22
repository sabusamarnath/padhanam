"""Conformance harness for the Revisable Protocol (D114, D125).

``shared_kernel/revisable.py`` declares ``Revisable`` as the
cross-context append-only revision contract. ``@runtime_checkable``
verifies method *names* only; this harness verifies what it does not —
the minimum callable signature, the return type, and the append-only /
ordering / genesis semantics the Protocol docstring commits.

Implementers register via ``register_revisable_implementer()`` at module
import. ``test_revisable_contract.py`` carries the parametrised
scenarios; each ``test_<implementer>_revisable.py`` registers one
implementer. The ``pytest_generate_tests`` hook below loads every
registration module (``test_*_revisable.py`` in this directory) before
parametrising, so the registry is populated regardless of pytest's
file-collection order — a future implementer (P14 methodology-application
revision, a later Case-level revision) adds a registration module and
needs no harness change.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from shared_kernel import AssertionChange

_PACKAGE = __name__.rpartition(".")[0]


@dataclass(frozen=True)
class RevisableImplementerFixture:
    """One Revisable implementer registered against the contract harness.

    - ``name`` — short label for the parametrised test id.
    - ``implementer_cls`` — the class claiming to satisfy Revisable.
    - ``make_instance`` — a zero-argument factory returning a fresh
      instance carrying its genesis revision.
    - ``sample_change`` — a representative AssertionChange the scenarios
      pass to ``revise``.
    """

    name: str
    implementer_cls: type
    make_instance: Callable[[], Any]
    sample_change: AssertionChange


_REGISTRY: list[RevisableImplementerFixture] = []


def register_revisable_implementer(
    fixture: RevisableImplementerFixture,
) -> None:
    """Register a Revisable implementer; idempotent on ``name``."""
    if any(f.name == fixture.name for f in _REGISTRY):
        return
    _REGISTRY.append(fixture)


def _load_registration_modules() -> None:
    """Import every ``test_*_revisable.py`` in this directory so each
    implementer's module-level ``register_revisable_implementer()`` call
    runs before the contract scenarios parametrise. Imports are cached,
    so this is safe to call from the per-function hook below."""
    for path in sorted(Path(__file__).parent.glob("test_*_revisable.py")):
        importlib.import_module(f"{_PACKAGE}.{path.stem}")


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrise ``revisable_implementer`` over the registered set."""
    if "revisable_implementer" not in metafunc.fixturenames:
        return
    _load_registration_modules()
    metafunc.parametrize(
        "revisable_implementer",
        _REGISTRY,
        ids=[f.name for f in _REGISTRY],
    )
