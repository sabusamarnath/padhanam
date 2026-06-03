"""Unit tests for email body chunking, graph mapping, and index_email (D151)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.email.application.index_email import index_email
from contexts.email.domain.email import Email
from contexts.email.domain.email_chunking import chunk_email
from contexts.email.domain.email_graph import email_to_graph

_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _email(*, subject: str = "Subj", body: str = "Body", from_a="a@x.com", to=("b@x.com",)) -> Email:
    return Email(
        id=uuid4(), tenant_id=_TENANT, jurisdiction="eu-west", message_id="m1", thread_id="t1",
        from_address=from_a, to_addresses=tuple(to), cc_addresses=(), subject=subject, body=body,
        snippet="s", received_at=_NOW, labels=(), history_id="9", content_hash="h",
        created_at=_NOW, updated_at=_NOW,
    )


def test_chunk_email_includes_subject_and_orders() -> None:
    chunks = chunk_email(_email(subject="Q2 review", body="para one\n\npara two"))
    assert chunks
    assert chunks[0].chunk_index == 0
    joined = "\n".join(c.content for c in chunks)
    assert "Q2 review" in joined and "para one" in joined and "para two" in joined


def test_chunk_email_hard_splits_long_paragraph() -> None:
    long_body = "x" * 2500
    chunks = chunk_email(_email(body=long_body), max_chars=1000)
    assert len(chunks) >= 3  # 2500 chars over ~1000 windows -> >= 3 chunks
    assert all(len(c.content) <= 1000 for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_email_empty_body() -> None:
    e = Email(
        id=uuid4(), tenant_id=_TENANT, jurisdiction="eu-west", message_id="m1", thread_id=None,
        from_address=None, to_addresses=(), cc_addresses=(), subject=None, body=None, snippet=None,
        received_at=_NOW, labels=(), history_id=None, content_hash=None, created_at=_NOW, updated_at=_NOW,
    )
    assert chunk_email(e) == []


def test_email_to_graph_participants_and_edges() -> None:
    entities, rels = email_to_graph(_email(from_a="alice@x.com", to=("bob@x.com", "carol@x.com")))
    names = {e.name for e in entities}
    assert names == {"alice@x.com", "bob@x.com", "carol@x.com"}
    assert all(e.entity_type == "Person" for e in entities)
    assert {(r.source_name, r.target_name) for r in rels} == {
        ("alice@x.com", "bob@x.com"),
        ("alice@x.com", "carol@x.com"),
    }
    assert all(r.relationship_type == "CORRESPONDED_WITH" for r in rels)


class _FakeEmbedder:
    async def embed_chunks(self, *, contents, tenant_context):
        return [[0.1] * 768 for _ in contents]


class _FakeGraph:
    def __init__(self) -> None:
        self.entities: list[Any] = []

    async def index_email(self, *, tenant_context, entities, relationships):
        self.entities.extend(entities)


class _FakeChunkRepo:
    def __init__(self) -> None:
        self.replaced: list[tuple[str, int]] = []

    async def replace_chunks(self, *, tenant_context, email_id, message_id, chunks):
        self.replaced.append((message_id, len(list(chunks))))

    async def delete_chunks_for_message(self, *, tenant_context, message_id):
        pass


def test_index_email_chunks_embeds_and_graphs() -> None:
    from shared_kernel import TenantContext

    ctx = TenantContext(tenant_id=str(_TENANT), jurisdiction="eu-west", cost_attribution_id="c")
    graph = _FakeGraph()
    chunk_repo = _FakeChunkRepo()
    count = asyncio.run(
        index_email(
            tenant_context=ctx, email=_email(body="para one\n\npara two"),
            embedder=_FakeEmbedder(), graph_index=graph, chunks=chunk_repo,
        )
    )
    assert count >= 1
    assert chunk_repo.replaced and chunk_repo.replaced[0][0] == "m1"
    assert graph.entities  # sender + recipient persons indexed
