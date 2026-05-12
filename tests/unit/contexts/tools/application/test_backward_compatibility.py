"""Unit tests for the schema-diff backward-compatibility stub (D89, S28b commit 6).

Covers the pass conditions (identical schemas, optional-field
addition, type widening) and the fail conditions (removed fields,
newly-required fields, type narrowing, returns-schema narrowing)
plus the genesis-revision no-predecessor path.
"""

from __future__ import annotations

import pytest

from contexts.tools.application.backward_compatibility import (
    BCOutcome,
    BCResult,
    check_revision_compatibility,
)


_OLD_PARAMS = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "limit": {"type": "integer"},
    },
    "required": ["query"],
}
_OLD_RETURNS = {"type": "string"}


class TestPassCases:
    def test_identical_schemas_pass(self) -> None:
        result = check_revision_compatibility(
            old_parameters=_OLD_PARAMS,
            old_returns=_OLD_RETURNS,
            new_parameters=_OLD_PARAMS,
            new_returns=_OLD_RETURNS,
        )
        assert result.outcome is BCOutcome.PASSED

    def test_added_optional_field_passes(self) -> None:
        new_params = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "filters": {"type": "object"},  # new optional
            },
            "required": ["query"],
        }
        result = check_revision_compatibility(
            old_parameters=_OLD_PARAMS,
            old_returns=_OLD_RETURNS,
            new_parameters=new_params,
            new_returns=_OLD_RETURNS,
        )
        assert result.outcome is BCOutcome.PASSED

    def test_type_widening_passes(self) -> None:
        """``int`` widens to ``[int, null]`` (nullable variant)."""
        new_params = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": ["integer", "null"]},
            },
            "required": ["query"],
        }
        result = check_revision_compatibility(
            old_parameters=_OLD_PARAMS,
            old_returns=_OLD_RETURNS,
            new_parameters=new_params,
            new_returns=_OLD_RETURNS,
        )
        assert result.outcome is BCOutcome.PASSED

    def test_genesis_revision_passes_trivially(self) -> None:
        result = check_revision_compatibility(
            old_parameters=None,
            old_returns=None,
            new_parameters=_OLD_PARAMS,
            new_returns=_OLD_RETURNS,
        )
        assert result.outcome is BCOutcome.PASSED
        assert "genesis" in result.reason.lower()


class TestFailCases:
    def test_removed_field_fails(self) -> None:
        new_params = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        result = check_revision_compatibility(
            old_parameters=_OLD_PARAMS,
            old_returns=_OLD_RETURNS,
            new_parameters=new_params,
            new_returns=_OLD_RETURNS,
        )
        assert result.outcome is BCOutcome.FAILED
        assert "limit" in result.reason
        assert "removed" in result.reason.lower()

    def test_newly_required_field_fails(self) -> None:
        new_params = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "auth_token": {"type": "string"},
            },
            "required": ["query", "auth_token"],
        }
        result = check_revision_compatibility(
            old_parameters=_OLD_PARAMS,
            old_returns=_OLD_RETURNS,
            new_parameters=new_params,
            new_returns=_OLD_RETURNS,
        )
        assert result.outcome is BCOutcome.FAILED
        assert "auth_token" in result.reason

    def test_field_promoted_to_required_fails(self) -> None:
        new_params = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query", "limit"],
        }
        result = check_revision_compatibility(
            old_parameters=_OLD_PARAMS,
            old_returns=_OLD_RETURNS,
            new_parameters=new_params,
            new_returns=_OLD_RETURNS,
        )
        assert result.outcome is BCOutcome.FAILED
        assert "limit" in result.reason

    def test_type_narrowing_fails(self) -> None:
        """Narrowing ``[integer, null]`` back to ``integer`` is a fail."""
        old = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": ["integer", "null"]},
            },
            "required": ["query"],
        }
        new = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        }
        result = check_revision_compatibility(
            old_parameters=old,
            old_returns=_OLD_RETURNS,
            new_parameters=new,
            new_returns=_OLD_RETURNS,
        )
        assert result.outcome is BCOutcome.FAILED
        assert "limit" in result.reason
        assert "narrowed" in result.reason.lower()

    def test_returns_field_removed_fails(self) -> None:
        old_returns = {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "count": {"type": "integer"},
            },
        }
        new_returns = {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
            },
        }
        result = check_revision_compatibility(
            old_parameters=_OLD_PARAMS,
            old_returns=old_returns,
            new_parameters=_OLD_PARAMS,
            new_returns=new_returns,
        )
        assert result.outcome is BCOutcome.FAILED
        assert "returns" in result.reason.lower()


class TestBCResultEncoding:
    def test_to_dict_round_trips(self) -> None:
        r = BCResult(outcome=BCOutcome.PASSED, reason="ok")
        d = r.to_dict()
        assert d == {"outcome": "passed", "reason": "ok"}
        assert BCResult.from_dict(d) == r

    def test_from_dict_empty_yields_synthetic_passed(self) -> None:
        r = BCResult.from_dict({})
        assert r.outcome is BCOutcome.PASSED
        assert r.reason == ""
