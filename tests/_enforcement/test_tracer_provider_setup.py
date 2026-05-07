"""Enforce that the OTel TracerProvider is constructed only in the
shared ``padhanam.observability.init_tracing`` helper, plus a
narrow allowlist for test files that capture spans in-memory.

The S18 reflection's "third-instance threshold met without lift"
note motivated the S19 commit 7 promotion. This AST test is the
fence that keeps the lift load-bearing: future bare-script
drivers (P11 recommendation engine workers, an HTTP API for
ingestion, any future apps/* member) must import the helper
rather than re-introducing inline TracerProvider setup.

Allowlist:
  - ``padhanam/observability/init_tracing.py`` is the helper itself.
  - ``apps/api/main.py`` retains its ``_configure_tracing`` shim
    that delegates to the helper (kept so tests patching the shim
    keep working). The shim does not construct a TracerProvider
    directly.
  - Tests under ``tests/`` may construct an in-memory
    ``TracerProvider()`` (no exporter) for span-capture
    assertions; the helper is for production-shaped exporters
    only. The walker recognises this pattern by the absence of
    ``add_span_processor(BatchSpanProcessor(OTLPSpanExporter(...)))``
    in the same file, but for clarity the test takes the
    explicit-allowlist approach: any test file that constructs a
    TracerProvider passes by virtue of being under ``tests/``.

What the test catches:
  - A new caller in ``apps/`` or ``contexts/`` that constructs a
    ``TracerProvider`` directly.
  - A new caller in ``ops/`` (operator scripts) that bypasses the
    helper.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


# Production code roots checked by this test. Tests are intentionally
# excluded so test files may construct in-memory TracerProviders for
# span-capture assertions (e.g. the unit test at
# tests/unit/contexts/inference/test_litellm_adapter.py).
_CHECKED_ROOTS = (
    REPO_ROOT / "apps",
    REPO_ROOT / "contexts",
    REPO_ROOT / "padhanam",
    REPO_ROOT / "ops",
)

# The single allowed construction site is the helper itself.
_ALLOWED_FILES = {
    REPO_ROOT / "padhanam" / "observability" / "init_tracing.py",
}


def _constructs_tracer_provider(node: ast.AST) -> bool:
    """True iff ``node`` is a Call whose callable is named
    ``TracerProvider`` (either directly or as ``X.TracerProvider``).
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id == "TracerProvider":
        return True
    if isinstance(func, ast.Attribute) and func.attr == "TracerProvider":
        return True
    return False


def _iter_python_files(root: Path):
    if not root.is_dir():
        return
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def test_tracer_provider_constructed_only_in_init_tracing_helper() -> None:
    offenders: list[tuple[str, int]] = []
    for root in _CHECKED_ROOTS:
        for path in _iter_python_files(root):
            if path.resolve() in _ALLOWED_FILES:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if _constructs_tracer_provider(node):
                    offenders.append(
                        (str(path.relative_to(REPO_ROOT)), node.lineno)
                    )
    assert offenders == [], (
        "TracerProvider() constructed outside the shared helper at "
        "padhanam/observability/init_tracing.py. "
        "S19 commit 7 lifted bare-script TracerProvider setup to a "
        "shared helper after the third-instance threshold met without "
        "lift across S17a/S17b/S18 (per the S18 reflection); future "
        "callers must import init_tracing rather than re-introducing "
        "inline setup. Offenders (file:line): " + repr(offenders)
    )
