"""End-to-end cost-capture verification for the LiteLLM extractor
adapter (S21 / D64).

Drives the ``LiteLLMEntityExtractor`` against the live LiteLLM
gateway → Ollama-served ``qwen2.5:7b`` and captures the emitted
OTel span via an in-process ``InMemorySpanExporter``. Asserts the
cost-attribution surface lands the same shape the chat adapter
landed at S15 and the embedder landed at S20: tenant.* attributes,
gen_ai.* attributes including operation name and the usage token
counts, and the four gen_ai.cost.* attributes including
``pricing_status``.

The unit tests at
``tests/unit/contexts/ingestion/test_litellm_extractor`` verify
adapter behaviour against mocked LiteLLM responses; this test
verifies the gateway integration delivers the expected shape under
real Ollama inference. The S21 reconciliation finding (Qwen 2.5 7B
via Ollama through LiteLLM has poor tool-calling fidelity but
reliable JSON-mode output) lands as a passing assertion here when
JSON mode produces a valid extraction; the cost path lands as
``table_hit`` at zero rates per the D49 precedent for
``qwen2.5:7b`` in the dev pricing table.

Skip discriminator: docker compose reachable + padhanam-api +
litellm + ollama healthy.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(
            ["docker", "compose", "ps", "-q"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
    return True


def _services_running(*names: str) -> bool:
    proc = subprocess.run(
        ["docker", "compose", "ps", "--services", "--filter", "status=running"],
        capture_output=True,
        text=True,
        check=False,
    )
    running = set(proc.stdout.split())
    return set(names).issubset(running)


@pytest.fixture(scope="module")
def stack_ready() -> None:
    if not _docker_available():
        pytest.skip("docker compose not reachable from test environment")
    if not _services_running("padhanam-api", "litellm", "ollama"):
        pytest.skip(
            "padhanam-api, litellm, and ollama must be running"
        )


def test_live_extract_call_emits_full_cost_attribution_shape(
    stack_ready: None,
) -> None:
    """Live LiteLLM → Ollama extraction call. Captures the OTel span
    via in-memory exporter and asserts the four cost.* attributes
    plus the three tenant.* attributes plus the operation name +
    model + token counts land on the span the same way the chat
    and embedding adapters do.
    """
    script = r"""
import asyncio
import json
import sys
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from contexts.ingestion.adapters.outbound.extraction import (
    LiteLLMEntityExtractor,
)
from contexts.ingestion.adapters.outbound.extraction import litellm_extractor as ex_module
from contexts.ingestion.domain.chunk import Chunk
from shared_kernel import TenantContext


exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
test_tracer = provider.get_tracer("test")
ex_module._tracer = test_tracer


tenant = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)

chunk = Chunk(
    id=uuid4(),
    source_id=uuid4(),
    tenant_id=tenant.tenant_id,
    jurisdiction=tenant.jurisdiction,
    chunk_index=0,
    content="ACME Corp is in London. Alice works at ACME Corp.",
)


async def main():
    extractor = LiteLLMEntityExtractor()
    result = await extractor.extract([chunk], tenant)
    return result


result = asyncio.run(main())
spans = exporter.get_finished_spans()
assert len(spans) >= 1, "expected at least one span emitted"

# The first span is the extract span (one model call per chunk;
# we have one chunk so one span).
span = spans[0]
attrs = dict(span.attributes)

required_keys = {
    "gen_ai.system",
    "gen_ai.request.model",
    "gen_ai.operation.name",
    "tenant.id",
    "tenant.jurisdiction",
    "tenant.cost_attribution_id",
    "gen_ai.cost.input_usd",
    "gen_ai.cost.output_usd",
    "gen_ai.cost.total_usd",
    "gen_ai.cost.pricing_status",
    "gen_ai.response.model",
}

missing = required_keys - set(attrs.keys())
assert not missing, f"missing span attributes: {sorted(missing)}; got {sorted(attrs.keys())}"

assert attrs["gen_ai.system"] == "litellm"
assert attrs["gen_ai.operation.name"] == "extract"
assert attrs["tenant.id"] == tenant.tenant_id
assert attrs["tenant.jurisdiction"] == tenant.jurisdiction

# Token counts must be present for table_hit; if absent the path
# lands as extraction_no_token_count.
status = attrs["gen_ai.cost.pricing_status"]
assert status in {"table_hit", "extraction_no_token_count", "unknown_model"}, status

if status == "table_hit":
    assert "gen_ai.usage.input_tokens" in attrs
    assert "gen_ai.usage.output_tokens" in attrs

# Extraction produced at least one entity (the chunk mentions
# ACME Corp and Alice) — Qwen 2.5 7B via JSON mode is reliable
# enough at this scale to surface at least one entity.
assert len(result.entities) >= 1, (
    f"expected at least one entity from extraction; got {result!r}"
)

print(json.dumps({
    "operation": attrs["gen_ai.operation.name"],
    "pricing_status": status,
    "entities": len(result.entities),
    "relationships": len(result.relationships),
}))
"""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "padhanam-api",
            "python",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, (
        f"unexpected exit {result.returncode}: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
