"""Unit tests for the Case domain entity (D124, S43)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

from contexts.portfolio.domain import Case, CaseStatus, CaseType


def _case(**overrides: Any) -> Case:
    now = datetime.now(timezone.utc)
    base: dict[str, Any] = dict(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        title="Q3 board deck",
        case_type=CaseType.PORTFOLIO_ITEM,
        status=CaseStatus.OPEN,
        created_at=now,
        updated_at=now,
    )
    base.update(overrides)
    return Case(**base)


def test_construction_happy_path() -> None:
    c = _case()
    assert c.case_type is CaseType.PORTFOLIO_ITEM
    assert c.status is CaseStatus.OPEN


def test_is_frozen() -> None:
    c = _case()
    with pytest.raises(FrozenInstanceError):
        c.status = CaseStatus.CLOSED  # type: ignore[misc]


def test_empty_jurisdiction_rejected() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        _case(jurisdiction="")


def test_empty_title_rejected() -> None:
    with pytest.raises(ValueError, match="title"):
        _case(title="   ")


def test_updated_before_created_rejected() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="updated_at"):
        _case(created_at=now, updated_at=now - timedelta(seconds=1))


def test_value_equality() -> None:
    c1 = _case()
    c2 = Case(
        id=c1.id,
        tenant_id=c1.tenant_id,
        jurisdiction=c1.jurisdiction,
        title=c1.title,
        case_type=c1.case_type,
        status=c1.status,
        created_at=c1.created_at,
        updated_at=c1.updated_at,
    )
    assert c1 == c2
    assert hash(c1) == hash(c2)
