"""LiteLLM outbound adapter implementing ChunkEmbedderPort (D62).

Vendor isolation: this is the only file in the ingestion context
that imports ``litellm``; the import-linter ``litellm-confined``
contract extends to admit this directory alongside
``contexts.inference.adapters.outbound.litellm`` per S20.

Trace propagation: each batch call wraps in an OTel span with
GenAI semantic-convention attributes per D27, mirroring the
chat-completion adapter's shape (S15 / D49 / D50). The span carries
the ``tenant.id``, ``tenant.jurisdiction``, and
``tenant.cost_attribution_id`` attributes so per-tenant cost-rollup
queries land embedding cost on the same surface chat cost lands on.
The ``gen_ai.operation.name`` attribute distinguishes embedding
spans from chat spans so the cost-query path can filter by
operation when it lands at S22 retrieval or P11 recommendation.

Cost capture per D41 / D49: the adapter reads
``gen_ai.usage.input_tokens`` from the LiteLLM response if present
and computes USD via the shared ``cost_for`` helper from
``padhanam.config.inference``. Token attribution for embedding
requests against Ollama-served models flows through LiteLLM's
local tokenizer (Ollama's /api/embeddings response omits a usage
block); when LiteLLM cannot supply a token count the adapter emits
``gen_ai.cost.pricing_status="embedding_no_token_count"`` to surface
the gap honestly without breaking the cost path. The S20 reflection
captures whether LiteLLM's local tokenizer reliably populates
input_tokens for embedding paths against Ollama or whether bridging
work lands at a future cost-attribution session.

Task-prefix per D62 / D65: ``nomic-embed-text:v1.5`` requires a
``search_document:`` prefix on corpus-side inputs and
``search_query:`` on query-side. The adapter dispatches on the
``EmbeddingTask`` parameter: ``DOCUMENT`` prepends the corpus
prefix, ``QUERY`` prepends the query prefix. The two-method shape
on the port (``embed`` for batch chunks, ``embed_query`` for a
single query string) matches the two access patterns the worker
and the retrieval adapter exercise; both methods route to the
same underlying SDK call (``litellm.aembedding``) with the same
trace-attribution shape.
"""

from __future__ import annotations

from typing import Any, Sequence

import litellm
from litellm.exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.embedding import Embedding
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from contexts.ingestion.ports.chunk_embedder_port import (
    EmbedderConfigurationError,
    EmbedderError,
)
from shared_kernel import TenantContext
from padhanam.config import InferenceSettings, UnknownModelError, cost_for


_tracer = trace.get_tracer("padhanam.ingestion.litellm_embedder")


# nomic-embed-text v1.5 task-prefix tokens per the model card.
# DOCUMENT lands at corpus-side embedding (the S20 worker);
# QUERY lands at retrieval-side embedding (the S22 vector adapter).
_TASK_PREFIXES: dict[EmbeddingTask, str] = {
    EmbeddingTask.DOCUMENT: "search_document: ",
    EmbeddingTask.QUERY: "search_query: ",
}


class LiteLLMChunkEmbedder:
    """Implements ChunkEmbedderPort against the LiteLLM gateway.

    Configuration (endpoint, master key, default embedding model)
    flows through ``InferenceSettings``; ``default_embedding_model``
    is the embedder-side analogue of ``default_model``.

    The same gateway endpoint serves both the chat and embeddings
    paths — LiteLLM routes by model name to the right backend.
    """

    def __init__(self, settings: InferenceSettings | None = None) -> None:
        self._settings = settings or InferenceSettings()

    async def embed(
        self,
        chunks: Sequence[Chunk],
        tenant_context: TenantContext,
        task: EmbeddingTask,
    ) -> Sequence[Embedding]:
        if not chunks:
            return []

        resolved_model = self._settings.default_embedding_model
        endpoint = self._settings.litellm_endpoint
        master_key = self._settings.litellm_master_key
        prefix = _TASK_PREFIXES[task]

        # GenAI semantic conventions per D27. Span name follows the
        # OTel GenAI guidance ("embeddings {model}") so Langfuse
        # renders this as an embedding span rather than an opaque
        # internal span. The tenant.* namespace mirrors the chat
        # adapter (S15 / D50) so per-tenant cost-rollup queries
        # treat embedding cost the same shape they treat chat cost.
        with _tracer.start_as_current_span(
            f"embeddings {resolved_model}",
            kind=SpanKind.CLIENT,
            attributes={
                "gen_ai.system": "litellm",
                "gen_ai.request.model": resolved_model,
                "gen_ai.operation.name": "embeddings",
                "tenant.id": tenant_context.tenant_id,
                "tenant.jurisdiction": tenant_context.jurisdiction,
                "tenant.cost_attribution_id": tenant_context.cost_attribution_id,
                "padhanam.embedding.batch_size": len(chunks),
                "padhanam.embedding.task": task.value,
            },
        ) as span:
            inputs = [prefix + chunk.content for chunk in chunks]
            try:
                # Call the LiteLLM gateway via the OpenAI-compatible
                # /v1/embeddings route. Same `openai/` prefix
                # pattern as the chat adapter so the SDK treats the
                # gateway as an OpenAI proxy; the gateway routes to
                # the Ollama backend via ops/litellm/config.yaml.
                response = await litellm.aembedding(
                    model=f"openai/{resolved_model}",
                    input=inputs,
                    api_base=endpoint,
                    api_key=master_key,
                )
            except (Timeout,) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise EmbedderError(str(e)) from e
            except (
                RateLimitError,
                ServiceUnavailableError,
                APIConnectionError,
            ) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise EmbedderError(str(e)) from e
            except (
                AuthenticationError,
                BadRequestError,
                NotFoundError,
            ) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise EmbedderConfigurationError(str(e)) from e
            except APIError as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise EmbedderError(str(e)) from e

            embeddings = _embeddings_from_litellm_response(
                response, chunks, resolved_model
            )

            # Token attribution per D41. Ollama's /api/embeddings
            # omits a usage block server-side; LiteLLM may compute
            # input tokens via its local tokenizer. When a token
            # count is available the cost path lands as table_hit
            # against the embedding model's pricing-row; when
            # missing, the pricing_status flag surfaces the gap
            # without breaking inference.
            input_tokens = _input_tokens_from_response(response)
            response_model = _response_model(response, resolved_model)

            if input_tokens is None:
                input_usd = 0.0
                output_usd = 0.0
                total_usd = 0.0
                pricing_status = "embedding_no_token_count"
            else:
                span.set_attribute(
                    "gen_ai.usage.input_tokens", input_tokens
                )
                try:
                    breakdown = cost_for(
                        response_model,
                        input_tokens,
                        0,  # embeddings have no output tokens
                    )
                    input_usd = float(breakdown.input_usd)
                    output_usd = float(breakdown.output_usd)
                    total_usd = float(breakdown.total_usd)
                    pricing_status = "table_hit"
                except UnknownModelError:
                    input_usd = 0.0
                    output_usd = 0.0
                    total_usd = 0.0
                    pricing_status = "unknown_model"

            span.set_attribute("gen_ai.response.model", response_model)
            span.set_attribute("gen_ai.cost.input_usd", input_usd)
            span.set_attribute("gen_ai.cost.output_usd", output_usd)
            span.set_attribute("gen_ai.cost.total_usd", total_usd)
            span.set_attribute("gen_ai.cost.pricing_status", pricing_status)

            return embeddings

    async def embed_query(
        self,
        query: str,
        tenant_context: TenantContext,
        task: EmbeddingTask,
    ) -> Sequence[float]:
        """Single-query embedding for the retrieval adapter (D65).

        Same gateway path and cost-attribution shape as ``embed``;
        the input is a single string with the task-specific prefix
        and the return is a single vector. Cost flows through the
        same trace surface so retrieval-side embedding rolls up on
        the same per-tenant cost queries as ingestion-side
        embedding.
        """
        resolved_model = self._settings.default_embedding_model
        endpoint = self._settings.litellm_endpoint
        master_key = self._settings.litellm_master_key
        prefix = _TASK_PREFIXES[task]

        with _tracer.start_as_current_span(
            f"embeddings {resolved_model}",
            kind=SpanKind.CLIENT,
            attributes={
                "gen_ai.system": "litellm",
                "gen_ai.request.model": resolved_model,
                "gen_ai.operation.name": "embeddings",
                "tenant.id": tenant_context.tenant_id,
                "tenant.jurisdiction": tenant_context.jurisdiction,
                "tenant.cost_attribution_id": tenant_context.cost_attribution_id,
                "padhanam.embedding.batch_size": 1,
                "padhanam.embedding.task": task.value,
            },
        ) as span:
            try:
                response = await litellm.aembedding(
                    model=f"openai/{resolved_model}",
                    input=[prefix + query],
                    api_base=endpoint,
                    api_key=master_key,
                )
            except (Timeout,) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise EmbedderError(str(e)) from e
            except (
                RateLimitError,
                ServiceUnavailableError,
                APIConnectionError,
            ) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise EmbedderError(str(e)) from e
            except (
                AuthenticationError,
                BadRequestError,
                NotFoundError,
            ) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise EmbedderConfigurationError(str(e)) from e
            except APIError as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise EmbedderError(str(e)) from e

            data = getattr(response, "data", None)
            if data is None and isinstance(response, dict):
                data = response.get("data")
            if not data:
                raise EmbedderError(
                    "LiteLLM embedding response missing data for query"
                )
            if len(data) != 1:
                raise EmbedderError(
                    f"LiteLLM embedding response length mismatch for query: "
                    f"got {len(data)} embeddings for 1 input"
                )
            vector = _vector_from_data_item(data[0])

            input_tokens = _input_tokens_from_response(response)
            response_model = _response_model(response, resolved_model)

            if input_tokens is None:
                input_usd = 0.0
                output_usd = 0.0
                total_usd = 0.0
                pricing_status = "embedding_no_token_count"
            else:
                span.set_attribute(
                    "gen_ai.usage.input_tokens", input_tokens
                )
                try:
                    breakdown = cost_for(
                        response_model,
                        input_tokens,
                        0,
                    )
                    input_usd = float(breakdown.input_usd)
                    output_usd = float(breakdown.output_usd)
                    total_usd = float(breakdown.total_usd)
                    pricing_status = "table_hit"
                except UnknownModelError:
                    input_usd = 0.0
                    output_usd = 0.0
                    total_usd = 0.0
                    pricing_status = "unknown_model"

            span.set_attribute("gen_ai.response.model", response_model)
            span.set_attribute("gen_ai.cost.input_usd", input_usd)
            span.set_attribute("gen_ai.cost.output_usd", output_usd)
            span.set_attribute("gen_ai.cost.total_usd", total_usd)
            span.set_attribute("gen_ai.cost.pricing_status", pricing_status)

            return vector


def _embeddings_from_litellm_response(
    response: Any,
    chunks: Sequence[Chunk],
    requested_model: str,
) -> list[Embedding]:
    """Map a LiteLLM EmbeddingResponse into a list of domain Embeddings.

    LiteLLM returns OpenAI-shaped objects with ``data`` being a list
    of ``{embedding: [...], index: int, object: 'embedding'}``. The
    response preserves input order; the adapter pairs response[i]
    with chunks[i] by position rather than by index attribute, since
    the index attribute is the position in the response and
    LiteLLM's contract preserves input order.
    """
    response_model = _response_model(response, requested_model)
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    if data is None:
        raise EmbedderError(
            "LiteLLM embedding response missing data field"
        )
    if len(data) != len(chunks):
        raise EmbedderError(
            f"LiteLLM embedding response length mismatch: "
            f"got {len(data)} embeddings for {len(chunks)} chunks"
        )
    embeddings: list[Embedding] = []
    for chunk, item in zip(chunks, data):
        vector = _vector_from_data_item(item)
        embeddings.append(
            Embedding(
                chunk_id=chunk.id,
                vector=vector,
                model=response_model,
            )
        )
    return embeddings


def _vector_from_data_item(item: Any) -> list[float]:
    """Extract the embedding vector from a LiteLLM response data item.

    Items may be Pydantic models with ``.embedding`` attributes or
    dicts with an ``embedding`` key — the adapter accepts either.
    """
    vector = getattr(item, "embedding", None)
    if vector is None and isinstance(item, dict):
        vector = item.get("embedding")
    if vector is None:
        raise EmbedderError(
            "LiteLLM embedding response item missing embedding vector"
        )
    return [float(v) for v in vector]


def _input_tokens_from_response(response: Any) -> int | None:
    """Return the input token count from a LiteLLM embedding response.

    Returns None when the usage block is absent or carries no token
    count (the Ollama-served path; LiteLLM may compute via local
    tokenizer or leave the usage block sparse). The adapter surfaces
    the absent-attribution case via the ``embedding_no_token_count``
    pricing-status value rather than fabricating zero.
    """
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return None
    tokens = getattr(usage, "prompt_tokens", None)
    if tokens is None and isinstance(usage, dict):
        tokens = usage.get("prompt_tokens")
    if tokens is None:
        return None
    return int(tokens)


def _response_model(response: Any, requested_model: str) -> str:
    """Return the embedding model the response identifies, falling back
    to the requested model when the response omits it.
    """
    response_model = getattr(response, "model", None)
    if response_model is None and isinstance(response, dict):
        response_model = response.get("model")
    return response_model or requested_model
