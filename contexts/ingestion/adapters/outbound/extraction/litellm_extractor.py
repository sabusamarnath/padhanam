"""LiteLLM outbound adapter implementing EntityExtractorPort
(D64).

Vendor isolation: this is the third place in the codebase that
imports ``litellm``, alongside the chat adapter at
``contexts.inference.adapters.outbound.litellm`` and the embedding
adapter at ``contexts.ingestion.adapters.outbound.embedding``;
the import-linter ``litellm-confined`` contract extends to admit
this directory.

Build-time refinement of D64 (recorded in the S21 session log
reflection per the framing-prompt-as-recommendation pattern):
S21's pre-write reconciliation against Qwen 2.5 7B served via
Ollama through LiteLLM revealed that tool-calling has poor
fidelity (the model called the function but with malformed
arguments — the Ollama tool-call binding does not robustly route
JSON-schema-shaped parameters through the LiteLLM bridge). JSON
mode (``response_format={"type": "json_object"}``) produced
reliable, schema-conformant JSON. The adapter uses JSON mode plus
a versioned prompt template (``prompts/extraction_v1.txt``).

Per-chunk extraction: one model call per input chunk so each
extracted entity carries the exact chunk it surfaced from. The
GraphRepository's MERGE-on-(tenant_id, name, entity_type) will
collapse repeated entities across chunks into a single node with
``source_chunk_ids`` accumulating the provenance.

Trace propagation per D27 / D41 / D49 / D50: each chunk's
extraction call wraps in a span with the GenAI semantic-
convention attributes plus the four cost attributes plus the
three tenant attributes the inference and embedding adapters
established at S15 / S20.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
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
from contexts.ingestion.domain.entity import Entity
from contexts.ingestion.domain.extraction_result import ExtractionResult
from contexts.ingestion.domain.relationship import EntityRef, Relationship
from contexts.ingestion.ports.entity_extractor_port import (
    ExtractorConfigurationError,
    ExtractorError,
)
from shared_kernel import TenantContext
from padhanam.config import InferenceSettings, UnknownModelError, cost_for


_tracer = trace.get_tracer("padhanam.ingestion.litellm_extractor")


_PROMPT_PATH = (
    Path(__file__).resolve().parent / "prompts" / "extraction_v1.txt"
)


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


class LiteLLMEntityExtractor:
    """Implements EntityExtractorPort against the LiteLLM gateway
    using ``response_format={"type": "json_object"}`` for reliable
    JSON output.

    Per-chunk extraction: ``extract`` makes one model call per
    input chunk and accumulates the results. The aggregate
    ``ExtractionResult`` carries one Entity instance per
    (chunk, name, entity_type) triple — duplicates within a chunk
    are deduplicated; duplicates across chunks become separate
    Entity rows from the adapter's perspective and are collapsed
    by the GraphRepository's MERGE on ``(tenant_id, name,
    entity_type)``.
    """

    def __init__(
        self,
        settings: InferenceSettings | None = None,
        prompt_template: str | None = None,
    ) -> None:
        self._settings = settings or InferenceSettings()
        self._prompt_template = prompt_template or _load_prompt()

    async def extract(
        self,
        chunks: Sequence[Chunk],
        tenant_context: TenantContext,
    ) -> ExtractionResult:
        if not chunks:
            return ExtractionResult()

        all_entities: list[Entity] = []
        all_relationships: list[Relationship] = []

        for chunk in chunks:
            entities, relationships = await self._extract_one(
                chunk, tenant_context
            )
            all_entities.extend(entities)
            all_relationships.extend(relationships)

        return ExtractionResult(
            entities=tuple(all_entities),
            relationships=tuple(all_relationships),
        )

    async def _extract_one(
        self,
        chunk: Chunk,
        tenant_context: TenantContext,
    ) -> tuple[list[Entity], list[Relationship]]:
        resolved_model = self._settings.default_model
        endpoint = self._settings.litellm_endpoint
        master_key = self._settings.litellm_master_key

        with _tracer.start_as_current_span(
            f"extract {resolved_model}",
            kind=SpanKind.CLIENT,
            attributes={
                "gen_ai.system": "litellm",
                "gen_ai.request.model": resolved_model,
                "gen_ai.operation.name": "extract",
                "tenant.id": tenant_context.tenant_id,
                "tenant.jurisdiction": tenant_context.jurisdiction,
                "tenant.cost_attribution_id": tenant_context.cost_attribution_id,
                "padhanam.extraction.chunk_id": str(chunk.id),
                "padhanam.extraction.source_id": str(chunk.source_id),
            },
        ) as span:
            prompt = self._prompt_template.replace(
                "{chunk_content}", chunk.content
            )
            try:
                response = await litellm.acompletion(
                    model=f"openai/{resolved_model}",
                    messages=[{"role": "user", "content": prompt}],
                    api_base=endpoint,
                    api_key=master_key,
                    response_format={"type": "json_object"},
                )
            except (Timeout,) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise ExtractorError(str(e)) from e
            except (
                RateLimitError,
                ServiceUnavailableError,
                APIConnectionError,
            ) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise ExtractorError(str(e)) from e
            except (
                AuthenticationError,
                BadRequestError,
                NotFoundError,
            ) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise ExtractorConfigurationError(str(e)) from e
            except APIError as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise ExtractorError(str(e)) from e

            content = _content_from_response(response)
            try:
                payload = json.loads(content)
            except json.JSONDecodeError as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise ExtractorConfigurationError(
                    f"extractor produced unparseable JSON: {e}; "
                    f"first 200 chars: {content[:200]!r}"
                ) from e

            entities, relationships = _build_domain_objects(
                payload, chunk, tenant_context
            )

            # Cost capture per D41 (mirrors the chat adapter at S15
            # and the embedder at S20). Qwen 2.5 7B via Ollama has
            # a usage block populated by LiteLLM so this lands as
            # table_hit at zero rates per the dev-cost precedent.
            response_model = _response_model(response, resolved_model)
            input_tokens = _input_tokens_from_response(response)
            output_tokens = _output_tokens_from_response(response)

            if input_tokens is None or output_tokens is None:
                input_usd = 0.0
                output_usd = 0.0
                total_usd = 0.0
                pricing_status = "extraction_no_token_count"
            else:
                span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
                span.set_attribute(
                    "gen_ai.usage.output_tokens", output_tokens
                )
                try:
                    breakdown = cost_for(
                        response_model, input_tokens, output_tokens
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
            span.set_attribute(
                "padhanam.extraction.entities_count", len(entities)
            )
            span.set_attribute(
                "padhanam.extraction.relationships_count", len(relationships)
            )

            return entities, relationships


def _content_from_response(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if not choices:
        raise ExtractorConfigurationError(
            "LiteLLM extraction response missing choices"
        )
    msg = getattr(choices[0], "message", None) or choices[0].get("message")
    content = getattr(msg, "content", None) or (
        msg.get("content") if isinstance(msg, dict) else None
    )
    if content is None:
        raise ExtractorConfigurationError(
            "LiteLLM extraction response missing content"
        )
    return content


def _build_domain_objects(
    payload: Any,
    chunk: Chunk,
    tenant_context: TenantContext,
) -> tuple[list[Entity], list[Relationship]]:
    if not isinstance(payload, dict):
        raise ExtractorConfigurationError(
            f"extraction payload is not a JSON object: {type(payload).__name__}"
        )
    raw_entities = payload.get("entities", [])
    raw_relationships = payload.get("relationships", [])
    if not isinstance(raw_entities, list) or not isinstance(
        raw_relationships, list
    ):
        raise ExtractorConfigurationError(
            "extraction payload `entities` and `relationships` must be JSON arrays"
        )

    now = datetime.now(tz=timezone.utc)

    entities: list[Entity] = []
    seen_entity_keys: set[tuple[str, str]] = set()
    for raw in raw_entities:
        if not isinstance(raw, dict):
            continue
        name = (raw.get("name") or "").strip()
        entity_type = (raw.get("entity_type") or "").strip()
        if not name or not entity_type:
            continue
        key = (name, entity_type)
        if key in seen_entity_keys:
            continue
        seen_entity_keys.add(key)
        entities.append(
            Entity(
                tenant_id=tenant_context.tenant_id,
                jurisdiction=tenant_context.jurisdiction,
                name=name,
                entity_type=entity_type,
                source_chunk_ids=(chunk.id,),
                created_at=now,
            )
        )

    relationships: list[Relationship] = []
    for raw in raw_relationships:
        if not isinstance(raw, dict):
            continue
        source_name = (raw.get("source_name") or "").strip()
        source_entity_type = (raw.get("source_entity_type") or "").strip()
        target_name = (raw.get("target_name") or "").strip()
        target_entity_type = (raw.get("target_entity_type") or "").strip()
        relationship_type = (raw.get("relationship_type") or "").strip()
        if not all(
            (source_name, source_entity_type, target_name,
             target_entity_type, relationship_type)
        ):
            continue
        # Skip relationships whose endpoints are not in the
        # extracted entities — the prompt asks for this property,
        # but defensive filtering keeps malformed model outputs from
        # producing dangling MERGE-MATCH failures at the wrapper.
        if (source_name, source_entity_type) not in seen_entity_keys:
            continue
        if (target_name, target_entity_type) not in seen_entity_keys:
            continue
        relationships.append(
            Relationship(
                tenant_id=tenant_context.tenant_id,
                jurisdiction=tenant_context.jurisdiction,
                source=EntityRef(
                    name=source_name, entity_type=source_entity_type
                ),
                target=EntityRef(
                    name=target_name, entity_type=target_entity_type
                ),
                relationship_type=relationship_type,
                source_chunk_id=chunk.id,
                created_at=now,
            )
        )

    return entities, relationships


def _input_tokens_from_response(response: Any) -> int | None:
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


def _output_tokens_from_response(response: Any) -> int | None:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return None
    tokens = getattr(usage, "completion_tokens", None)
    if tokens is None and isinstance(usage, dict):
        tokens = usage.get("completion_tokens")
    if tokens is None:
        return None
    return int(tokens)


def _response_model(response: Any, requested_model: str) -> str:
    response_model = getattr(response, "model", None)
    if response_model is None and isinstance(response, dict):
        response_model = response.get("model")
    return response_model or requested_model
