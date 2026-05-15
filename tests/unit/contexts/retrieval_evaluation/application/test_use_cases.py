"""Application use-case tests against in-memory fakes."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.application import (
    EmptyDraftError,
    GoldSetNotFoundError,
    NoDraftToFinalizeError,
    append_entry_to_revision,
    create_gold_set,
    finalize_revision,
    get_gold_set,
    list_gold_sets,
)
from contexts.retrieval_evaluation.domain import (
    GENESIS_REVISION_HASH,
    GoldSetRevisionStatus,
    compute_revision_hash,
)
from tests.unit.contexts.retrieval_evaluation.application._fakes import (
    FakeGoldSetReader,
    FakeGoldSetRepository,
    InMemoryGoldSetStore,
)


def _tenant() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-0000-0000-00000000a000",
        jurisdiction="GB",
        cost_attribution_id="cost-attr-1",
    )


def _other_tenant() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-0000-0000-00000000b000",
        jurisdiction="EU",
        cost_attribution_id="cost-attr-2",
    )


def _at(seconds: int) -> datetime:
    return datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc) + timedelta(
        seconds=seconds
    )


def _store_pair() -> tuple[
    InMemoryGoldSetStore, FakeGoldSetRepository, FakeGoldSetReader
]:
    store = InMemoryGoldSetStore()
    return store, FakeGoldSetRepository(store), FakeGoldSetReader(store)


def test_create_gold_set_persists_aggregate_and_initial_draft() -> None:
    _, repo, reader = _store_pair()
    result = asyncio.run(
        create_gold_set(
            tenant_context=_tenant(),
            name="P11 retrieval baseline",
            created_by_user_id="cli-operator",
            repository=repo,
            now=_at(0),
        )
    )
    snapshot = asyncio.run(
        get_gold_set(
            tenant_context=_tenant(),
            gold_set_id=result.gold_set.id,
            reader=reader,
        )
    )
    assert snapshot is not None
    assert snapshot.gold_set.name == "P11 retrieval baseline"
    assert snapshot.current_revision is None
    draft = asyncio.run(
        reader.find_current_draft_revision(
            tenant_context=_tenant(),
            gold_set_id=result.gold_set.id,
        )
    )
    assert draft is not None
    assert draft.revision_number == 1
    assert draft.status is GoldSetRevisionStatus.DRAFT


def test_append_entry_appends_to_initial_draft() -> None:
    _, repo, reader = _store_pair()
    create_result = asyncio.run(
        create_gold_set(
            tenant_context=_tenant(),
            name="baseline",
            created_by_user_id="cli-operator",
            repository=repo,
            now=_at(0),
        )
    )
    chunks = (uuid4(), uuid4())
    append_result = asyncio.run(
        append_entry_to_revision(
            tenant_context=_tenant(),
            gold_set_id=create_result.gold_set.id,
            query="alpha",
            expected_chunk_ids=chunks,
            created_by_user_id="cli-operator",
            reader=reader,
            repository=repo,
            now=_at(10),
        )
    )
    assert append_result.opened_new_draft is False
    assert append_result.entry.entry_index == 0
    assert append_result.entry.expected_chunk_ids == chunks


def test_finalize_revision_computes_hash_and_updates_current_revision() -> None:
    _, repo, reader = _store_pair()
    create_result = asyncio.run(
        create_gold_set(
            tenant_context=_tenant(),
            name="baseline",
            created_by_user_id="cli-operator",
            repository=repo,
            now=_at(0),
        )
    )
    gold_set_id = create_result.gold_set.id
    chunks_a = (uuid4(),)
    chunks_b = (uuid4(), uuid4())
    asyncio.run(
        append_entry_to_revision(
            tenant_context=_tenant(),
            gold_set_id=gold_set_id,
            query="alpha",
            expected_chunk_ids=chunks_a,
            created_by_user_id="cli-operator",
            reader=reader,
            repository=repo,
            now=_at(10),
        )
    )
    asyncio.run(
        append_entry_to_revision(
            tenant_context=_tenant(),
            gold_set_id=gold_set_id,
            query="beta",
            expected_chunk_ids=chunks_b,
            created_by_user_id="cli-operator",
            reader=reader,
            repository=repo,
            now=_at(20),
        )
    )

    result = asyncio.run(
        finalize_revision(
            tenant_context=_tenant(),
            gold_set_id=gold_set_id,
            reader=reader,
            repository=repo,
            now=_at(30),
        )
    )
    assert result.previous_event_hash == GENESIS_REVISION_HASH
    assert result.revision.status is GoldSetRevisionStatus.FINALIZED
    assert result.revision.this_event_hash == result.this_event_hash

    rev_snapshot = asyncio.run(
        reader.get_revision_with_entries(
            tenant_context=_tenant(),
            revision_id=result.revision.id,
        )
    )
    recomputed = compute_revision_hash(
        revision_number=result.revision.revision_number,
        entries=rev_snapshot.entries,
        previous_event_hash=GENESIS_REVISION_HASH,
    )
    assert recomputed == result.this_event_hash

    snapshot = asyncio.run(
        get_gold_set(
            tenant_context=_tenant(),
            gold_set_id=gold_set_id,
            reader=reader,
        )
    )
    assert snapshot is not None
    assert snapshot.current_revision is not None
    assert snapshot.current_revision.id == result.revision.id


def test_append_after_finalize_opens_new_draft() -> None:
    _, repo, reader = _store_pair()
    create_result = asyncio.run(
        create_gold_set(
            tenant_context=_tenant(),
            name="baseline",
            created_by_user_id="cli-operator",
            repository=repo,
            now=_at(0),
        )
    )
    gold_set_id = create_result.gold_set.id
    asyncio.run(
        append_entry_to_revision(
            tenant_context=_tenant(),
            gold_set_id=gold_set_id,
            query="q1",
            expected_chunk_ids=(uuid4(),),
            created_by_user_id="cli-operator",
            reader=reader,
            repository=repo,
            now=_at(10),
        )
    )
    finalized = asyncio.run(
        finalize_revision(
            tenant_context=_tenant(),
            gold_set_id=gold_set_id,
            reader=reader,
            repository=repo,
            now=_at(20),
        )
    )
    second_append = asyncio.run(
        append_entry_to_revision(
            tenant_context=_tenant(),
            gold_set_id=gold_set_id,
            query="q2",
            expected_chunk_ids=(uuid4(), uuid4()),
            created_by_user_id="cli-operator",
            reader=reader,
            repository=repo,
            now=_at(30),
        )
    )
    assert second_append.opened_new_draft is True
    assert second_append.revision.revision_number == 2

    second_finalize = asyncio.run(
        finalize_revision(
            tenant_context=_tenant(),
            gold_set_id=gold_set_id,
            reader=reader,
            repository=repo,
            now=_at(40),
        )
    )
    assert second_finalize.previous_event_hash == finalized.this_event_hash
    assert second_finalize.this_event_hash != finalized.this_event_hash


def test_finalize_on_empty_draft_raises() -> None:
    _, repo, reader = _store_pair()
    create_result = asyncio.run(
        create_gold_set(
            tenant_context=_tenant(),
            name="empty",
            created_by_user_id="cli-operator",
            repository=repo,
            now=_at(0),
        )
    )
    with pytest.raises(EmptyDraftError):
        asyncio.run(
            finalize_revision(
                tenant_context=_tenant(),
                gold_set_id=create_result.gold_set.id,
                reader=reader,
                repository=repo,
                now=_at(10),
            )
        )


def test_finalize_without_draft_raises() -> None:
    _, repo, reader = _store_pair()
    with pytest.raises(NoDraftToFinalizeError):
        asyncio.run(
            finalize_revision(
                tenant_context=_tenant(),
                gold_set_id=uuid4(),
                reader=reader,
                repository=repo,
                now=_at(0),
            )
        )


def test_append_for_missing_gold_set_raises() -> None:
    _, repo, reader = _store_pair()
    with pytest.raises(GoldSetNotFoundError):
        asyncio.run(
            append_entry_to_revision(
                tenant_context=_tenant(),
                gold_set_id=uuid4(),
                query="x",
                expected_chunk_ids=(uuid4(),),
                created_by_user_id="cli-operator",
                reader=reader,
                repository=repo,
                now=_at(0),
            )
        )


def test_cross_tenant_get_returns_none() -> None:
    _, repo, reader = _store_pair()
    create_result = asyncio.run(
        create_gold_set(
            tenant_context=_tenant(),
            name="baseline",
            created_by_user_id="cli-operator",
            repository=repo,
            now=_at(0),
        )
    )
    snapshot = asyncio.run(
        get_gold_set(
            tenant_context=_other_tenant(),
            gold_set_id=create_result.gold_set.id,
            reader=reader,
        )
    )
    assert snapshot is None


def test_list_gold_sets_paginates_and_isolates_by_tenant() -> None:
    _, repo, reader = _store_pair()
    ids: list[UUID] = []
    for i in range(3):
        result = asyncio.run(
            create_gold_set(
                tenant_context=_tenant(),
                name=f"gs-{i}",
                created_by_user_id="cli-operator",
                repository=repo,
                now=_at(i * 10),
            )
        )
        ids.append(result.gold_set.id)
    asyncio.run(
        create_gold_set(
            tenant_context=_other_tenant(),
            name="other-tenant-gs",
            created_by_user_id="cli-operator",
            repository=repo,
            now=_at(100),
        )
    )

    page1, next_cursor = asyncio.run(
        list_gold_sets(
            tenant_context=_tenant(),
            reader=reader,
            encoded_cursor=None,
            page_size=2,
        )
    )
    assert len(page1.gold_sets) == 2
    assert next_cursor is not None
    # Newest first
    assert page1.gold_sets[0].id == ids[2]
    assert page1.gold_sets[1].id == ids[1]

    page2, page2_next = asyncio.run(
        list_gold_sets(
            tenant_context=_tenant(),
            reader=reader,
            encoded_cursor=next_cursor,
            page_size=2,
        )
    )
    assert len(page2.gold_sets) == 1
    assert page2.gold_sets[0].id == ids[0]
    assert page2_next is None
