"""Discover the set of source directories the AST enforcement walks.

Reads the uv workspace manifest at the repo root rather than hardcoding
paths so renames (S8 lesson) and adding a new bounded context (S7+
pattern) are picked up automatically. This is the pyproject-as-source-
of-truth pattern: configuration values that appear in multiple places
(workspace member list, AST walk roots, future packaging metadata)
flow from one canonical reference.

CLAUDE.md token-discipline note: "Configuration values that appear in
multiple files (...) are discovered from a single source rather than
hardcoded." This module is the single source for "which Python source
trees does enforcement walk."
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

# Always-included roots: cross-cutting platform code, the shared kernel,
# and apps/. These live at the workspace root rather than as members so
# they aren't named in [tool.uv.workspace] but are part of the codebase
# the AST enforcement covers.
_ALWAYS_INCLUDED = ("padhanam", "shared_kernel", "apps")


def enforced_source_roots(repo_root: Path) -> list[Path]:
    """Return absolute paths of every directory the enforcement walks.

    Combines the workspace members declared in ``pyproject.toml`` with
    the always-included cross-cutting directories. Returns only paths
    that exist on disk.
    """
    pyproject = repo_root / "pyproject.toml"
    members: list[str] = []
    if pyproject.exists():
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
        members = (
            data.get("tool", {})
            .get("uv", {})
            .get("workspace", {})
            .get("members", [])
        ) or []

    roots: list[Path] = []
    for name in (*_ALWAYS_INCLUDED, *members):
        path = repo_root / name
        if path.is_dir():
            roots.append(path)
    return roots


if sys.version_info < (3, 11):  # pragma: no cover - tomllib is stdlib from 3.11
    raise RuntimeError(
        "tests/_enforcement/_discovery.py requires Python 3.11+ for tomllib"
    )
