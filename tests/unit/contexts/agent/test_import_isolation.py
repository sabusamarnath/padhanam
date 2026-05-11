"""AST-level cross-context isolation test for the agent context (S25 / D79).

Backstop for the two import-linter contracts shipped at commit 9
(agent-no-methodology-internal, agent-no-ingestion-internal). Walks
every Python source file under contexts/agent/{domain,application,ports}
and parses the AST to assert no Import or ImportFrom node references
``contexts.methodology`` or ``contexts.ingestion``. The apps/cli wiring
layer is the legitimate seam per D79; contracts and this test scope
end at the apps/ boundary.

Why both the import-linter contracts AND this AST test: the contracts
cover the static import graph (file-level imports resolved through
import-linter's graph builder); the AST test catches text-level
references inside import statements directly, which makes the
guarantee legible at file granularity without consulting import-linter
output. Symmetric to the AST tests at tests/_enforcement/ that backstop
the platform-wide vendor-confinement contracts.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


_AGENT_INTERNAL_ROOTS = (
    Path("/Users/sabu/padhanam/contexts/agent/domain"),
    Path("/Users/sabu/padhanam/contexts/agent/application"),
    Path("/Users/sabu/padhanam/contexts/agent/ports"),
)

_FORBIDDEN_PREFIXES = (
    "contexts.methodology",
    "contexts.ingestion",
)


def _python_files_under(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _imports_in(path: Path) -> list[str]:
    """Return every module name appearing in Import or ImportFrom AST nodes."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                names.append(node.module)
    return names


def _all_agent_internal_files() -> list[Path]:
    out: list[Path] = []
    for root in _AGENT_INTERNAL_ROOTS:
        out.extend(_python_files_under(root))
    return out


def test_agent_internal_layers_collected_for_isolation_check() -> None:
    """Sanity check: the discovery walk finds non-trivial coverage so
    a future structural change that moves agent code under a different
    path surfaces here rather than silently weakening the guarantee."""
    files = _all_agent_internal_files()
    # Expect at least: agent.py (domain), use_cases.py (application),
    # methodology_lookup.py and source_lookup.py (application/ports),
    # agent_repository.py (ports), plus the __init__.py files.
    assert len(files) >= 6, (
        f"agent internal layer discovery found only {len(files)} files; "
        f"the structural assumption is that domain + application + ports "
        f"together carry at least six modules"
    )


@pytest.mark.parametrize(
    "file_path",
    _all_agent_internal_files(),
    ids=lambda p: str(p.relative_to(Path("/Users/sabu/padhanam"))),
)
def test_agent_internal_module_imports_no_forbidden_cross_context(file_path: Path) -> None:
    """For every internal-layer agent module, the AST parse finds no
    imports from contexts.methodology or contexts.ingestion. D79's
    consumer-side DTO + Protocol-port shape exists to keep these
    cross-context imports out of agent's domain/application/ports
    layers; the apps/cli wiring layer is the legitimate seam."""
    names = _imports_in(file_path)
    offenders = [n for n in names if n.startswith(_FORBIDDEN_PREFIXES)]
    assert offenders == [], (
        f"{file_path} imports from forbidden cross-context modules: {offenders}. "
        f"D79's consumer-side abstractions (MethodologyLookup, SourceLookup) "
        f"exist precisely to keep these out; the apps/cli wiring layer is the "
        f"legitimate seam for cross-context translation."
    )
