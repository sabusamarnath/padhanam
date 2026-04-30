"""Enforce "domain code is pure" at the AST level.

The import-linter ``Domain code is pure`` contract catches static
imports of vendor SDKs. This AST test catches the more subtle pattern:
vendor SDK imports inside function bodies (lazy imports) that
import-linter sees with allow_indirect_imports = false but operators
might add casually as a "we'll just import this here" shortcut. The
AST walker doesn't care whether the import is at module level or
inside a function — it inspects the syntax tree directly.

The list of forbidden vendor names is the same set the import-linter
contract uses, so the two enforcement layers stay aligned.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests._enforcement._discovery import enforced_source_roots

REPO_ROOT = Path(__file__).resolve().parents[2]

# Mirror the import-linter `Domain code is pure` contract's
# forbidden_modules list. Updating either should update both — left as a
# manual coupling because the contract config is INI and not parseable
# without a heavier helper.
_FORBIDDEN_NAMES: frozenset[str] = frozenset({
    "pydantic",
    "pydantic_settings",
    "cryptography",
    "jwt",
    "langfuse",
    "langgraph",
    "langchain",
    "litellm",
    "crewai",
    "openai",
    "anthropic",
    "fastapi",
    "starlette",
    "httpx",
    "sqlalchemy",
})


def _domain_dirs() -> list[Path]:
    return [r / "domain" for r in _context_dirs() if (r / "domain").is_dir()]


def _context_dirs() -> list[Path]:
    """Resolve the contexts/* roots from the workspace manifest."""
    workspace_roots = enforced_source_roots(REPO_ROOT)
    return [r for r in workspace_roots if r.parent == REPO_ROOT / "contexts"]


def _is_forbidden_import(node: ast.AST) -> tuple[bool, str | None]:
    if isinstance(node, ast.Import):
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in _FORBIDDEN_NAMES:
                return True, alias.name
    if isinstance(node, ast.ImportFrom):
        if node.module:
            top = node.module.split(".")[0]
            if top in _FORBIDDEN_NAMES:
                return True, node.module
    return False, None


def test_no_vendor_imports_in_any_context_domain() -> None:
    offenders: list[tuple[Path, int, str]] = []
    for domain_dir in _domain_dirs():
        for path in domain_dir.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                forbidden, name = _is_forbidden_import(node)
                if forbidden and name is not None:
                    offenders.append(
                        (path.relative_to(REPO_ROOT), node.lineno, name)
                    )
    assert offenders == [], (
        "Vendor SDK import found in a context's domain layer "
        "(D16 violation): " + repr(offenders)
    )
