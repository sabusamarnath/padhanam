"""Runner-orchestration tests against in-memory fakes (D110, S40)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Mapping
from uuid import UUID, uuid4

import pytest

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.application import (
    EXECUTING_STRATEGIES,
    GRAPH_ONLY,
    VECTOR_ONLY,
    GoldSetMissingFinalizedRevisionError,
    GoldSetNotFoundError,
    create_gold_set,
    finalize_revision,
    get_evaluation_run,
    list_evaluation_runs,
    run_retrieval_evaluation,
    to_adapter_dispatch,
)
from contexts.retrieval_evaluation.application.audit_events import (
    ACTION_AGGREGATE_APPEND,
    ACTION_RESULT_APPEND,
    ACTION_RUN_COMPLETE,
    ACTION_RUN_FAIL,
    ACTION_RUN_START,
    RESOURCE_TYPE_AGGREGATE,
    RESOURCE_TYPE_RESULT,
    RESOURCE_TYPE_RUN,
)
from contexts.retrieval_evaluation.application.cursor import (
    decode_run_cursor,
    encode_run_cursor,
)
from contexts.retrieval_evaluation.domain import (
    BinaryRelevanceMetrics,
    EvaluationRunStatus,
)
from contexts.retrieval_evaluation.domain.query_filters import (
    EvaluationRunListCursor,
    MalformedCursorError,
)
from contexts.retrieval_evaluation.ports.retrieval_runner import RankedChunks
from tests.unit.contexts.retrieval_evaluation.application._fakes import (
    FakeEvaluationRunReader,
    FakeEvaluationRunRepository,
    FakeGoldSetReader,
    FakeGoldSetRepository,
    FakeRetrievalRunner,
    InMemoryEvaluationRunStore,
    InMemoryGoldSetStore,
    RecordingAuditPort,
)
from contexts.retrieval_evaluation.application.append_entry_to_revision import (
    append_entry_to_revision,
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


def _seed_finalized_gold_set(
    *,
    tenant: TenantContext,
    queries_with_expected: list[tuple[str, tuple[UUID, ...]]],
) -> tuple[UUID, FakeGoldSetReader, InMemoryGoldSetStore]:
    """Build a finalized gold-set with the given entries; return id + reader."""
    store = InMemoryGoldSetStore()
    repo = FakeGoldSetRepository(store)
    reader = FakeGoldSetReader(store)
    created = asyncio.run(
        create_gold_set(
            tenant_context=tenant,
            name=f"baseline-{uuid4().hex[:8]}",
            created_by_user_id="cli-operator",
            repository=repo,
            now=_at(0),
        )
    )
    for offset, (query, expected) in enumerate(queries_with_expected, start=1):
        asyncio.run(
            append_entry_to_revision(
                tenant_context=tenant,
                gold_set_id=created.gold_set.id,
                query=query,
                expected_chunk_ids=expected,
                created_by_user_id="cli-operator",
                reader=reader,
                repository=repo,
                now=_at(offset),
            )
        )
    asyncio.run(
        finalize_revision(
            tenant_context=tenant,
            gold_set_id=created.gold_set.id,
            reader=reader,
            repository=repo,
            now=_at(100),
        )
    )
    return created.gold_set.id, reader, store


def _runner_responses(
    queries_with_expected: list[tuple[str, tuple[UUID, ...]]],
) -> dict[tuple[str, frozenset], RankedChunks]:
    """One response per (query × strategy) pair; vector returns expected
    in-order, graph returns expected reversed for some signal contrast."""
    responses: dict[tuple[str, frozenset], RankedChunks] = {}
    for offset, (query, expected) in enumerate(queries_with_expected, start=1):
        for strategy in EXECUTING_STRATEGIES:
            dispatch = to_adapter_dispatch(strategy)
            key = (query, frozenset(dispatch.items()))
            chunk_ids = expected if strategy == VECTOR_ONLY else tuple(reversed(expected))
            responses[key] = RankedChunks(
                chunk_ids=chunk_ids,
                latency_ms=10 * offset + (1 if strategy == GRAPH_ONLY else 0),
            )
    return responses


# ----------------------------------------------------------------------
# strategy_keys
# ----------------------------------------------------------------------


def test_executing_strategies_carries_vector_and_graph_only() -> None:
    assert EXECUTING_STRATEGIES == (VECTOR_ONLY, GRAPH_ONLY)
    assert "parallel_rrf" not in EXECUTING_STRATEGIES


def test_to_adapter_dispatch_projects_vector_only() -> None:
    assert to_adapter_dispatch(VECTOR_ONLY) == {"primary": "vector"}


def test_to_adapter_dispatch_projects_graph_only() -> None:
    assert to_adapter_dispatch(GRAPH_ONLY) == {"primary": "graph"}


def test_to_adapter_dispatch_returns_fresh_mapping_per_call() -> None:
    a = to_adapter_dispatch(VECTOR_ONLY)
    b = to_adapter_dispatch(VECTOR_ONLY)
    a["primary"] = "mutated"
    assert b == {"primary": "vector"}


def test_to_adapter_dispatch_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError, match="parallel_rrf"):
        to_adapter_dispatch("parallel_rrf")
    with pytest.raises(ValueError):
        to_adapter_dispatch("bogus")


# ----------------------------------------------------------------------
# cursor codec
# ----------------------------------------------------------------------


def test_evaluation_run_cursor_codec_round_trip() -> None:
    original = EvaluationRunListCursor(
        invoked_at=_at(0), id=uuid4(), page_size=20
    )
    encoded = encode_run_cursor(original)
    decoded = decode_run_cursor(encoded)
    assert decoded == original


def test_evaluation_run_cursor_decode_malformed_base64_raises() -> None:
    with pytest.raises(MalformedCursorError):
        decode_run_cursor("not!!base64!!")


def test_evaluation_run_cursor_decode_missing_field_raises() -> None:
    # base64 of a JSON object missing 'invoked_at'
    import base64
    import json

    payload = json.dumps({"id": str(uuid4()), "page_size": 20}).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii")
    with pytest.raises(MalformedCursorError, match="invoked_at"):
        decode_run_cursor(encoded)


# ----------------------------------------------------------------------
# run_retrieval_evaluation
# ----------------------------------------------------------------------


def test_run_retrieval_evaluation_persists_run_results_and_aggregates() -> None:
    expected_q1 = (uuid4(), uuid4(), uuid4())
    expected_q2 = (uuid4(), uuid4())
    queries = [("q1", expected_q1), ("q2", expected_q2)]
    gs_id, gs_reader, _ = _seed_finalized_gold_set(
        tenant=_tenant(), queries_with_expected=queries
    )
    run_store = InMemoryEvaluationRunStore()
    repo = FakeEvaluationRunRepository(run_store)
    runner = FakeRetrievalRunner(responses=_runner_responses(queries))
    audit = RecordingAuditPort()

    result = asyncio.run(
        run_retrieval_evaluation(
            tenant_context=_tenant(),
            gold_set_id=gs_id,
            invoked_by_user_id="cli-operator",
            reader=gs_reader,
            repository=repo,
            retrieval_runner=runner,
            audit_port=audit,
            metric_calculator=BinaryRelevanceMetrics(),
        )
    )

    assert result.run.status is EvaluationRunStatus.COMPLETED
    assert result.run.completed_at is not None
    # 2 queries × 2 strategies = 4 per-query results
    assert len(result.results) == 4
    # 1 aggregate per executing strategy
    assert len(result.aggregates) == 2
    aggregate_strategies = {a.retrieval_strategy for a in result.aggregates}
    assert aggregate_strategies == set(EXECUTING_STRATEGIES)


def test_run_retrieval_evaluation_emits_audit_event_for_every_write() -> None:
    expected = (uuid4(),)
    queries = [("q1", expected)]
    gs_id, gs_reader, _ = _seed_finalized_gold_set(
        tenant=_tenant(), queries_with_expected=queries
    )
    repo = FakeEvaluationRunRepository(InMemoryEvaluationRunStore())
    audit = RecordingAuditPort()
    asyncio.run(
        run_retrieval_evaluation(
            tenant_context=_tenant(),
            gold_set_id=gs_id,
            invoked_by_user_id="cli-operator",
            reader=gs_reader,
            repository=repo,
            retrieval_runner=FakeRetrievalRunner(
                responses=_runner_responses(queries)
            ),
            audit_port=audit,
            metric_calculator=BinaryRelevanceMetrics(),
        )
    )

    # 1 run.start + 1 result × 2 strategies + 1 aggregate × 2 strategies
    # + 1 run.complete = 6 events
    assert len(audit.events) == 6

    actions = [e.action_verb for e in audit.events]
    assert actions[0] == ACTION_RUN_START
    assert actions[-1] == ACTION_RUN_COMPLETE
    assert actions.count(ACTION_RESULT_APPEND) == 2
    assert actions.count(ACTION_AGGREGATE_APPEND) == 2

    resource_types = {e.resource_type for e in audit.events}
    assert resource_types == {
        RESOURCE_TYPE_RUN,
        RESOURCE_TYPE_RESULT,
        RESOURCE_TYPE_AGGREGATE,
    }


def test_run_retrieval_evaluation_marks_failed_on_runner_exception() -> None:
    expected = (uuid4(),)
    queries = [("q1", expected)]
    gs_id, gs_reader, _ = _seed_finalized_gold_set(
        tenant=_tenant(), queries_with_expected=queries
    )
    run_store = InMemoryEvaluationRunStore()
    repo = FakeEvaluationRunRepository(run_store)
    audit = RecordingAuditPort()
    runner = FakeRetrievalRunner(always_raises=RuntimeError("retrieval blew up"))

    with pytest.raises(RuntimeError, match="retrieval blew up"):
        asyncio.run(
            run_retrieval_evaluation(
                tenant_context=_tenant(),
                gold_set_id=gs_id,
                invoked_by_user_id="cli-operator",
                reader=gs_reader,
                repository=repo,
                retrieval_runner=runner,
                audit_port=audit,
                metric_calculator=BinaryRelevanceMetrics(),
            )
        )

    # Run exists, transitioned to failed
    stored_runs = list(run_store.runs.values())
    assert len(stored_runs) == 1
    assert stored_runs[0].status is EvaluationRunStatus.FAILED
    assert stored_runs[0].completed_at is not None

    # Two audit events: run.start + run.fail
    actions = [e.action_verb for e in audit.events]
    assert actions == [ACTION_RUN_START, ACTION_RUN_FAIL]


def test_run_retrieval_evaluation_gold_set_not_found_raises() -> None:
    repo = FakeEvaluationRunRepository(InMemoryEvaluationRunStore())
    gs_reader = FakeGoldSetReader(InMemoryGoldSetStore())

    with pytest.raises(GoldSetNotFoundError):
        asyncio.run(
            run_retrieval_evaluation(
                tenant_context=_tenant(),
                gold_set_id=uuid4(),
                invoked_by_user_id="cli-operator",
                reader=gs_reader,
                repository=repo,
                retrieval_runner=FakeRetrievalRunner(),
                audit_port=RecordingAuditPort(),
                metric_calculator=BinaryRelevanceMetrics(),
            )
        )


def test_run_retrieval_evaluation_no_finalized_revision_raises() -> None:
    # Create a gold-set but do NOT finalize.
    store = InMemoryGoldSetStore()
    gs_repo = FakeGoldSetRepository(store)
    gs_reader = FakeGoldSetReader(store)
    created = asyncio.run(
        create_gold_set(
            tenant_context=_tenant(),
            name="never-finalized",
            created_by_user_id="cli-operator",
            repository=gs_repo,
            now=_at(0),
        )
    )

    with pytest.raises(GoldSetMissingFinalizedRevisionError):
        asyncio.run(
            run_retrieval_evaluation(
                tenant_context=_tenant(),
                gold_set_id=created.gold_set.id,
                invoked_by_user_id="cli-operator",
                reader=gs_reader,
                repository=FakeEvaluationRunRepository(
                    InMemoryEvaluationRunStore()
                ),
                retrieval_runner=FakeRetrievalRunner(),
                audit_port=RecordingAuditPort(),
                metric_calculator=BinaryRelevanceMetrics(),
            )
        )


def test_run_retrieval_evaluation_cross_tenant_gold_set_raises() -> None:
    expected = (uuid4(),)
    queries = [("q1", expected)]
    gs_id, gs_reader, _ = _seed_finalized_gold_set(
        tenant=_tenant(), queries_with_expected=queries
    )
    # Invoke as the other tenant: the GoldSetReader returns None.
    with pytest.raises(GoldSetNotFoundError):
        asyncio.run(
            run_retrieval_evaluation(
                tenant_context=_other_tenant(),
                gold_set_id=gs_id,
                invoked_by_user_id="cli-operator",
                reader=gs_reader,
                repository=FakeEvaluationRunRepository(
                    InMemoryEvaluationRunStore()
                ),
                retrieval_runner=FakeRetrievalRunner(),
                audit_port=RecordingAuditPort(),
                metric_calculator=BinaryRelevanceMetrics(),
            )
        )


def test_run_retrieval_evaluation_dispatches_every_executing_strategy() -> None:
    expected = (uuid4(), uuid4())
    queries = [("q1", expected)]
    gs_id, gs_reader, _ = _seed_finalized_gold_set(
        tenant=_tenant(), queries_with_expected=queries
    )
    runner = FakeRetrievalRunner(responses=_runner_responses(queries))
    asyncio.run(
        run_retrieval_evaluation(
            tenant_context=_tenant(),
            gold_set_id=gs_id,
            invoked_by_user_id="cli-operator",
            reader=gs_reader,
            repository=FakeEvaluationRunRepository(InMemoryEvaluationRunStore()),
            retrieval_runner=runner,
            audit_port=RecordingAuditPort(),
            metric_calculator=BinaryRelevanceMetrics(),
        )
    )

    # Runner invoked once per (entry × executing strategy)
    assert len(runner.invocations) == 1 * len(EXECUTING_STRATEGIES)
    dispatches = {frozenset(d.items()) for _, d, _ in runner.invocations}
    expected_dispatches = {
        frozenset(to_adapter_dispatch(s).items()) for s in EXECUTING_STRATEGIES
    }
    assert dispatches == expected_dispatches


# ----------------------------------------------------------------------
# get_evaluation_run / list_evaluation_runs
# ----------------------------------------------------------------------


def test_get_evaluation_run_returns_snapshot_with_results_and_aggregates() -> None:
    expected = (uuid4(),)
    queries = [("q1", expected)]
    gs_id, gs_reader, _ = _seed_finalized_gold_set(
        tenant=_tenant(), queries_with_expected=queries
    )
    run_store = InMemoryEvaluationRunStore()
    repo = FakeEvaluationRunRepository(run_store)
    run_reader = FakeEvaluationRunReader(run_store)
    runner_result = asyncio.run(
        run_retrieval_evaluation(
            tenant_context=_tenant(),
            gold_set_id=gs_id,
            invoked_by_user_id="cli-operator",
            reader=gs_reader,
            repository=repo,
            retrieval_runner=FakeRetrievalRunner(
                responses=_runner_responses(queries)
            ),
            audit_port=RecordingAuditPort(),
            metric_calculator=BinaryRelevanceMetrics(),
        )
    )

    snapshot = asyncio.run(
        get_evaluation_run(
            tenant_context=_tenant(),
            run_id=runner_result.run.id,
            reader=run_reader,
        )
    )
    assert snapshot is not None
    assert snapshot.run.id == runner_result.run.id
    assert snapshot.run.status is EvaluationRunStatus.COMPLETED
    assert len(snapshot.results) == len(EXECUTING_STRATEGIES)
    assert len(snapshot.aggregates) == len(EXECUTING_STRATEGIES)


def test_get_evaluation_run_cross_tenant_returns_none() -> None:
    expected = (uuid4(),)
    queries = [("q1", expected)]
    gs_id, gs_reader, _ = _seed_finalized_gold_set(
        tenant=_tenant(), queries_with_expected=queries
    )
    run_store = InMemoryEvaluationRunStore()
    repo = FakeEvaluationRunRepository(run_store)
    run_reader = FakeEvaluationRunReader(run_store)
    runner_result = asyncio.run(
        run_retrieval_evaluation(
            tenant_context=_tenant(),
            gold_set_id=gs_id,
            invoked_by_user_id="cli-operator",
            reader=gs_reader,
            repository=repo,
            retrieval_runner=FakeRetrievalRunner(
                responses=_runner_responses(queries)
            ),
            audit_port=RecordingAuditPort(),
            metric_calculator=BinaryRelevanceMetrics(),
        )
    )

    snapshot = asyncio.run(
        get_evaluation_run(
            tenant_context=_other_tenant(),
            run_id=runner_result.run.id,
            reader=run_reader,
        )
    )
    assert snapshot is None


def test_list_evaluation_runs_paginates_and_isolates_by_tenant() -> None:
    # Three runs for tenant A, two for tenant B.
    tenant_a, tenant_b = _tenant(), _other_tenant()
    run_store = InMemoryEvaluationRunStore()
    repo = FakeEvaluationRunRepository(run_store)
    run_reader = FakeEvaluationRunReader(run_store)

    queries_a = [("q1", (uuid4(),))]
    queries_b = [("q1", (uuid4(),))]
    gs_id_a, gs_reader_a, _ = _seed_finalized_gold_set(
        tenant=tenant_a, queries_with_expected=queries_a
    )
    gs_id_b, gs_reader_b, _ = _seed_finalized_gold_set(
        tenant=tenant_b, queries_with_expected=queries_b
    )

    for _ in range(3):
        asyncio.run(
            run_retrieval_evaluation(
                tenant_context=tenant_a,
                gold_set_id=gs_id_a,
                invoked_by_user_id="cli-operator",
                reader=gs_reader_a,
                repository=repo,
                retrieval_runner=FakeRetrievalRunner(
                    responses=_runner_responses(queries_a)
                ),
                audit_port=RecordingAuditPort(),
                metric_calculator=BinaryRelevanceMetrics(),
            )
        )
    for _ in range(2):
        asyncio.run(
            run_retrieval_evaluation(
                tenant_context=tenant_b,
                gold_set_id=gs_id_b,
                invoked_by_user_id="cli-operator",
                reader=gs_reader_b,
                repository=repo,
                retrieval_runner=FakeRetrievalRunner(
                    responses=_runner_responses(queries_b)
                ),
                audit_port=RecordingAuditPort(),
                metric_calculator=BinaryRelevanceMetrics(),
            )
        )

    page1, next_cursor = asyncio.run(
        list_evaluation_runs(
            tenant_context=tenant_a,
            reader=run_reader,
            encoded_cursor=None,
            page_size=2,
        )
    )
    assert len(page1.runs) == 2
    assert next_cursor is not None
    # All page-1 runs belong to tenant A
    for run in page1.runs:
        assert str(run.tenant_id) == tenant_a.tenant_id

    page2, next_cursor2 = asyncio.run(
        list_evaluation_runs(
            tenant_context=tenant_a,
            reader=run_reader,
            encoded_cursor=next_cursor,
            page_size=2,
        )
    )
    assert len(page2.runs) == 1
    assert next_cursor2 is None


def test_list_evaluation_runs_invalid_page_size_raises() -> None:
    run_reader = FakeEvaluationRunReader(InMemoryEvaluationRunStore())
    with pytest.raises(ValueError):
        asyncio.run(
            list_evaluation_runs(
                tenant_context=_tenant(),
                reader=run_reader,
                encoded_cursor=None,
                page_size=0,
            )
        )
    with pytest.raises(ValueError):
        asyncio.run(
            list_evaluation_runs(
                tenant_context=_tenant(),
                reader=run_reader,
                encoded_cursor=None,
                page_size=51,
            )
        )
