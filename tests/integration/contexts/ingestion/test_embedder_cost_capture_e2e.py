"""End-to-end cost-capture verification for the LiteLLM embedder
adapter (S20 / D62).

Drives the ``LiteLLMChunkEmbedder`` against the live LiteLLM gateway
→ Ollama-served ``nomic-embed-text:v1.5`` and captures the emitted
OTel span via an in-process InMemorySpanExporter. Asserts the cost-
attribution surface lands the same shape the chat adapter lands at
S15: tenant.* attributes, gen_ai.* attributes including the operation
name and the usage token count, and the four gen_ai.cost.* attributes
including pricing_status.

The unit test ``tests/unit/contexts/ingestion/test_litellm_embedder``
verifies the adapter's behaviour against mocked LiteLLM responses;
this test verifies the gateway integration delivers the expected
shape under real Ollama inference. The S20 reconciliation finding
(LiteLLM may or may not populate gen_ai.usage.input_tokens for
Ollama-served embeddings) lands as a passing assertion here when
LiteLLM's local tokenizer does populate the count, or as the
documented attribution gap surfaced via
gen_ai.cost.pricing_status='embedding_no_token_count' when it
doesn't. Either outcome is honest about the actual integration.

Skip discriminator: docker compose reachable + litellm + ollama
healthy.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from uuid import uuid4

import pytest

from contexts.ingestion.adapters.outbound.embedding import (
    LiteLLMChunkEmbedder,
)
from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from shared_kernel import TenantContext
from padhanam.config import InferenceSettings


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


def _service_health(probe_url: str) -> bool:
    """Probe a service from inside the padhanam-api container via stdlib
    urllib (LiteLLM and Ollama do not ship curl)."""
    probe = (
        "import urllib.request, sys\n"
        "try:\n"
        f"    sys.exit(0 if urllib.request.urlopen({probe_url!r}, timeout=5).status == 200 else 1)\n"
        "except Exception:\n"
        "    sys.exit(1)\n"
    )
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "padhanam-api",
                "python",
                "-c",
                probe,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


@pytest.fixture(scope="module")
def stack_ready() -> None:
    if not _docker_available():
        pytest.skip("docker compose not reachable from test environment")
    services_run = subprocess.run(
        ["docker", "compose", "ps", "--services", "--filter", "status=running"],
        capture_output=True,
        text=True,
        check=False,
    )
    running = set(services_run.stdout.split())
    needed = {"padhanam-api", "litellm", "ollama"}
    if not needed.issubset(running):
        missing = needed - running
        pytest.skip(f"compose services not running: {sorted(missing)}")
    if not _service_health("http://ollama:11434/api/tags"):
        pytest.skip("ollama health probe failed; live embed path unreachable")
    if not _service_health("http://litellm:4000/health/liveliness"):
        pytest.skip("litellm health probe failed; live embed path unreachable")


_TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)


def _chunk(content: str) -> Chunk:
    return Chunk(
        id=uuid4(),
        source_id=uuid4(),
        tenant_id=_TENANT_A.tenant_id,
        jurisdiction=_TENANT_A.jurisdiction,
        chunk_index=0,
        content=content,
    )


def test_live_embed_call_emits_full_cost_attribution_shape(
    stack_ready: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live LiteLLM → Ollama embed call. Captures the OTel span via
    in-memory exporter and asserts the four cost.* attributes plus
    the three tenant.* attributes plus operation-name + model land
    on the span the same way the chat adapter lands them.

    The test runs from the host (not inside the container) because
    the gateway endpoint resolves at the host through caddy at
    https://litellm.localhost — but the test directly targets the
    Compose-internal http://litellm:4000 via the test's own
    InferenceSettings. To make the host reach the internal port,
    the test runs INSIDE the padhanam-api container via
    docker compose exec, which is the same shape S17a/S17b
    established for live e2e tests.
    """
    # The script runs inside padhanam-api so http://litellm:4000
    # resolves over the Compose network. Captures spans via in-
    # process InMemorySpanExporter, returns the captured span
    # attributes as JSON for assertion.
    script = """
import asyncio
import json
import os
import sys
from uuid import uuid4

# Ensure InferenceSettings finds the master key from the container
# environment (compose.yaml passes LITELLM_MASTER_KEY through).
assert os.environ.get("LITELLM_MASTER_KEY"), "master key missing"

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from contexts.ingestion.adapters.outbound.embedding import (
    LiteLLMChunkEmbedder,
)
from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.embedding_task import EmbeddingTask
from shared_kernel import TenantContext

# Replace the embedder module's tracer with the in-memory one.
exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
test_tracer = provider.get_tracer("test")

from contexts.ingestion.adapters.outbound.embedding import (
    litellm_embedder as embedder_module,
)
embedder_module._tracer = test_tracer


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
    content="hello cost world",
)

embedder = LiteLLMChunkEmbedder()

async def run():
    embeddings = await embedder.embed([chunk], tenant, EmbeddingTask.DOCUMENT)
    return len(embeddings), len(embeddings[0].vector)

count, dim = asyncio.run(run())

spans = exporter.get_finished_spans()
assert len(spans) == 1, f"expected 1 span, got {len(spans)}"
span = spans[0]
attrs = dict(span.attributes)
attrs["__span_name"] = span.name
attrs["__embedding_count"] = count
attrs["__vector_dim"] = dim
print(json.dumps(attrs))
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
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, (
        f"in-container script failed (exit {result.returncode}):\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    import json
    # Last stdout line is the JSON payload.
    payload_line = result.stdout.strip().splitlines()[-1]
    attrs = json.loads(payload_line)

    # Embedding shape: 1 chunk in -> 1 embedding out, 768-dim.
    assert attrs["__embedding_count"] == 1
    assert attrs["__vector_dim"] == 768

    # GenAI semantic-convention attributes per D27.
    assert attrs["__span_name"] == "embeddings nomic-embed-text:v1.5"
    assert attrs["gen_ai.system"] == "litellm"
    assert attrs["gen_ai.operation.name"] == "embeddings"
    assert attrs["gen_ai.request.model"] == "nomic-embed-text:v1.5"
    assert attrs["gen_ai.response.model"] == "nomic-embed-text:v1.5"

    # Tenant.* attributes per D50; per-tenant cost rollup keys off
    # tenant.id and tenant.cost_attribution_id.
    assert attrs["tenant.id"] == _TENANT_A.tenant_id
    assert attrs["tenant.jurisdiction"] == _TENANT_A.jurisdiction
    assert attrs["tenant.cost_attribution_id"] == _TENANT_A.cost_attribution_id

    # Cost attribution per D41 / D49. Two acceptable outcomes per the
    # S20 reconciliation: (1) LiteLLM populated input_tokens via its
    # local tokenizer for the Ollama-served path → pricing_status=
    # 'table_hit' against the zero-rate row; (2) usage block omitted
    # → pricing_status='embedding_no_token_count'. Both are honest
    # about the integration's actual behaviour. Total USD is zero
    # either way (Ollama-hosted dev model at zero rates per D62).
    assert attrs["gen_ai.cost.pricing_status"] in (
        "table_hit",
        "embedding_no_token_count",
    )
    assert attrs["gen_ai.cost.total_usd"] == 0.0
    assert attrs["gen_ai.cost.input_usd"] == 0.0
    assert attrs["gen_ai.cost.output_usd"] == 0.0

    # When LiteLLM populated the token count, the input_tokens
    # attribute lands on the span. When it didn't, the attribute is
    # absent (the adapter does not fabricate zero); the
    # pricing_status flag carries the gap signal.
    if attrs["gen_ai.cost.pricing_status"] == "table_hit":
        assert "gen_ai.usage.input_tokens" in attrs
        assert attrs["gen_ai.usage.input_tokens"] >= 1


def test_cost_for_helper_handles_embedding_model_lookup() -> None:
    """Per D62: nomic-embed-text:v1.5 lands in PRICING_TABLE so cost
    queries against the embedding model resolve cleanly. The chat
    adapter's cost_for() helper lives in padhanam.config.inference;
    embedding cost flows through the same helper. This unit-shaped
    test verifies the helper does not raise UnknownModelError for
    the embedding model — the same architectural surface the chat
    path uses works for the embedding path.
    """
    from padhanam.config import cost_for

    breakdown = cost_for("nomic-embed-text:v1.5", input_tokens=100, output_tokens=0)
    # Zero rates per D62 (Ollama-hosted dev model). The structure is
    # what matters; the values are the honest dev-cost numbers.
    assert breakdown.input_usd == 0
    assert breakdown.output_usd == 0
    assert breakdown.total_usd == 0
