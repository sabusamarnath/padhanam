"""End-to-end integration tests for ``padhanam agent run`` (S30b, D90).

The agent run subcommand consumes the SSE endpoint at
``POST /agents/{agent_id}/invoke`` per D90. These tests drive the full
CLI surface (Typer dispatcher + ``run_invocation`` coroutine + SSE
parser + StreamRenderer) against a fake SSE endpoint served by
``httpx.MockTransport``. The fake serves canned SSE wire data in the
exact format produced by ``apps/api/adapters/sse_event_translator.py``,
so the tests verify the round-trip: domain events → SSE wire →
renderer output.

Skipped at the live-stack-shaped tests in ``test_invoke_agent_end_to_end``
(which exec inside the padhanam-api container against the live LLM
gateway); this module stays on the CLI ↔ SSE wire format surface so it
runs in unit-test time without Docker.
"""

from __future__ import annotations

import asyncio
import io
import json
from typing import Iterator

import httpx
import pytest

from apps.cli._agent_run import (
    EXIT_FAILED,
    EXIT_INVARIANT_BLOCKED,
    EXIT_SUCCESS,
    run_invocation,
)


_AGENT_ID = "00000000-0000-4000-8000-0000000000aa"


def _sse_block(event_type: str, data: dict) -> bytes:
    """Build a single SSE block in the wire format from sse_event_translator."""
    data_json = json.dumps(data, separators=(",", ":"))
    return f"event: {event_type}\ndata: {data_json}\n\n".encode("utf-8")


def _make_factory(
    *,
    expected_path: str,
    response_chunks: list[bytes],
    expected_user_input: str,
    response_status: int = 200,
    request_seen: dict | None = None,
):
    """Build an http_client_factory that serves canned SSE chunks.

    Captures the request shape so tests can assert the body and headers.
    """
    body_bytes = b"".join(response_chunks)

    def handler(request: httpx.Request) -> httpx.Response:
        if request_seen is not None:
            request_seen["method"] = request.method
            request_seen["url"] = str(request.url)
            request_seen["headers"] = dict(request.headers)
            request_seen["content"] = request.content.decode("utf-8")
        assert request.url.path == expected_path
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["user_input"] == expected_user_input
        return httpx.Response(
            status_code=response_status,
            headers={"content-type": "text/event-stream"},
            content=body_bytes,
        )

    transport = httpx.MockTransport(handler)

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, timeout=None)

    return factory


def test_happy_path_renders_events_and_returns_exit_zero() -> None:
    chunks = [
        _sse_block(
            "InvocationStarted",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "agent_template_id": _AGENT_ID,
                "tenant_context": {
                    "tenant_id": "00000000-0000-4000-8000-00000000a001",
                    "jurisdiction": "eu-west",
                    "cost_attribution_id": "00000000-0000-4000-8000-00000000a001",
                },
                "model_name": "qwen2.5:7b",
                "started_at": "2026-05-13T10:00:00+00:00",
            },
        ),
        _sse_block(
            "IterationStarted",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "iteration_index": 1,
                "started_at": "2026-05-13T10:00:00+00:00",
            },
        ),
        _sse_block(
            "ContentDelta",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "iteration_index": 1,
                "text_fragment": "Hello ",
            },
        ),
        _sse_block(
            "ContentDelta",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "iteration_index": 1,
                "text_fragment": "world",
            },
        ),
        _sse_block(
            "IterationCompleted",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "iteration_index": 1,
                "termination_signal": "content",
                "duration_ms": 1000,
                "cost_usd": "0.001",
            },
        ),
        _sse_block(
            "InvocationCompleted",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "final_result": "Hello world",
                "termination_reason": "content",
                "total_cost_usd": "0.001",
                "audit_chain_hashes": ["a" * 64, "b" * 64],
                "duration_ms": 1500,
            },
        ),
    ]
    request_seen: dict = {}
    factory = _make_factory(
        expected_path=f"/agents/{_AGENT_ID}/invoke",
        response_chunks=chunks,
        expected_user_input="frame this for me",
        request_seen=request_seen,
    )

    writer = io.StringIO()
    exit_code = asyncio.run(
        run_invocation(
            tenant_label="a",
            agent_id=_AGENT_ID,
            user_input="frame this for me",
            api_url="http://stub:8000",
            writer=writer,
            http_client_factory=factory,
        )
    )

    assert exit_code == EXIT_SUCCESS
    rendered = writer.getvalue()
    # Renderer fingerprints across the eight events.
    assert "[invocation]" in rendered
    assert f"agent={_AGENT_ID}" in rendered
    assert "[input] frame this for me" in rendered
    assert "[iteration 1]" in rendered
    assert "Hello world" in rendered
    assert "iterations=1" in rendered
    assert "total_cost_usd=0.001" in rendered

    # Wire-side assertions: the bearer token reached the endpoint, and
    # the body shape matches what the API router expects.
    assert request_seen["headers"]["authorization"].startswith("Bearer ")
    assert json.loads(request_seen["content"]) == {
        "user_input": "frame this for me"
    }


def test_invariant_blocked_stream_returns_exit_code_two() -> None:
    chunks = [
        _sse_block(
            "InvocationStarted",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "agent_template_id": _AGENT_ID,
                "tenant_context": {
                    "tenant_id": "00000000-0000-4000-8000-00000000a001",
                    "jurisdiction": "eu-west",
                    "cost_attribution_id": "00000000-0000-4000-8000-00000000a001",
                },
                "model_name": "qwen2.5:7b",
                "started_at": "2026-05-13T10:00:00+00:00",
            },
        ),
        _sse_block(
            "InvariantBlocked",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "classification": "financial",
                "blocked_tool_name": "stripe_charge",
                "audit_chain_hashes": ["a" * 64, "b" * 64],
            },
        ),
    ]
    factory = _make_factory(
        expected_path=f"/agents/{_AGENT_ID}/invoke",
        response_chunks=chunks,
        expected_user_input="charge the card",
    )
    writer = io.StringIO()
    exit_code = asyncio.run(
        run_invocation(
            tenant_label="a",
            agent_id=_AGENT_ID,
            user_input="charge the card",
            api_url="http://stub:8000",
            writer=writer,
            http_client_factory=factory,
        )
    )
    assert exit_code == EXIT_INVARIANT_BLOCKED
    rendered = writer.getvalue()
    assert "BLOCKED" in rendered
    assert "financial" in rendered
    assert "stripe_charge" in rendered


def test_invocation_failed_stream_returns_exit_code_one() -> None:
    chunks = [
        _sse_block(
            "InvocationStarted",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "agent_template_id": _AGENT_ID,
                "tenant_context": {
                    "tenant_id": "00000000-0000-4000-8000-00000000a001",
                    "jurisdiction": "eu-west",
                    "cost_attribution_id": "00000000-0000-4000-8000-00000000a001",
                },
                "model_name": "qwen2.5:7b",
                "started_at": "2026-05-13T10:00:00+00:00",
            },
        ),
        _sse_block(
            "InvocationFailed",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "error_type": "TimeoutError",
                "error_detail": "LLM gateway timed out",
                "partial_audit_chain_state": ["a" * 64],
                "duration_ms": 30000,
            },
        ),
    ]
    factory = _make_factory(
        expected_path=f"/agents/{_AGENT_ID}/invoke",
        response_chunks=chunks,
        expected_user_input="frame this",
    )
    writer = io.StringIO()
    exit_code = asyncio.run(
        run_invocation(
            tenant_label="a",
            agent_id=_AGENT_ID,
            user_input="frame this",
            api_url="http://stub:8000",
            writer=writer,
            http_client_factory=factory,
        )
    )
    assert exit_code == EXIT_FAILED
    assert "TimeoutError" in writer.getvalue()


def test_http_error_response_returns_exit_failed_and_renders_body() -> None:
    factory = _make_factory(
        expected_path=f"/agents/{_AGENT_ID}/invoke",
        response_chunks=[b'{"detail": "agent runtime not configured"}'],
        expected_user_input="x",
        response_status=503,
    )
    writer = io.StringIO()
    exit_code = asyncio.run(
        run_invocation(
            tenant_label="a",
            agent_id=_AGENT_ID,
            user_input="x",
            api_url="http://stub:8000",
            writer=writer,
            http_client_factory=factory,
        )
    )
    assert exit_code == EXIT_FAILED
    assert "http_status=503" in writer.getvalue()


def test_tee_writes_rendered_stream_to_output_file(
    tmp_path,
) -> None:
    chunks = [
        _sse_block(
            "InvocationStarted",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "agent_template_id": _AGENT_ID,
                "tenant_context": {
                    "tenant_id": "00000000-0000-4000-8000-00000000a001",
                    "jurisdiction": "eu-west",
                    "cost_attribution_id": "00000000-0000-4000-8000-00000000a001",
                },
                "model_name": "qwen2.5:7b",
                "started_at": "2026-05-13T10:00:00+00:00",
            },
        ),
        _sse_block(
            "ContentDelta",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "iteration_index": 1,
                "text_fragment": "captured-output",
            },
        ),
        _sse_block(
            "InvocationCompleted",
            {
                "invocation_id": "00000000-0000-4000-8000-0000000000ff",
                "final_result": "captured-output",
                "termination_reason": "content",
                "total_cost_usd": "0.0",
                "audit_chain_hashes": ["a" * 64, "b" * 64],
                "duration_ms": 100,
            },
        ),
    ]
    factory = _make_factory(
        expected_path=f"/agents/{_AGENT_ID}/invoke",
        response_chunks=chunks,
        expected_user_input="x",
    )
    output_path = tmp_path / "demo_output.md"
    writer = io.StringIO()
    exit_code = asyncio.run(
        run_invocation(
            tenant_label="a",
            agent_id=_AGENT_ID,
            user_input="x",
            api_url="http://stub:8000",
            output_file=output_path,
            writer=writer,
            http_client_factory=factory,
        )
    )
    assert exit_code == EXIT_SUCCESS
    file_text = output_path.read_text(encoding="utf-8")
    # Tee: both stdout-stand-in and output file see the same content.
    assert "captured-output" in writer.getvalue()
    assert "captured-output" in file_text


# ---------------------------------------------------------------------
# Typer CliRunner surface — the run subcommand is wired in
# ---------------------------------------------------------------------


def test_agent_run_subcommand_is_registered_in_help() -> None:
    from typer.testing import CliRunner

    from apps.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["agent", "--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout


def test_agent_run_help_documents_options() -> None:
    from typer.testing import CliRunner

    from apps.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["agent", "run", "--help"])
    assert result.exit_code == 0
    assert "--tenant" in result.stdout
    assert "--agent" in result.stdout
    assert "--input" in result.stdout
    assert "--api-url" in result.stdout
    assert "--output-file" in result.stdout
