"""Unit tests for RoleLookup port and RoleView DTO (S26a-2 / D86).

Three concerns mirror test_methodology_lookup.py:

1. RoleView is a frozen dataclass with the D86-named field set.
2. RoleLookup is a Protocol; structural-typing satisfaction does not
   require explicit subclass inheritance.
3. The module imports nothing from ``contexts.methodology`` or
   ``contexts.ingestion`` — the consumer-side DTO pattern from D79
   extends to the new role port to preserve D17's independence
   contracts; the AST parse surfaces accidental re-export drift
   before import-linter does.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from contexts.agent.application.ports.role_lookup import (
    RoleLookup,
    RoleView,
)
from padhanam.security import OPERATOR_ROLE, Principal
from shared_kernel import TenantId


_D86_FIELD_NAMES = {
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


def test_role_view_is_frozen_dataclass() -> None:
    assert is_dataclass(RoleView)
    view = RoleView(
        role_id=uuid4(),
        role_version=1,
        description="LVT guide",
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


def test_role_view_field_set_matches_d86() -> None:
    actual = {f.name for f in fields(RoleView)}
    assert actual == _D86_FIELD_NAMES, (
        f"RoleView fields drifted from D86: "
        f"unexpected={actual - _D86_FIELD_NAMES}, "
        f"missing={_D86_FIELD_NAMES - actual}"
    )


def test_role_lookup_is_structurally_satisfiable() -> None:
    """Protocol satisfaction is structural; an async callable with the
    right keyword-only signature satisfies the type without explicit
    inheritance."""
    import asyncio

    role_id = uuid4()

    async def fake(
        *,
        role_id,
        version,
        principal,
    ) -> RoleView:
        return RoleView(
            role_id=role_id,
            role_version=version or 1,
            description=None,
            system_prompt="",
            tool_allowlist=(),
            retrieval_strategy={},
            filter_tree={},
            top_k=1,
            min_score=Decimal("0"),
            model_selection="",
        )

    lookup: RoleLookup = fake  # type: ignore[assignment]
    principal = Principal(
        subject="x",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="x",
    )
    view = asyncio.run(lookup(role_id=role_id, version=2, principal=principal))
    assert view.role_id == role_id
    assert view.role_version == 2


def test_role_lookup_module_imports_nothing_from_other_contexts() -> None:
    """D17 cross-context independence at the file level: the role
    lookup module must not import from contexts.methodology or
    contexts.ingestion. AST backstop for the import-linter contract."""
    module_path = Path(
        "/Users/sabu/padhanam/contexts/agent/application/ports/role_lookup.py"
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
        f"role_lookup.py imports from forbidden cross-context modules: {offenders}"
    )


def test_role_view_carries_resolved_version_not_none() -> None:
    """D86 commits the lookup to resolve version=None to the latest
    integer at the adapter layer; the view always carries an int."""
    view = RoleView(
        role_id=uuid4(),
        role_version=4,
        description=None,
        system_prompt="",
        tool_allowlist=(),
        retrieval_strategy={},
        filter_tree={},
        top_k=1,
        min_score=Decimal("0"),
        model_selection="",
    )
    assert isinstance(view.role_version, int)
    assert view.role_version == 4


def test_role_view_description_can_be_none() -> None:
    view = RoleView(
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
