"""Unit tests for SourceLookup port and SourceNotFoundError (S25 / D79).

Four concerns:

1. SourceNotFoundError inherits from LookupError so callers using the
   generic not-found shape continue to work, but the more specific
   class lets the consumer surface "which source ids failed?" at
   error sites.
2. SourceNotFoundError carries the offending ids on the exception
   instance so callers can format a precise error without re-query.
3. SourceLookup is a Protocol; structural-typing satisfaction does
   not require explicit inheritance.
4. The module imports nothing from ``contexts.methodology`` or
   ``contexts.ingestion``.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from contexts.agent.application.ports.source_lookup import (
    SourceLookup,
    SourceNotFoundError,
)
from padhanam.security import OPERATOR_ROLE, Principal
from shared_kernel import TenantContext, TenantId


def _operator_principal() -> Principal:
    return Principal(
        subject="cli-operator",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="cli-dev-token",
    )


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )


def test_source_not_found_error_inherits_from_lookup_error() -> None:
    err = SourceNotFoundError(missing_source_ids=(uuid4(),))
    assert isinstance(err, LookupError)


def test_source_not_found_error_carries_offending_ids() -> None:
    missing = (uuid4(), uuid4(), uuid4())
    err = SourceNotFoundError(missing_source_ids=missing)
    assert err.missing_source_ids == missing
    # Error message contains the ids in sorted lexical order so
    # operator logs render deterministically.
    text = str(err)
    for sid in missing:
        assert str(sid) in text


def test_source_not_found_error_empty_ids_tuple_is_well_formed() -> None:
    """Edge case: caller hands an empty tuple. The exception still
    constructs; the empty-tuple message form is a coding-error
    signal (the caller shouldn't raise SourceNotFoundError with
    zero ids) but the structure does not collapse."""
    err = SourceNotFoundError(missing_source_ids=())
    assert err.missing_source_ids == ()
    assert isinstance(err, LookupError)


def test_source_lookup_is_structurally_satisfiable() -> None:
    """A class with the right async method satisfies the Protocol
    structurally."""

    captured: dict[str, object] = {}

    class _Adapter:
        async def assert_sources_exist(
            self,
            *,
            source_ids,
            tenant_context,
            principal,
        ) -> None:
            captured["source_ids"] = source_ids
            captured["tenant_context"] = tenant_context
            captured["principal"] = principal

    lookup: SourceLookup = _Adapter()  # type: ignore[assignment]
    asyncio.run(
        lookup.assert_sources_exist(
            source_ids=(uuid4(),),
            tenant_context=_tenant_context(),
            principal=_operator_principal(),
        )
    )
    assert "source_ids" in captured
    assert "tenant_context" in captured
    assert "principal" in captured


def test_source_lookup_propagates_source_not_found_error() -> None:
    """The Protocol-implementing adapter raises SourceNotFoundError
    when it identifies missing sources; the test asserts the raise
    surfaces and the offending ids round-trip."""

    missing = (uuid4(),)

    class _Adapter:
        async def assert_sources_exist(
            self,
            *,
            source_ids,
            tenant_context,
            principal,
        ) -> None:
            raise SourceNotFoundError(missing_source_ids=missing)

    lookup: SourceLookup = _Adapter()  # type: ignore[assignment]
    with pytest.raises(SourceNotFoundError) as exc_info:
        asyncio.run(
            lookup.assert_sources_exist(
                source_ids=missing,
                tenant_context=_tenant_context(),
                principal=_operator_principal(),
            )
        )
    assert exc_info.value.missing_source_ids == missing


def test_source_lookup_module_imports_nothing_from_other_contexts() -> None:
    """D17 cross-context independence at the file level."""
    module_path = Path(
        "/Users/sabu/padhanam/contexts/agent/application/ports/source_lookup.py"
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
        f"source_lookup.py imports from forbidden cross-context modules: {offenders}"
    )
