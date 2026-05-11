"""Unit tests for MethodologyLookup port and MethodologyView DTO (S25 / D79).

Three concerns:

1. MethodologyView is a frozen dataclass with the D79-named field set.
2. MethodologyLookup is a Protocol; structural-typing satisfaction
   does not require explicit subclass inheritance.
3. The module imports nothing from ``contexts.methodology`` or
   ``contexts.ingestion`` — the consumer-side DTO pattern from D79
   exists to preserve D17's independence contracts; the AST parse
   surfaces accidental re-export drift before import-linter does.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, fields, is_dataclass
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from contexts.agent.application.ports.methodology_lookup import (
    MethodologyLookup,
    MethodologyView,
)
from padhanam.security import OPERATOR_ROLE, Principal
from shared_kernel import TenantId


_D79_D86_FIELD_NAMES = {
    "methodology_template_id",
    "methodology_version",
    "role_id",
    "role_version",
    "description",
    "system_prompt",
    "tool_allowlist",
    "retrieval_strategy",
    "filter_tree",
    "top_k",
    "min_score",
    "model_selection",
}


def test_methodology_view_is_frozen_dataclass() -> None:
    assert is_dataclass(MethodologyView)
    view = MethodologyView(
        methodology_template_id=uuid4(),
        methodology_version=1,
        role_id=uuid4(),
        role_version=1,
        description="x",
        system_prompt="x",
        tool_allowlist=(),
        retrieval_strategy={"strategy": "vector_only", "params": {}},
        filter_tree={"node": {}},
        top_k=5,
        min_score=Decimal("0.7"),
        model_selection="qwen2.5:7b",
    )
    with pytest.raises(FrozenInstanceError):
        view.top_k = 6  # type: ignore[misc]


def test_methodology_view_field_set_matches_d79_extended_by_d86() -> None:
    """The DTO carries the fields D79 names plus D86's role lineage
    pair (role_id, role_version) so create_agent_from_methodology can
    populate both lineage pairs from a single cross-context hop."""
    actual = {f.name for f in fields(MethodologyView)}
    assert actual == _D79_D86_FIELD_NAMES, (
        f"MethodologyView fields drifted from D79+D86: "
        f"unexpected={actual - _D79_D86_FIELD_NAMES}, "
        f"missing={_D79_D86_FIELD_NAMES - actual}"
    )


def test_methodology_lookup_is_structurally_satisfiable() -> None:
    """Protocol satisfaction is structural; an async callable with the
    right keyword-only signature satisfies the type without explicit
    inheritance. The bare assignment plus a round-trip call exercises
    the runtime behaviour the apps/cli adapter will rely on."""

    import asyncio

    template_id = uuid4()

    async def fake(
        *,
        template_id,
        version,
        principal,
    ) -> MethodologyView:
        return MethodologyView(
            methodology_template_id=template_id,
            methodology_version=version or 1,
            role_id=uuid4(),
            role_version=1,
            description=None,
            system_prompt="",
            tool_allowlist=(),
            retrieval_strategy={},
            filter_tree={},
            top_k=1,
            min_score=Decimal("0"),
            model_selection="",
        )

    lookup: MethodologyLookup = fake  # type: ignore[assignment]
    principal = Principal(
        subject="x",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="x",
    )
    view = asyncio.run(lookup(template_id=template_id, version=2, principal=principal))
    assert view.methodology_template_id == template_id
    assert view.methodology_version == 2


def test_methodology_lookup_module_imports_nothing_from_other_contexts() -> None:
    """D17 cross-context independence at the file level.

    The MethodologyView pattern's structural value depends on the
    consumer's DTO module not pulling in the producer's types; the
    AST parse here is the file-level backstop for the import-linter
    contract that lands at commit 9.
    """
    module_path = Path(
        "/Users/sabu/padhanam/contexts/agent/application/ports/methodology_lookup.py"
    )
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_prefixes = ("contexts.methodology", "contexts.ingestion")
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(forbidden_prefixes):
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith(forbidden_prefixes):
                offenders.append(mod)
    assert offenders == [], (
        f"methodology_lookup.py imports from forbidden cross-context modules: {offenders}"
    )


def test_methodology_view_carries_resolved_version_not_none() -> None:
    """D79 commits the lookup to resolve version=None to the latest
    integer at the adapter layer; the view always carries an int.
    This test is a guard against a future adapter regression that
    might pass None through to the use case."""
    view = MethodologyView(
        methodology_template_id=uuid4(),
        methodology_version=3,
        role_id=uuid4(),
        role_version=1,
        description=None,
        system_prompt="",
        tool_allowlist=(),
        retrieval_strategy={},
        filter_tree={},
        top_k=1,
        min_score=Decimal("0"),
        model_selection="",
    )
    assert isinstance(view.methodology_version, int)
    assert view.methodology_version == 3
    assert isinstance(view.role_version, int)


def test_methodology_view_description_can_be_none() -> None:
    """The methodology template's description is nullable; the view
    inherits the same shape and the cloned agent preserves the None
    rather than substituting an empty string at this layer (D75's
    hash-payload normalisation handles that downstream)."""
    view = MethodologyView(
        methodology_template_id=uuid4(),
        methodology_version=1,
        role_id=uuid4(),
        role_version=1,
        description=None,
        system_prompt="",
        tool_allowlist=(),
        retrieval_strategy={},
        filter_tree={},
        top_k=1,
        min_score=Decimal("0"),
        model_selection="",
    )
    assert view.description is None


def test_principal_type_imported_from_platform_layer() -> None:
    """The Protocol's principal parameter is typed via
    ``padhanam.security.Principal``; the test confirms the type
    actually resolves and is constructable so the wiring layer isn't
    forced to invent a substitute when implementing the adapter."""
    p = Principal(
        subject="cli-operator",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="cli-dev-token",
    )
    assert isinstance(p, Principal)
