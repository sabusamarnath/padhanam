"""Forbid plaintext credentials as instance state in tenancy adapters
(D34 control (b)).

The structural rule that justifies envelope encryption is that
plaintext lives only in function-local variables — never in instance
state, never in module globals, never in container references that
outlive the function call. A plaintext value object held in
``self._connection_config`` is precisely the regression this test is
designed to catch.

Mechanism: walk every Python source file under
``contexts/tenancy/adapters/`` via AST. For each ``ClassDef``, inspect
class-level annotated assignments (``ann_assign``) and ``__init__``
``self.X: T = ...`` patterns. Fail if any annotation names
``TenantConnectionConfig`` (the canonical plaintext value object) by
unqualified or qualified name.

The enforcement source roots come from ``_discovery.py`` — the
workspace-manifest-driven helper that already powers
``test_no_getenv.py`` and ``test_no_vendor_in_domain.py``. Renames
update walk roots automatically (S7+S8 lesson).

Future plaintext value objects: when a new ``Plaintext*`` value
object enters the codebase under a context with adapters, this test's
``_FORBIDDEN_TYPE_NAMES`` set should grow to include it. The trigger:
the moment a plaintext-bearing value object enters
``contexts/<X>/domain/`` and a write path exists in any
``contexts/<X>/adapters/`` module, this AST test gains the type name.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests._enforcement._discovery import enforced_source_roots

REPO_ROOT = Path(__file__).resolve().parents[2]


# Canonical plaintext value objects that must never persist as
# instance state in any tenancy adapter. New plaintext types added in
# future contexts must be added here at the same time as their write
# path lands.
_FORBIDDEN_TYPE_NAMES: frozenset[str] = frozenset({"TenantConnectionConfig"})


def _adapter_dirs() -> list[Path]:
    """Resolve `contexts/<context>/adapters/` directories from the
    workspace manifest. Tenancy is the only adapter tree this test
    cares about today; future plaintext-bearing contexts will also
    surface here automatically."""
    workspace_roots = enforced_source_roots(REPO_ROOT)
    adapter_dirs = []
    for r in workspace_roots:
        if r.parent != REPO_ROOT / "contexts":
            continue
        adapters = r / "adapters"
        if adapters.is_dir():
            adapter_dirs.append(adapters)
    return adapter_dirs


def _annotation_name(node: ast.AST) -> str | None:
    """Best-effort extraction of an annotation's referenced type name.

    Handles:
      - bare names: ``TenantConnectionConfig``
      - dotted attributes: ``contexts.tenancy.domain.TenantConnectionConfig``
      - Optional/Union wrappers: ``T | None``, ``Optional[T]``
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _annotation_name(node.slice)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        # ``T | None`` — left or right may carry the offender.
        for child in (node.left, node.right):
            n = _annotation_name(child)
            if n in _FORBIDDEN_TYPE_NAMES:
                return n
        return None
    return None


def _class_offenders(cls: ast.ClassDef) -> list[tuple[int, str]]:
    """Return (lineno, name) pairs for any plaintext-typed instance attribute."""
    offenders: list[tuple[int, str]] = []

    # Class-level: `attr: T` annotations directly under the class.
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            name = _annotation_name(stmt.annotation)
            if name in _FORBIDDEN_TYPE_NAMES:
                offenders.append((stmt.lineno, name))

    # __init__: `self.attr: T = ...` annotated assignments.
    for stmt in cls.body:
        if isinstance(stmt, ast.FunctionDef) and stmt.name == "__init__":
            for inner in ast.walk(stmt):
                if (
                    isinstance(inner, ast.AnnAssign)
                    and isinstance(inner.target, ast.Attribute)
                    and isinstance(inner.target.value, ast.Name)
                    and inner.target.value.id == "self"
                ):
                    name = _annotation_name(inner.annotation)
                    if name in _FORBIDDEN_TYPE_NAMES:
                        offenders.append((inner.lineno, name))
        if isinstance(stmt, ast.AsyncFunctionDef) and stmt.name == "__init__":
            for inner in ast.walk(stmt):
                if (
                    isinstance(inner, ast.AnnAssign)
                    and isinstance(inner.target, ast.Attribute)
                    and isinstance(inner.target.value, ast.Name)
                    and inner.target.value.id == "self"
                ):
                    name = _annotation_name(inner.annotation)
                    if name in _FORBIDDEN_TYPE_NAMES:
                        offenders.append((inner.lineno, name))
    return offenders


def test_no_plaintext_credential_typed_instance_state() -> None:
    offenders: list[tuple[Path, int, str, str]] = []
    for adapters_dir in _adapter_dirs():
        for path in adapters_dir.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for lineno, name in _class_offenders(node):
                        offenders.append(
                            (path.relative_to(REPO_ROOT), lineno, node.name, name)
                        )
    assert offenders == [], (
        "Plaintext credential value object found in adapter instance state "
        "(D34 control (b) violation): " + repr(offenders)
    )
