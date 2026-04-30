"""Enforce D19's "no os.getenv outside vadakkan/config/" rule.

import-linter's contracts operate at module level, not attribute level —
we can ban imports of the ``os`` module entirely, but ``os.urandom`` is a
legitimate use in ``vadakkan/security/crypto.py``. Banning ``os`` outright
is too coarse, so D19 is enforced here by AST walking instead. Any new
``os.getenv(...)`` call outside ``vadakkan/config/`` fails this test.

Source-of-truth discovery (S7 housekeeping): the set of directories to
walk is read from the workspace topology (root pyproject.toml plus its
declared members), not from a hardcoded list. Renaming a context
directory updates this discovery automatically because the workspace
manifest is the canonical reference.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests._enforcement._discovery import enforced_source_roots

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_PATH = REPO_ROOT / "vadakkan" / "config"


def _source_files() -> list[Path]:
    return [p for r in enforced_source_roots(REPO_ROOT) for p in r.rglob("*.py")]


def _is_os_getenv(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "getenv"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
    )


def test_no_os_getenv_outside_platform_config() -> None:
    offenders: list[tuple[Path, int]] = []
    for path in _source_files():
        if ALLOWED_PATH in path.parents:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if _is_os_getenv(node):
                offenders.append((path.relative_to(REPO_ROOT), node.lineno))
    assert offenders == [], (
        "os.getenv found outside vadakkan/config/ (D19 violation): " + repr(offenders)
    )
