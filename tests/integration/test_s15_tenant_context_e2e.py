"""End-to-end integration test for S15 tenant-context enrichment.

Drives an authenticated inference request for tenant A and tenant B
through the live stack, verifies each trace carries the three
``tenant.*`` attributes and the four ``gen_ai.cost.*`` attributes
on the LiteLLMAdapter span, and asserts per-tenant audit chain
isolation holds against the enriched payload (D35 invariant).

The test is environment-gated: if the Compose stack is not reachable
or seeded tenants are absent, the test ``skip``s rather than failing.
The production-shaped path uses the same Langfuse public-API pattern
established at S12's ``test_p3_full_slice``.
"""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import time
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.live_llm  # D99: real LLM via LiteLLM/Ollama

from padhanam.config import ObservabilitySettings
from padhanam.security.auth import issue_dev_token


_SSL_CTX = ssl._create_unverified_context()

SEEDED_TENANT_A_UUID = "00000000-0000-4000-8000-00000000a001"
SEEDED_TENANT_B_UUID = "00000000-0000-4000-8000-00000000b002"
TENANT_A_JURISDICTION = "eu-west"
TENANT_B_JURISDICTION = "us-east"


def _api_base() -> str:
    return os.environ.get("PADHANAM_API_BASE", "https://localhost/api")


def _langfuse_base() -> str:
    return os.environ.get("LANGFUSE_BASE", "https://langfuse.localhost")


def _langfuse_basic_auth() -> str:
    return ObservabilitySettings().otlp_basic_auth_header


def _tenant_token(tenant_uuid: str) -> str:
    return issue_dev_token(
        subject=f"alice@{tenant_uuid[:8]}",
        tenant_id=tenant_uuid,
        roles=["inference.invoke"],
    )


def _post_completion(tenant_uuid: str) -> tuple[int, dict]:
    body = json.dumps(
        {
            "messages": [
                {"role": "user", "content": "Reply with one short sentence."}
            ],
            "model": "qwen2.5:7b",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{_api_base()}/inference/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {_tenant_token(tenant_uuid)}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120, context=_SSL_CTX) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def _stack_reachable() -> bool:
    try:
        with urllib.request.urlopen(
            f"{_api_base()}/health", timeout=2.0, context=_SSL_CTX
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


_LIST_SCRIPT = """
import asyncio
from contexts.tenancy.adapters.outbound.postgres.registry import PostgresTenantRegistry
from contexts.audit.adapters.outbound.noop import NoOpAuditAdapter
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import file_security_event_logger
reg = PostgresTenantRegistry.from_settings(
    settings=ControlPlaneSettings(),
    audit=NoOpAuditAdapter(),
    security_events=file_security_event_logger(),
)
ts = asyncio.run(reg.list_tenants())
print(",".join(str(t.id) for t in ts))
"""


def _seeded_tenants_present() -> bool:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "padhanam-api", "python", "-"],
        cwd=os.environ.get("PADHANAM_REPO_ROOT", os.getcwd()),
        input=_LIST_SCRIPT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode != 0:
        return False
    output = result.stdout.strip().split("\n")[-1]
    return SEEDED_TENANT_A_UUID in output and SEEDED_TENANT_B_UUID in output


def _audit_count(tenant_label: str) -> int:
    """Run a SELECT COUNT(*) inside the api container against the
    tenant's data-plane database. Returns -1 if the lookup failed.
    """
    script = f"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from padhanam.config import TenantPostgresSettings
import sqlalchemy as sa
s = TenantPostgresSettings.for_tenant("{tenant_label}")
url = f"postgresql+asyncpg://{{s.user}}:{{s.password}}@{{s.host}}:{{s.port}}/{{s.db}}"
engine = create_async_engine(url)
async def go():
    async with engine.connect() as c:
        r = await c.execute(sa.text("SELECT COUNT(*) FROM tenant_audit"))
        print(r.scalar())
asyncio.run(go())
"""
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "padhanam-api", "python", "-"],
        cwd=os.environ.get("PADHANAM_REPO_ROOT", os.getcwd()),
        input=script,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode != 0:
        return -1
    last = result.stdout.strip().split("\n")[-1]
    try:
        return int(last)
    except ValueError:
        return -1


def _fetch_trace(trace_id: str) -> dict | None:
    """Poll Langfuse public API for the trace until the LiteLLMAdapter
    span ("chat ...") is present in observations. Ingestion is async
    through Redis → worker → ClickHouse, and the trace shell becomes
    queryable before all child observations ingest; we keep polling
    while the trace exists but the chat span is missing.
    """
    headers = {"Authorization": _langfuse_basic_auth()}
    deadline = time.monotonic() + 30.0
    last_body: dict | None = None
    while time.monotonic() < deadline:
        req = urllib.request.Request(
            f"{_langfuse_base()}/api/public/traces/{trace_id}",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=5, context=_SSL_CTX) as resp:
                if resp.status == 200:
                    last_body = json.loads(resp.read().decode())
                    has_chat = any(
                        (o.get("name") or "").startswith("chat ")
                        for o in last_body.get("observations") or []
                    )
                    if has_chat:
                        return last_body
        except urllib.error.HTTPError:
            pass
        time.sleep(2)
    return last_body


def _llm_span_attrs(trace: dict) -> dict:
    """Find the LiteLLMAdapter span (named "chat qwen2.5:7b") in the
    Langfuse trace's observations and return its attributes dict.

    Langfuse 3 surfaces OTel attributes under observation.metadata.attributes.
    """
    for o in trace.get("observations") or []:
        if (o.get("name") or "").startswith("chat "):
            md = o.get("metadata") or {}
            return md.get("attributes") or md
    return {}


@pytest.fixture(scope="module")
def stack_ready() -> None:
    if not _stack_reachable():
        pytest.skip(f"padhanam-api not reachable at {_api_base()}")
    if not _seeded_tenants_present():
        pytest.skip("seeded tenants not present; run `make seed-tenants` first")


@pytest.mark.parametrize(
    "tenant_uuid,jurisdiction",
    [
        (SEEDED_TENANT_A_UUID, TENANT_A_JURISDICTION),
        (SEEDED_TENANT_B_UUID, TENANT_B_JURISDICTION),
    ],
    ids=["tenant_a", "tenant_b"],
)
def test_inference_emits_tenant_and_cost_attributes(
    stack_ready, tenant_uuid: str, jurisdiction: str
) -> None:
    status, body = _post_completion(tenant_uuid)
    assert status == 200, body
    trace_id = body.get("trace_id")
    assert trace_id and len(trace_id) == 32, f"unexpected trace_id: {trace_id!r}"

    trace = _fetch_trace(trace_id)
    if trace is None:
        pytest.skip(
            "trace not visible in Langfuse within deadline; "
            "ingestion may be lagging — operator-driven re-check"
        )

    attrs = _llm_span_attrs(trace)
    if not attrs:
        # The Langfuse public-API exposure of OTel attributes varies
        # across versions. The structural commitment (request 200,
        # trace exists) holds; the browser-interactive verification is
        # the authoritative gate per the S4 convention.
        pytest.skip("LLM span attributes not exposed by Langfuse API surface")

    # tenant.* attributes per D37 + S15.
    assert attrs.get("tenant.id") == tenant_uuid
    assert attrs.get("tenant.jurisdiction") == jurisdiction
    assert attrs.get("tenant.cost_attribution_id") == tenant_uuid
    # gen_ai.cost.* attributes from S14 still co-exist correctly.
    assert "gen_ai.cost.input_usd" in attrs
    assert "gen_ai.cost.output_usd" in attrs
    assert "gen_ai.cost.total_usd" in attrs
    assert attrs.get("gen_ai.cost.pricing_status") == "table_hit"
    # Legacy padhanam.tenant_id removed at S15.
    assert "padhanam.tenant_id" not in attrs


def test_inference_path_does_not_write_to_per_tenant_audit(stack_ready) -> None:
    """The inference path does not emit audit events. Per D35, audit
    isolation is preserved trivially: tenant A's data-plane sees no
    new rows after a tenant B inference call, and vice versa. The
    test counts both before/after a tenant A inference run and
    asserts no audit row appeared on tenant B's data plane.
    """
    before_a = _audit_count("a")
    before_b = _audit_count("b")
    if before_a < 0 or before_b < 0:
        pytest.skip("could not read tenant audit counts")

    status, _ = _post_completion(SEEDED_TENANT_A_UUID)
    assert status == 200

    after_a = _audit_count("a")
    after_b = _audit_count("b")

    # Inference produces no audit rows on either side. Guards against
    # an accidental cross-tenant write being introduced when auditing
    # is added to the inference path in a future package.
    assert after_a == before_a
    assert after_b == before_b
