"""Domain value-object tests for gold-set aggregate root and value objects."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.retrieval_evaluation.domain import (
    GoldSet,
    GoldSetEntry,
    GoldSetRevision,
    GoldSetRevisionStatus,
)


_TENANT = UUID("00000000-0000-0000-0000-00000000a000")
_USER = "operator@tenant_a"


def _now() -> datetime:
    return datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)


def _chunk() -> UUID:
    return uuid4()


def test_gold_set_constructs_with_no_current_revision() -> None:
    gold_set = GoldSet(
        id=uuid4(),
        tenant_id=_TENANT,
        jurisdiction="GB",
        name="P11 retrieval baseline",
        created_by_user_id=_USER,
        created_at=_now(),
        current_revision_id=None,
    )
    assert gold_set.current_revision_id is None


def test_gold_set_rejects_empty_jurisdiction() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        GoldSet(
            id=uuid4(),
            tenant_id=_TENANT,
            jurisdiction="   ",
            name="x",
            created_by_user_id=_USER,
            created_at=_now(),
            current_revision_id=None,
        )


def test_gold_set_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="name"):
        GoldSet(
            id=uuid4(),
            tenant_id=_TENANT,
            jurisdiction="GB",
            name="",
            created_by_user_id=_USER,
            created_at=_now(),
            current_revision_id=None,
        )


def test_draft_revision_requires_no_finalization_fields() -> None:
    rev = GoldSetRevision(
        id=uuid4(),
        gold_set_id=uuid4(),
        revision_number=1,
        status=GoldSetRevisionStatus.DRAFT,
        created_by_user_id=_USER,
        created_at=_now(),
        finalized_at=None,
        this_event_hash=None,
        previous_event_hash=None,
    )
    assert not rev.is_finalized


def test_finalized_revision_requires_hash_and_timestamp() -> None:
    with pytest.raises(ValueError, match="this_event_hash"):
        GoldSetRevision(
            id=uuid4(),
            gold_set_id=uuid4(),
            revision_number=1,
            status=GoldSetRevisionStatus.FINALIZED,
            created_by_user_id=_USER,
            created_at=_now(),
            finalized_at=_now(),
            this_event_hash=None,
            previous_event_hash="0" * 64,
        )


def test_draft_revision_rejects_hash_or_finalized_at() -> None:
    with pytest.raises(ValueError, match="finalized_at"):
        GoldSetRevision(
            id=uuid4(),
            gold_set_id=uuid4(),
            revision_number=1,
            status=GoldSetRevisionStatus.DRAFT,
            created_by_user_id=_USER,
            created_at=_now(),
            finalized_at=_now(),
            this_event_hash=None,
            previous_event_hash=None,
        )


def test_revision_number_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="revision_number"):
        GoldSetRevision(
            id=uuid4(),
            gold_set_id=uuid4(),
            revision_number=0,
            status=GoldSetRevisionStatus.DRAFT,
            created_by_user_id=_USER,
            created_at=_now(),
            finalized_at=None,
            this_event_hash=None,
            previous_event_hash=None,
        )


def test_gold_set_entry_constructs_with_chunk_ids() -> None:
    entry = GoldSetEntry(
        id=uuid4(),
        gold_set_revision_id=uuid4(),
        entry_index=0,
        query="what is the cost ceiling for the PM agent?",
        expected_chunk_ids=(_chunk(), _chunk(), _chunk()),
    )
    assert len(entry.expected_chunk_ids) == 3


def test_gold_set_entry_rejects_negative_index() -> None:
    with pytest.raises(ValueError, match="entry_index"):
        GoldSetEntry(
            id=uuid4(),
            gold_set_revision_id=uuid4(),
            entry_index=-1,
            query="x",
            expected_chunk_ids=(_chunk(),),
        )


def test_gold_set_entry_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query"):
        GoldSetEntry(
            id=uuid4(),
            gold_set_revision_id=uuid4(),
            entry_index=0,
            query="   ",
            expected_chunk_ids=(_chunk(),),
        )


def test_gold_set_entry_rejects_empty_chunk_list() -> None:
    with pytest.raises(ValueError, match="expected_chunk_ids"):
        GoldSetEntry(
            id=uuid4(),
            gold_set_revision_id=uuid4(),
            entry_index=0,
            query="x",
            expected_chunk_ids=(),
        )
