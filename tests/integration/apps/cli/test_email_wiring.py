"""Email composition-root wiring tests (D146, D151, S56a).

Exercises the apps bridges with doubles (no live Ollama/Neo4j): the
EmailChunkEmbedderBridge over ingestion's batch ChunkEmbedderPort.embed
(returning vectors in order), and the EmailGraphIndexBridge mapping email
graph DTOs to ingestion Entity/Relationship over a fake GraphRepository.
"""

from __future__ import annotations

import asyncio
from typing import Any

from apps.cli._email import EmailChunkEmbedderBridge, EmailGraphIndexBridge
from contexts.email.domain.email_graph import EmailGraphEntity, EmailGraphRelationship
from contexts.ingestion.domain.embedding import Embedding
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from shared_kernel import TenantContext

_CTX = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001", jurisdiction="eu-west",
    cost_attribution_id="c",
)


class _FakeChunkEmbedder:
    def __init__(self) -> None:
        self.calls: list[tuple[int, EmbeddingTask]] = []

    async def embed(self, chunks, tenant_context, task):
        self.calls.append((len(list(chunks)), task))
        return [Embedding(chunk_id=c.id, vector=[float(i)] * 768, model="fake") for i, c in enumerate(chunks)]

    async def embed_query(self, query, tenant_context, task):  # pragma: no cover
        raise AssertionError("email uses the batch embed, not embed_query")


def test_embedder_bridge_batches_and_orders() -> None:
    embedder = _FakeChunkEmbedder()
    bridge = EmailChunkEmbedderBridge(chunk_embedder=embedder)
    vectors = asyncio.run(
        bridge.embed_chunks(contents=["chunk a", "chunk b", "chunk c"], tenant_context=_CTX)
    )
    assert len(vectors) == 3
    assert embedder.calls == [(3, EmbeddingTask.DOCUMENT)]
    assert vectors[0] == [0.0] * 768 and vectors[2] == [2.0] * 768  # input order preserved


def test_embedder_bridge_empty() -> None:
    vectors = asyncio.run(
        EmailChunkEmbedderBridge(chunk_embedder=_FakeChunkEmbedder()).embed_chunks(
            contents=[], tenant_context=_CTX
        )
    )
    assert list(vectors) == []


class _FakeGraphRepository:
    def __init__(self) -> None:
        self.entities: list[Any] = []
        self.relationships: list[Any] = []

    async def merge_entities(self, entities, tenant_context) -> None:
        self.entities.extend(entities)

    async def merge_relationships(self, relationships, tenant_context) -> None:
        self.relationships.extend(relationships)

    async def get_entities_by_chunk_ids(self, chunk_ids, tenant_context):  # pragma: no cover
        return ()


def test_graph_bridge_maps_to_ingestion_shapes() -> None:
    graph = _FakeGraphRepository()
    bridge = EmailGraphIndexBridge(graph_repository=graph)
    asyncio.run(
        bridge.index_email(
            tenant_context=_CTX,
            entities=(EmailGraphEntity(name="alice@x.com", entity_type="Person"),),
            relationships=(
                EmailGraphRelationship(
                    source_name="alice@x.com", source_type="Person",
                    target_name="bob@x.com", target_type="Person",
                    relationship_type="CORRESPONDED_WITH",
                ),
            ),
        )
    )
    assert graph.entities[0].name == "alice@x.com"
    assert graph.entities[0].tenant_id == _CTX.tenant_id
    rel = graph.relationships[0]
    assert rel.source.name == "alice@x.com" and rel.target.name == "bob@x.com"
    assert rel.relationship_type == "CORRESPONDED_WITH"
