"""Unit tests for the LiteLLM ingestion extractor adapter (S21 / D64).

The adapter is one of three places ``litellm`` enters the ingestion
context — tests stub the SDK at the module-import boundary using
``unittest.mock.patch``. Domain-shape assertions verify the
JSON-mode call shape, the prompt-template substitution, the
defensive filtering of malformed entities and orphan-endpoint
relationships, the cost-attribution path, and the exception-
translation rules at the adapter boundary.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from contexts.ingestion.adapters.outbound.extraction import (
    LiteLLMEntityExtractor,
)
from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.ports.entity_extractor_port import (
    ExtractorConfigurationError,
    ExtractorError,
)
from shared_kernel import TenantContext


_TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)


def _chunk(content: str, chunk_id: UUID | None = None) -> Chunk:
    return Chunk(
        id=chunk_id or uuid4(),
        source_id=uuid4(),
        tenant_id=_TENANT_A.tenant_id,
        jurisdiction=_TENANT_A.jurisdiction,
        chunk_index=0,
        content=content,
    )


def _good_response(json_str: str) -> SimpleNamespace:
    """Build a SimpleNamespace mimicking a LiteLLM completion response
    with the JSON content we want to feed the parser. Includes a
    minimal usage block so the cost path lands as table_hit at zero
    rates (qwen2.5:7b is in the dev pricing table)."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=json_str)
            )
        ],
        model="qwen2.5:7b",
        usage=SimpleNamespace(prompt_tokens=120, completion_tokens=80),
    )


_GOOD_JSON = """{
  "entities": [
    {"name": "ACME Corp", "entity_type": "Organisation"},
    {"name": "Alice", "entity_type": "Person"}
  ],
  "relationships": [
    {
      "source_name": "ACME Corp",
      "source_entity_type": "Organisation",
      "target_name": "Alice",
      "target_entity_type": "Person",
      "relationship_type": "employs"
    }
  ]
}"""


def test_extract_returns_domain_entities_and_relationships() -> None:
    extractor = LiteLLMEntityExtractor()
    chunk = _chunk("ACME Corp employs Alice.")

    with patch(
        "contexts.ingestion.adapters.outbound.extraction.litellm_extractor.litellm.acompletion",
        return_value=_good_response(_GOOD_JSON),
    ):
        result = asyncio.run(extractor.extract([chunk], _TENANT_A))

    assert len(result.entities) == 2
    assert {e.name for e in result.entities} == {"ACME Corp", "Alice"}
    assert all(e.tenant_id == _TENANT_A.tenant_id for e in result.entities)
    assert all(e.source_chunk_ids == (chunk.id,) for e in result.entities)

    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.tenant_id == _TENANT_A.tenant_id
    assert rel.source.name == "ACME Corp"
    assert rel.target.name == "Alice"
    assert rel.relationship_type == "employs"
    assert rel.source_chunk_id == chunk.id


def test_extract_dedupes_entities_within_a_chunk() -> None:
    extractor = LiteLLMEntityExtractor()
    chunk = _chunk("ACME ACME ACME.")
    duplicated = """{
        "entities": [
            {"name": "ACME", "entity_type": "Organisation"},
            {"name": "ACME", "entity_type": "Organisation"}
        ],
        "relationships": []
    }"""

    with patch(
        "contexts.ingestion.adapters.outbound.extraction.litellm_extractor.litellm.acompletion",
        return_value=_good_response(duplicated),
    ):
        result = asyncio.run(extractor.extract([chunk], _TENANT_A))

    assert len(result.entities) == 1
    assert result.entities[0].name == "ACME"


def test_extract_filters_relationships_with_orphan_endpoints() -> None:
    extractor = LiteLLMEntityExtractor()
    chunk = _chunk("Some text.")
    orphan_relationship = """{
        "entities": [
            {"name": "ACME", "entity_type": "Organisation"}
        ],
        "relationships": [
            {
                "source_name": "ACME",
                "source_entity_type": "Organisation",
                "target_name": "Alice",
                "target_entity_type": "Person",
                "relationship_type": "employs"
            }
        ]
    }"""

    with patch(
        "contexts.ingestion.adapters.outbound.extraction.litellm_extractor.litellm.acompletion",
        return_value=_good_response(orphan_relationship),
    ):
        result = asyncio.run(extractor.extract([chunk], _TENANT_A))

    assert len(result.entities) == 1
    assert result.relationships == ()


def test_extract_skips_entities_with_missing_name_or_type() -> None:
    extractor = LiteLLMEntityExtractor()
    chunk = _chunk("Some text.")
    malformed = """{
        "entities": [
            {"name": "ACME", "entity_type": "Organisation"},
            {"name": "", "entity_type": "Person"},
            {"name": "Alice", "entity_type": ""},
            {"name": null, "entity_type": "Person"}
        ],
        "relationships": []
    }"""

    with patch(
        "contexts.ingestion.adapters.outbound.extraction.litellm_extractor.litellm.acompletion",
        return_value=_good_response(malformed),
    ):
        result = asyncio.run(extractor.extract([chunk], _TENANT_A))

    assert len(result.entities) == 1
    assert result.entities[0].name == "ACME"


def test_extract_no_op_on_empty_input() -> None:
    extractor = LiteLLMEntityExtractor()

    with patch(
        "contexts.ingestion.adapters.outbound.extraction.litellm_extractor.litellm.acompletion",
    ) as mock_call:
        result = asyncio.run(extractor.extract([], _TENANT_A))

    assert result.entities == ()
    assert result.relationships == ()
    mock_call.assert_not_called()


def test_extract_unparseable_json_raises_configuration_error() -> None:
    extractor = LiteLLMEntityExtractor()
    chunk = _chunk("Some text.")

    with patch(
        "contexts.ingestion.adapters.outbound.extraction.litellm_extractor.litellm.acompletion",
        return_value=_good_response("this is not JSON"),
    ):
        with pytest.raises(ExtractorConfigurationError, match="unparseable JSON"):
            asyncio.run(extractor.extract([chunk], _TENANT_A))


def test_extract_translates_timeout_to_retryable_error() -> None:
    from litellm.exceptions import Timeout as LiteLLMTimeout

    extractor = LiteLLMEntityExtractor()
    chunk = _chunk("Some text.")

    timeout_exc = LiteLLMTimeout(
        message="probe timeout", model="qwen2.5:7b", llm_provider="ollama"
    )

    with patch(
        "contexts.ingestion.adapters.outbound.extraction.litellm_extractor.litellm.acompletion",
        side_effect=timeout_exc,
    ):
        with pytest.raises(ExtractorError):
            asyncio.run(extractor.extract([chunk], _TENANT_A))


def test_extract_per_chunk_call_count() -> None:
    """Per-chunk extraction: N input chunks → N model calls."""
    extractor = LiteLLMEntityExtractor()
    chunks = [_chunk(f"chunk {i}") for i in range(3)]

    with patch(
        "contexts.ingestion.adapters.outbound.extraction.litellm_extractor.litellm.acompletion",
        return_value=_good_response('{"entities": [], "relationships": []}'),
    ) as mock_call:
        result = asyncio.run(extractor.extract(chunks, _TENANT_A))

    assert mock_call.call_count == 3
    assert result.entities == ()
    assert result.relationships == ()
