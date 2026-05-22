"""Conformance harness for the StructuredOutputPort Protocol (D130).

``shared_kernel/structured_output.py`` declares ``StructuredOutputPort``
as the cross-cutting LLM-call structured-output abstraction.
``@runtime_checkable`` verifies the method *name* only; this harness
verifies what it does not — that ``generate_structured`` is async and
presents the Protocol's request-in / response-out signature.

The behavioural contract (the response value conforms to the
request's JSON Schema) can only be verified against a live model; it
is a live-tier concern and is out of scope for the default
collection. The structural scenarios here run on every cycle and
auto-check each registered implementer.

Implementers register via ``register_structured_output_implementer()``
at module import. ``test_structured_output_contract.py`` carries the
parametrised scenarios; each ``test_<implementer>_structured_output.py``
registers one implementer. The inference LiteLLM adapter is the first
implementer (S45, D130).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

_PACKAGE = __name__.rpartition(".")[0]


@dataclass(frozen=True)
class StructuredOutputImplementerFixture:
    """One StructuredOutputPort implementer registered against the harness.

    - ``name`` — short label for the parametrised test id.
    - ``implementer_cls`` — the class claiming to satisfy StructuredOutputPort.
    - ``make_instance`` — a zero-argument factory returning a fresh
      implementer instance (construction must not perform I/O).
    """

    name: str
    implementer_cls: type
    make_instance: Callable[[], Any]


_REGISTRY: list[StructuredOutputImplementerFixture] = []


def register_structured_output_implementer(
    fixture: StructuredOutputImplementerFixture,
) -> None:
    """Register a StructuredOutputPort implementer; idempotent on ``name``."""
    if any(f.name == fixture.name for f in _REGISTRY):
        return
    _REGISTRY.append(fixture)


def _load_registration_modules() -> None:
    """Import every ``test_*_structured_output.py`` in this directory so
    each implementer's module-level registration call runs before the
    contract scenarios parametrise. Imports are cached."""
    for path in sorted(
        Path(__file__).parent.glob("test_*_structured_output.py")
    ):
        importlib.import_module(f"{_PACKAGE}.{path.stem}")


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrise ``structured_output_implementer`` over the registered set."""
    if "structured_output_implementer" not in metafunc.fixturenames:
        return
    _load_registration_modules()
    metafunc.parametrize(
        "structured_output_implementer",
        _REGISTRY,
        ids=[f.name for f in _REGISTRY],
    )
