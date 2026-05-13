"""Unit tests for the run-history api.py surface (D17, D95, S31 commit 3).

Per D17, every context exposes one ``api.py`` re-exporting the
public surface other contexts call through. At S31 commit 3 the
surface is the single ``record_run`` use case. AST parse plus
runtime check together enforce the re-export.
"""

from __future__ import annotations

import ast
from pathlib import Path


_API_PATH = Path(
    "/Users/sabu/padhanam/contexts/run_history/api.py"
)


def test_api_re_exports_record_run() -> None:
    """The api facade exposes record_run as a callable attribute."""
    from contexts.run_history import api

    assert hasattr(api, "record_run"), (
        "contexts.run_history.api must re-export record_run per D17"
    )
    assert callable(api.record_run)


def test_api_module_lists_record_run_in_all() -> None:
    """``__all__`` lists record_run so star-import consumers see it."""
    from contexts.run_history import api

    assert "record_run" in api.__all__, (
        f"record_run missing from contexts.run_history.api.__all__: {api.__all__!r}"
    )


def test_api_imports_only_from_own_context() -> None:
    """D17 api-facade-via-callable pattern: api.py imports only
    from its own context's application layer (the legitimate
    facade-internal edge). Cross-context imports at the api layer
    are forbidden; the AST parse backstops the import-linter
    contract.
    """
    source = _API_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    legal_prefixes = (
        "contexts.run_history",  # own context's application/domain re-exports
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
            elif mod.startswith("contexts.") and not mod.startswith(
                legal_prefixes
            ):
                offenders.append(mod)

    assert offenders == [], (
        f"contexts/run_history/api.py imports from forbidden cross-context "
        f"modules: {offenders}"
    )
