"""Unit tests for the RunHistoryReader port surface (D17, D97, S33).

Verifies the read-side Protocol's method signatures and the
``RunListPage`` envelope shape. Also enforces that the port module
imports nothing from forbidden cross-context modules (S22-style
producer-context port location; consumer is a composition surface
at apps/api, not a bounded context).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from contexts.run_history.ports.reader import RunHistoryReader, RunListPage


_PORT_PATH = Path(
    "/Users/sabu/padhanam/contexts/run_history/ports/reader.py"
)


def test_run_history_reader_protocol_exposes_two_methods() -> None:
    """get_run and list_runs_with_filters per D97."""
    methods = {
        name
        for name, _ in inspect.getmembers(RunHistoryReader, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    assert methods == {"get_run", "list_runs_with_filters"}


def test_run_list_page_carries_runs_and_next_cursor() -> None:
    """Envelope shape: tuple of runs plus optional next-page cursor."""
    fields = {f.name for f in RunListPage.__dataclass_fields__.values()}
    assert fields == {"runs", "next_cursor"}


def test_reader_module_imports_no_forbidden_cross_context() -> None:
    """Port lives at producer context per D97; imports from agent,
    ingestion, methodology, tools, etc. are forbidden at the port
    layer per D17."""
    source = _PORT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    legal_prefixes = (
        "contexts.run_history",
        "shared_kernel",
    )
    forbidden_cross_context_prefixes = (
        "contexts.agent",
        "contexts.methodology",
        "contexts.ingestion",
        "contexts.tools",
        "contexts.audit",
        "contexts.inference",
        "contexts.observability",
        "contexts.tenancy",
        "contexts.evaluation",
    )

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(forbidden_cross_context_prefixes):
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith(forbidden_cross_context_prefixes):
                offenders.append(mod)
            elif mod.startswith("contexts.") and not mod.startswith(legal_prefixes):
                offenders.append(mod)

    assert offenders == [], (
        f"contexts/run_history/ports/reader.py imports from forbidden "
        f"cross-context modules: {offenders}"
    )
