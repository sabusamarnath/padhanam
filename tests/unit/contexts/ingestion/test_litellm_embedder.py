"""Unit tests for the LiteLLM ingestion embedder adapter (S20 / D62).

The adapter is the only place ``litellm`` enters the ingestion
context — tests stub the SDK at the module-import boundary using
``unittest.mock.patch``. Domain-shape assertions verify the
batch-mapping shape, the task-prefix application per nomic-embed-
text v1.5, the OTel span attributes, the cost-attribution path
including the embedding-specific ``embedding_no_token_count``
pricing-status flag, and the exception-translation rules at the
adapter boundary.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    Timeout,
)

from contexts.ingestion.adapters.outbound.embedding import (
    LiteLLMChunkEmbedder,
)
from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from contexts.ingestion.ports.chunk_embedder_port import (
    EmbedderConfigurationError,
    EmbedderError,
)
from shared_kernel import TenantContext
from padhanam.config import InferenceSettings


_TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)


def _settings() -> InferenceSettings:
    return InferenceSettings(litellm_master_key="sk-test-key")


def _chunk(content: str) -> Chunk:
    return Chunk(
        id=uuid4(),
        source_id=uuid4(),
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        chunk_index=0,
        content=content,
    )


def _ok_response(vectors: list[list[float]], input_tokens: int = 12) -> SimpleNamespace:
    """Construct a LiteLLM-shaped embedding response with the supplied
    vectors. Mirrors the OpenAI shape ``{data: [{embedding: [...], ...}],
    usage: {prompt_tokens: N}, model: ...}``.
    """
    return SimpleNamespace(
        data=[SimpleNamespace(embedding=v, index=i, object="embedding")
              for i, v in enumerate(vectors)],
        usage=SimpleNamespace(prompt_tokens=input_tokens),
        model="nomic-embed-text:v1.5",
    )


def _ok_response_no_token_count(vectors: list[list[float]]) -> SimpleNamespace:
    """Response shape where the usage block omits prompt_tokens — the
    Ollama-served path per the S20 reconciliation finding."""
    return SimpleNamespace(
        data=[SimpleNamespace(embedding=v, index=i, object="embedding")
              for i, v in enumerate(vectors)],
        usage=None,
        model="nomic-embed-text:v1.5",
    )


def test_embedder_returns_one_embedding_per_chunk_in_order() -> None:
    embedder = LiteLLMChunkEmbedder(settings=_settings())
    chunks = [_chunk("first"), _chunk("second"), _chunk("third")]
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]

    async def fake_aembedding(**kwargs: object) -> SimpleNamespace:
        return _ok_response(vectors)

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=fake_aembedding,
    ):
        result = asyncio.run(embedder.embed(chunks, _TENANT_A, EmbeddingTask.DOCUMENT))

    assert len(result) == 3
    assert [list(e.vector) for e in result] == vectors
    assert [e.chunk_id for e in result] == [c.id for c in chunks]
    assert all(e.model == "nomic-embed-text:v1.5" for e in result)


def test_embedder_applies_search_document_prefix_to_each_chunk() -> None:
    """Per D62: nomic-embed-text:v1.5 requires the corpus-side
    ``search_document:`` task prefix; the adapter prepends it before
    sending. Without the prefix, retrieval quality degrades silently
    on the model card's specification.
    """
    embedder = LiteLLMChunkEmbedder(settings=_settings())
    chunks = [_chunk("hello world"), _chunk("second chunk")]
    captured: dict[str, object] = {}

    async def fake_aembedding(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _ok_response([[0.1] * 768, [0.2] * 768])

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=fake_aembedding,
    ):
        asyncio.run(embedder.embed(chunks, _TENANT_A, EmbeddingTask.DOCUMENT))

    assert captured["input"] == [
        "search_document: hello world",
        "search_document: second chunk",
    ]


def test_embedder_applies_search_query_prefix_when_task_is_query() -> None:
    """Per D65: passing ``EmbeddingTask.QUERY`` switches the prefix
    to ``search_query:``. The retrieval adapter at S22 uses this
    task value for query-side embedding so the model produces
    embeddings that match cosine geometry against the document-
    prefixed corpus side.
    """
    embedder = LiteLLMChunkEmbedder(settings=_settings())
    chunks = [_chunk("what is acme")]
    captured: dict[str, object] = {}

    async def fake_aembedding(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _ok_response([[0.1] * 768])

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=fake_aembedding,
    ):
        asyncio.run(embedder.embed(chunks, _TENANT_A, EmbeddingTask.QUERY))

    assert captured["input"] == ["search_query: what is acme"]


def test_embed_query_applies_search_query_prefix() -> None:
    """``embed_query`` is the single-string retrieval-side path. With
    ``EmbeddingTask.QUERY`` the adapter prepends ``search_query:`` to
    the query string and returns the single embedding vector.
    """
    embedder = LiteLLMChunkEmbedder(settings=_settings())
    captured: dict[str, object] = {}

    async def fake_aembedding(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _ok_response([[0.5] * 768])

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=fake_aembedding,
    ):
        vector = asyncio.run(
            embedder.embed_query(
                "find ACME documents", _TENANT_A, EmbeddingTask.QUERY
            )
        )

    assert captured["input"] == ["search_query: find ACME documents"]
    assert list(vector) == [0.5] * 768


def test_embed_query_emits_cost_attributes_on_span(captured_spans) -> None:
    """``embed_query`` emits the same cost-attribution shape as the
    chunk-batch ``embed`` so retrieval-side embedding rolls up on the
    same per-tenant cost queries as ingestion-side embedding.
    """
    embedder = LiteLLMChunkEmbedder(settings=_settings())

    async def fake_aembedding(**kwargs: object) -> SimpleNamespace:
        return _ok_response([[0.1] * 768], input_tokens=7)

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=fake_aembedding,
    ):
        asyncio.run(
            embedder.embed_query("hello", _TENANT_A, EmbeddingTask.QUERY)
        )

    attrs = dict(captured_spans.get_finished_spans()[0].attributes)
    assert attrs["gen_ai.operation.name"] == "embeddings"
    assert attrs["padhanam.embedding.task"] == "query"
    assert attrs["padhanam.embedding.batch_size"] == 1
    assert attrs["tenant.id"] == _TENANT_A.tenant_id
    assert attrs["gen_ai.usage.input_tokens"] == 7
    assert attrs["gen_ai.cost.pricing_status"] == "table_hit"


def test_embed_query_translates_timeout_to_embedder_error() -> None:
    embedder = LiteLLMChunkEmbedder(settings=_settings())

    async def raise_timeout(**kwargs: object) -> SimpleNamespace:
        raise Timeout("boom", "litellm", "nomic")

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=raise_timeout,
    ):
        with pytest.raises(EmbedderError):
            asyncio.run(
                embedder.embed_query("x", _TENANT_A, EmbeddingTask.QUERY)
            )


def test_embedder_passes_endpoint_master_key_and_resolved_model() -> None:
    embedder = LiteLLMChunkEmbedder(settings=_settings())
    captured: dict[str, object] = {}

    async def fake_aembedding(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _ok_response([[0.1] * 768])

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=fake_aembedding,
    ):
        asyncio.run(embedder.embed([_chunk("x")], _TENANT_A, EmbeddingTask.DOCUMENT))

    # The adapter prefixes with "openai/" so the LiteLLM SDK routes
    # the call through the gateway as an OpenAI-compatible proxy.
    assert captured["model"] == "openai/nomic-embed-text:v1.5"
    assert captured["api_base"] == "http://litellm:4000"
    assert captured["api_key"] == "sk-test-key"


def test_embedder_returns_empty_for_empty_input_without_calling_litellm() -> None:
    embedder = LiteLLMChunkEmbedder(settings=_settings())
    called = {"count": 0}

    async def fake_aembedding(**kwargs: object) -> SimpleNamespace:
        called["count"] += 1
        return _ok_response([])

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=fake_aembedding,
    ):
        result = asyncio.run(embedder.embed([], _TENANT_A, EmbeddingTask.DOCUMENT))

    assert result == []
    assert called["count"] == 0


def test_embedder_emits_cost_attributes_on_span(
    captured_spans,
) -> None:
    """Per D41 / D49: the embedder span carries the four
    gen_ai.cost.* attributes plus tenant.* attributes the chat
    adapter emits, so per-tenant cost-rollup queries treat embedding
    cost the same shape they treat chat cost.
    """
    embedder = LiteLLMChunkEmbedder(settings=_settings())

    async def fake_aembedding(**kwargs: object) -> SimpleNamespace:
        return _ok_response([[0.1] * 768], input_tokens=42)

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=fake_aembedding,
    ):
        asyncio.run(embedder.embed([_chunk("x")], _TENANT_A, EmbeddingTask.DOCUMENT))

    spans = captured_spans.get_finished_spans()
    span = spans[0]
    assert span.name == "embeddings nomic-embed-text:v1.5"
    attrs = dict(span.attributes)
    assert attrs["gen_ai.system"] == "litellm"
    assert attrs["gen_ai.operation.name"] == "embeddings"
    assert attrs["gen_ai.request.model"] == "nomic-embed-text:v1.5"
    assert attrs["gen_ai.response.model"] == "nomic-embed-text:v1.5"
    assert attrs["gen_ai.usage.input_tokens"] == 42
    assert attrs["tenant.id"] == _TENANT_A.tenant_id
    assert attrs["tenant.jurisdiction"] == _TENANT_A.jurisdiction
    assert attrs["tenant.cost_attribution_id"] == _TENANT_A.cost_attribution_id
    assert attrs["padhanam.embedding.batch_size"] == 1
    # Pricing table has nomic-embed-text:v1.5 at zero rates (Ollama-
    # hosted dev). Cost attributes still appear so consumers always
    # see the structure.
    assert attrs["gen_ai.cost.input_usd"] == 0.0
    assert attrs["gen_ai.cost.output_usd"] == 0.0
    assert attrs["gen_ai.cost.total_usd"] == 0.0
    assert attrs["gen_ai.cost.pricing_status"] == "table_hit"


def test_embedder_emits_embedding_no_token_count_when_usage_absent(
    captured_spans,
) -> None:
    """Per D62 build refinement: when LiteLLM cannot supply a token
    count for the embedding call (Ollama's /api/embeddings omits a
    usage block server-side, and LiteLLM's local tokenizer may not
    populate prompt_tokens for every embedding path), the adapter
    surfaces the gap via gen_ai.cost.pricing_status rather than
    fabricating zero token counts. Cost path lands at zero with the
    flag attribute distinguishing the case from a real zero-cost
    table_hit.
    """
    embedder = LiteLLMChunkEmbedder(settings=_settings())

    async def fake_aembedding(**kwargs: object) -> SimpleNamespace:
        return _ok_response_no_token_count([[0.1] * 768])

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=fake_aembedding,
    ):
        asyncio.run(embedder.embed([_chunk("x")], _TENANT_A, EmbeddingTask.DOCUMENT))

    attrs = dict(captured_spans.get_finished_spans()[0].attributes)
    assert attrs["gen_ai.cost.pricing_status"] == "embedding_no_token_count"
    assert attrs["gen_ai.cost.total_usd"] == 0.0
    # gen_ai.usage.input_tokens is absent — the adapter does not
    # fabricate a number; consumers that care about the gap can
    # filter on pricing_status.
    assert "gen_ai.usage.input_tokens" not in attrs


def test_embedder_unknown_model_emits_unknown_model_pricing_status(
    captured_spans,
) -> None:
    """Per D49 precedent: an embedding model routed through LiteLLM
    but missing from the pricing table is configuration drift; the
    adapter emits zeros plus pricing_status='unknown_model' rather
    than breaking the call.
    """
    settings = InferenceSettings(
        litellm_master_key="sk-test-key",
        default_embedding_model="some-unmapped-model",
    )
    embedder = LiteLLMChunkEmbedder(settings=settings)

    async def fake_aembedding(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1] * 768, index=0,
                                   object="embedding")],
            usage=SimpleNamespace(prompt_tokens=12),
            model="some-unmapped-model",
        )

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=fake_aembedding,
    ):
        asyncio.run(embedder.embed([_chunk("x")], _TENANT_A, EmbeddingTask.DOCUMENT))

    attrs = dict(captured_spans.get_finished_spans()[0].attributes)
    assert attrs["gen_ai.cost.pricing_status"] == "unknown_model"
    assert attrs["gen_ai.cost.total_usd"] == 0.0


def test_embedder_response_length_mismatch_raises_embedder_error() -> None:
    embedder = LiteLLMChunkEmbedder(settings=_settings())

    async def fake_aembedding(**kwargs: object) -> SimpleNamespace:
        # Two chunks in, one vector out — protocol violation.
        return _ok_response([[0.1] * 768])

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=fake_aembedding,
    ):
        with pytest.raises(EmbedderError, match="length mismatch"):
            asyncio.run(
                embedder.embed(
                    [_chunk("a"), _chunk("b")], _TENANT_A, EmbeddingTask.DOCUMENT
                )
            )


def test_timeout_maps_to_embedder_error() -> None:
    embedder = LiteLLMChunkEmbedder(settings=_settings())

    async def raise_timeout(**kwargs: object) -> SimpleNamespace:
        raise Timeout("boom", "litellm", "nomic")

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=raise_timeout,
    ):
        with pytest.raises(EmbedderError):
            asyncio.run(embedder.embed([_chunk("x")], _TENANT_A, EmbeddingTask.DOCUMENT))


def test_rate_limit_maps_to_embedder_error() -> None:
    embedder = LiteLLMChunkEmbedder(settings=_settings())

    async def raise_rate_limit(**kwargs: object) -> SimpleNamespace:
        raise RateLimitError("rate", "litellm", "nomic")

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=raise_rate_limit,
    ):
        with pytest.raises(EmbedderError):
            asyncio.run(embedder.embed([_chunk("x")], _TENANT_A, EmbeddingTask.DOCUMENT))


def test_auth_error_maps_to_embedder_configuration_error() -> None:
    embedder = LiteLLMChunkEmbedder(settings=_settings())

    async def raise_auth(**kwargs: object) -> SimpleNamespace:
        raise AuthenticationError("bad key", "litellm", "nomic")

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=raise_auth,
    ):
        with pytest.raises(EmbedderConfigurationError):
            asyncio.run(embedder.embed([_chunk("x")], _TENANT_A, EmbeddingTask.DOCUMENT))


def test_bad_request_maps_to_embedder_configuration_error() -> None:
    embedder = LiteLLMChunkEmbedder(settings=_settings())

    async def raise_bad_request(**kwargs: object) -> SimpleNamespace:
        raise BadRequestError("bad model", "litellm", "nomic")

    with patch(
        "contexts.ingestion.adapters.outbound.embedding.litellm_embedder.litellm.aembedding",
        side_effect=raise_bad_request,
    ):
        with pytest.raises(EmbedderConfigurationError):
            asyncio.run(embedder.embed([_chunk("x")], _TENANT_A, EmbeddingTask.DOCUMENT))


@pytest.fixture
def captured_spans(monkeypatch: pytest.MonkeyPatch):
    """Replace the module's tracer with an SDK tracer backed by an
    in-memory exporter so cost-attribute assertions can inspect the
    recorded span. Returns the exporter; callers read
    ``captured_spans.get_finished_spans()`` after the operation
    under test runs. Restored automatically by monkeypatch.
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    from contexts.ingestion.adapters.outbound.embedding import (
        litellm_embedder as embedder_module,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(
        embedder_module, "_tracer", provider.get_tracer("test")
    )
    return exporter
