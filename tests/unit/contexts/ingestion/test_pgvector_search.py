"""Unit tests for the pgvector retrieval adapter (S22 / D65).

The adapter's SQL construction and embedder dispatch are verified
here. Behavioural assertions (tenant isolation under live DB,
``state = 'indexed'`` filter, similarity ordering) live in the e2e
integration test at ``tests/integration/contexts/ingestion/
test_retrieval_e2e.py`` because they need real pgvector cosine
distance and a populated chunks table.
"""

from __future__ import annotations

import asyncio
from typing import Sequence
from unittest.mock import MagicMock
from uuid import uuid4

from contexts.ingestion.adapters.outbound.retrieval import PgVectorSearch
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from shared_kernel import TenantContext


_TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)


class _CapturingEmbedder:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector
        self.calls: list[tuple[str, TenantContext, EmbeddingTask]] = []

    async def embed(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def embed_query(
        self,
        query: str,
        tenant_context: TenantContext,
        task: EmbeddingTask,
    ) -> Sequence[float]:
        self.calls.append((query, tenant_context, task))
        return self._vector


def _make_session_factory(rows: list[dict[str, object]]):
    """Build a fake async_sessionmaker whose session.execute returns
    a result whose ``.mappings().all()`` yields ``rows``. Captures
    the SQL parameters in ``captured`` for assertion.
    """
    captured: dict[str, object] = {}

    class _FakeResult:
        def mappings(self):
            class _M:
                def all(self_inner):
                    return rows

            return _M()

    class _FakeSession:
        async def execute(self_inner, statement, params=None):
            captured["params"] = params
            captured["statement"] = statement
            return _FakeResult()

        async def __aenter__(self_inner):
            return self_inner

        async def __aexit__(self_inner, *args):
            return None

    def factory():
        return _FakeSession()

    return factory, captured


def test_search_vector_calls_embedder_with_query_task() -> None:
    """D65: the adapter embeds the query with EmbeddingTask.QUERY so
    the nomic-embed-text v1.5 ``search_query:`` prefix lands.
    """
    embedder = _CapturingEmbedder([0.1] * 768)
    factory, _ = _make_session_factory([])
    adapter = PgVectorSearch(session_factory=factory, embedder=embedder)

    asyncio.run(adapter.search_vector("acme", _TENANT_A, limit=5))

    assert len(embedder.calls) == 1
    query, ctx, task = embedder.calls[0]
    assert query == "acme"
    assert ctx == _TENANT_A
    assert task == EmbeddingTask.QUERY


def test_search_vector_passes_tenant_id_state_and_limit_in_params() -> None:
    """D65: the SQL parameters carry the bound tenant_id, the
    indexed-state filter literal, and the limit; the WHERE clause
    in the SQL text pins both ``chunks.tenant_id`` and
    ``sources.tenant_id`` so cross-tenant rows cannot match.
    """
    embedder = _CapturingEmbedder([0.0] * 768)
    factory, captured = _make_session_factory([])
    adapter = PgVectorSearch(session_factory=factory, embedder=embedder)

    asyncio.run(adapter.search_vector("anything", _TENANT_A, limit=7))

    params = captured["params"]
    assert params["tenant_id"] == _TENANT_A.tenant_id
    assert params["indexed_state"] == "indexed"
    assert params["limit"] == 7
    # The vector lands as a pgvector text literal so the SQL casts
    # cleanly via CAST(... AS vector).
    assert isinstance(params["query_vec"], str)
    assert params["query_vec"].startswith("[")
    assert params["query_vec"].endswith("]")


def test_search_vector_sql_text_filters_indexed_state_and_tenant() -> None:
    """The SQL text carries the cross-track readiness filter
    (``s.state = :indexed_state``) and the tenant predicates.
    Verified against the rendered statement so a regression that
    drops the filter surfaces at unit-test time.
    """
    embedder = _CapturingEmbedder([0.0] * 768)
    factory, captured = _make_session_factory([])
    adapter = PgVectorSearch(session_factory=factory, embedder=embedder)

    asyncio.run(adapter.search_vector("anything", _TENANT_A, limit=1))

    sql = str(captured["statement"])
    assert "s.state = :indexed_state" in sql
    assert "s.tenant_id = :tenant_id" in sql
    assert "c.tenant_id = :tenant_id" in sql
    assert "c.embedding <=> CAST(:query_vec AS vector)" in sql


def test_search_vector_returns_empty_for_zero_limit_without_calling_embedder() -> None:
    """A zero or negative limit short-circuits before embedder + DB
    work. Defensive against agent-layer composition that miscalculates
    a remaining-budget limit; cheaper to return empty than to issue
    a degenerate SQL query.
    """
    embedder = _CapturingEmbedder([0.0] * 768)
    factory, captured = _make_session_factory([])
    adapter = PgVectorSearch(session_factory=factory, embedder=embedder)

    result = asyncio.run(
        adapter.search_vector("anything", _TENANT_A, limit=0)
    )

    assert result == []
    assert embedder.calls == []
    assert "params" not in captured


def test_search_vector_maps_rows_to_chunk_results() -> None:
    """Each returned row maps to a ChunkResult with the similarity
    score the SQL surfaced (1.0 - cosine_distance).
    """
    chunk_id = uuid4()
    source_id = uuid4()
    rows = [
        {
            "id": str(chunk_id),
            "source_id": str(source_id),
            "tenant_id": _TENANT_A.tenant_id,
            "jurisdiction": _TENANT_A.jurisdiction,
            "content": "ACME Corp is in London",
            "structural_metadata": {"heading_text": "Intro"},
            "chunk_index": 4,
            "created_at": __import__("datetime").datetime.now(
                tz=__import__("datetime").timezone.utc
            ),
            "source_file_name": "acme.pdf",
            "source_file_type": "application/pdf",
            "similarity_score": 0.91,
        }
    ]
    embedder = _CapturingEmbedder([0.0] * 768)
    factory, _ = _make_session_factory(rows)
    adapter = PgVectorSearch(session_factory=factory, embedder=embedder)

    result = asyncio.run(adapter.search_vector("acme", _TENANT_A, limit=5))

    assert len(result) == 1
    r = result[0]
    assert r.chunk_id == chunk_id
    assert r.source_id == source_id
    assert r.tenant_id == _TENANT_A.tenant_id
    assert r.content == "ACME Corp is in London"
    assert r.similarity_score == 0.91
    assert r.structural_metadata == {"heading_text": "Intro"}
    # D96 / S32: chunk_index and source_snapshot surfaced from the
    # SQL join so the agent-context adapter can build citation
    # candidates single-pass.
    assert r.chunk_index == 4
    assert r.source_snapshot == {
        "file_name": "acme.pdf",
        "file_type": "application/pdf",
    }
