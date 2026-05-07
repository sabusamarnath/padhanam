"""Enforce that the ``neo4j`` driver enters the codebase only at the
``contexts.ingestion.adapters.outbound.neo4j`` wrapper plus the
``ops.migrate_neo4j`` Cypher migration runner per D63.

The wrapper at
``contexts/ingestion/adapters/outbound/neo4j/session.py`` is the
single Cypher-execution surface that auto-binds the tenant_id
predicate; the migration runner is operator tooling that runs
schema-DDL Cypher against the bare driver. Every other module
must reach Neo4j through the wrapper, so missing-predicate Cypher
cannot exist in callable code.

The AST walker complements the import-linter ``neo4j-confined``
contract by catching `from neo4j import ...` and `import neo4j`
patterns at the syntax-tree level, which is more robust against
future contract-config drift than relying on the contract alone
— and it covers ``ops/`` which is not in import-linter's root
package list.

Allowlist:
  - ``contexts/ingestion/adapters/outbound/neo4j/`` — the single
    wrapper module tree.
  - ``ops/migrate_neo4j.py`` — the Phase 3 Cypher migration runner.
  - Tests under ``tests/`` — may import the driver directly to set
    up integration fixtures or to assert wrapper behaviour against
    the real bolt protocol.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


_CHECKED_ROOTS = (
    REPO_ROOT / "apps",
    REPO_ROOT / "contexts",
    REPO_ROOT / "padhanam",
    REPO_ROOT / "ops",
)

_ALLOWED_DIRS = {
    REPO_ROOT / "contexts" / "ingestion" / "adapters" / "outbound" / "neo4j",
}

_ALLOWED_FILES = {
    REPO_ROOT / "ops" / "migrate_neo4j.py",
}


def _imports_neo4j(node: ast.AST) -> bool:
    """True iff ``node`` is an Import or ImportFrom that names the
    ``neo4j`` package or any submodule.
    """
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == "neo4j" or alias.name.startswith("neo4j."):
                return True
        return False
    if isinstance(node, ast.ImportFrom):
        if node.module is None:
            return False
        return node.module == "neo4j" or node.module.startswith("neo4j.")
    return False


def _iter_python_files(root: Path):
    if not root.is_dir():
        return
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _is_allowed(path: Path) -> bool:
    resolved = path.resolve()
    if resolved in _ALLOWED_FILES:
        return True
    return any(allowed in resolved.parents for allowed in _ALLOWED_DIRS)


def test_neo4j_imported_only_from_allowed_locations() -> None:
    offenders: list[tuple[str, int]] = []
    for root in _CHECKED_ROOTS:
        for path in _iter_python_files(root):
            if _is_allowed(path):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if _imports_neo4j(node):
                    offenders.append(
                        (str(path.relative_to(REPO_ROOT)), node.lineno)
                    )
    assert offenders == [], (
        "neo4j driver imported outside the allowed surfaces. The "
        "single Cypher-execution surface is "
        "contexts/ingestion/adapters/outbound/neo4j/ (the "
        "TenantScopedNeo4jSession wrapper plus the GraphRepository "
        "adapter); ops/migrate_neo4j.py is the Phase 3 Cypher "
        "migration runner. Per D63, missing-predicate Cypher cannot "
        "exist in callable code because every Cypher path goes "
        "through the wrapper that auto-binds the tenant_id "
        "predicate. Offenders (file:line): " + repr(offenders)
    )
