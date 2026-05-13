"""Unit tests for the agent run SSE consumer (S30b commit 2, D90).

Three concern areas:

1. SSE wire-format parsing — ``parse_sse_block`` and ``parse_sse_body``
   against the exact wire format produced by
   ``apps/api/adapters/sse_event_translator.py``.

2. Per-event-type rendering — each of the eleven D90 event types
   exercises its renderer; assertions check the rendered text carries
   the load-bearing fields.

3. Exit-code mapping — the three terminal-event types map to the
   correct CLI exit codes per D90.

The end-to-end CLI invocation is the integration test at
``tests/integration/apps/cli/test_agent_run_e2e.py``; this module stays
on the pure-Python parser and renderer surface.
"""

from __future__ import annotations

import io
import json

import pytest

from apps.cli._agent_run import (
    EXIT_FAILED,
    EXIT_INVARIANT_BLOCKED,
    EXIT_SUCCESS,
    ParsedEvent,
    StreamRenderer,
    parse_sse_block,
    parse_sse_body,
    render_events_to_string,
)


# ---------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------


def _sse_block(event_type: str, data: dict) -> str:
    """Build a single SSE block in the wire format from sse_event_translator."""
    data_json = json.dumps(data, separators=(",", ":"))
    return f"event: {event_type}\ndata: {data_json}\n\n"


def test_parse_sse_block_returns_event_for_valid_block() -> None:
    block = "event: InvocationStarted\ndata: {\"invocation_id\":\"abc\"}"
    parsed = parse_sse_block(block)
    assert parsed is not None
    assert parsed.event_type == "InvocationStarted"
    assert parsed.data == {"invocation_id": "abc"}


def test_parse_sse_block_returns_none_for_block_with_no_event_line() -> None:
    block = "data: {\"foo\":1}"
    assert parse_sse_block(block) is None


def test_parse_sse_block_returns_none_for_block_with_no_data_line() -> None:
    block = "event: ContentDelta"
    assert parse_sse_block(block) is None


def test_parse_sse_block_returns_none_when_data_is_not_json_object() -> None:
    block = "event: Foo\ndata: \"just a string\""
    assert parse_sse_block(block) is None


def test_parse_sse_block_returns_none_when_data_is_malformed_json() -> None:
    block = "event: Foo\ndata: {not json"
    assert parse_sse_block(block) is None


def test_parse_sse_body_parses_multiple_blocks_in_order() -> None:
    body = (
        _sse_block("InvocationStarted", {"agent_template_id": "a"})
        + _sse_block("ContentDelta", {"text_fragment": "hello"})
        + _sse_block("InvocationCompleted", {"termination_reason": "content"})
    )
    parsed = parse_sse_body(body)
    assert [e.event_type for e in parsed] == [
        "InvocationStarted",
        "ContentDelta",
        "InvocationCompleted",
    ]
    assert parsed[1].data["text_fragment"] == "hello"


def test_parse_sse_body_ignores_blank_blocks_at_seams() -> None:
    body = (
        "\n\n"
        + _sse_block("InvocationStarted", {"agent_template_id": "a"})
        + "\n\n"
        + _sse_block("InvocationCompleted", {"termination_reason": "content"})
    )
    parsed = parse_sse_body(body)
    assert len(parsed) == 2


# ---------------------------------------------------------------------
# Per-event rendering
# ---------------------------------------------------------------------


def _render_one(event_type: str, data: dict, *, user_input: str = "test-input") -> str:
    rendered, _exit_code = render_events_to_string(
        [ParsedEvent(event_type=event_type, data=data)],
        user_input=user_input,
    )
    return rendered


def test_renders_invocation_started_with_agent_tenant_model_and_input_echo() -> None:
    rendered = _render_one(
        "InvocationStarted",
        {
            "agent_template_id": "agent-xyz",
            "tenant_context": {"tenant_id": "tenant-alpha"},
            "model_name": "qwen2.5:7b",
        },
        user_input="frame this for me",
    )
    assert "agent=agent-xyz" in rendered
    assert "tenant=tenant-alpha" in rendered
    assert "model=qwen2.5:7b" in rendered
    assert "[input] frame this for me" in rendered


def test_renders_iteration_started_with_index() -> None:
    rendered = _render_one("IterationStarted", {"iteration_index": 3})
    assert "[iteration 3]" in rendered


def test_renders_llm_call_started_with_message_count() -> None:
    rendered = _render_one(
        "LLMCallStarted",
        {"iteration_index": 1, "model_name": "x", "message_count": 7},
    )
    assert "generating" in rendered.lower()
    assert "message_count=7" in rendered


def test_renders_content_delta_without_newline_so_deltas_accumulate() -> None:
    body = "".join(
        _render_one("ContentDelta", {"text_fragment": frag})
        for frag in ("Hello ", "world", "!")
    )
    # Each delta should land verbatim with no separator characters.
    assert "Hello world!" in body


def test_renders_tool_call_proposed_with_name_arguments_and_classification() -> None:
    rendered = _render_one(
        "ToolCallProposed",
        {
            "iteration_index": 1,
            "tool_name": "retrieve",
            "arguments": "{\"query\":\"vision\"}",
            "classification": "read-only",
        },
    )
    assert "retrieve" in rendered
    assert "read-only" in rendered
    assert "\"query\":\"vision\"" in rendered


def test_renders_tool_call_executing_with_tool_name() -> None:
    rendered = _render_one(
        "ToolCallExecuting", {"tool_name": "retrieve", "iteration_index": 1}
    )
    assert "executing" in rendered.lower()
    assert "retrieve" in rendered


def test_renders_tool_call_completed_with_success_status_and_summary() -> None:
    rendered = _render_one(
        "ToolCallCompleted",
        {
            "iteration_index": 1,
            "tool_name": "retrieve",
            "success": True,
            "result_summary": "3 chunks",
            "duration_ms": 42,
        },
    )
    assert "ok" in rendered.lower()
    assert "3 chunks" in rendered
    assert "duration_ms=42" in rendered


def test_renders_tool_call_completed_marks_error_on_failure() -> None:
    rendered = _render_one(
        "ToolCallCompleted",
        {
            "iteration_index": 1,
            "tool_name": "retrieve",
            "success": False,
            "result_summary": "tool errored",
            "duration_ms": 7,
        },
    )
    assert "ERROR" in rendered


def test_renders_iteration_completed_with_signal_duration_cost() -> None:
    rendered = _render_one(
        "IterationCompleted",
        {
            "iteration_index": 2,
            "termination_signal": "continue",
            "duration_ms": 1500,
            "cost_usd": "0.0012",
        },
    )
    assert "iteration 2 done" in rendered
    assert "signal=continue" in rendered
    assert "duration_ms=1500" in rendered
    assert "cost_usd=0.0012" in rendered


def test_renders_invocation_completed_with_reason_iterations_cost() -> None:
    # Two IterationCompleted events precede the terminal so the count is 2.
    events = [
        ParsedEvent(
            "IterationCompleted",
            {
                "iteration_index": 1,
                "termination_signal": "continue",
                "duration_ms": 100,
                "cost_usd": "0.001",
            },
        ),
        ParsedEvent(
            "IterationCompleted",
            {
                "iteration_index": 2,
                "termination_signal": "content",
                "duration_ms": 200,
                "cost_usd": "0.002",
            },
        ),
        ParsedEvent(
            "InvocationCompleted",
            {
                "termination_reason": "content",
                "total_cost_usd": "0.003",
                "duration_ms": 500,
                "final_result": "answer",
                "audit_chain_hashes": ["a" * 64, "b" * 64],
            },
        ),
    ]
    rendered, exit_code = render_events_to_string(events, user_input="x")
    assert "termination_reason=content" in rendered
    assert "iterations=2" in rendered
    assert "total_cost_usd=0.003" in rendered
    assert "duration_ms=500" in rendered
    assert exit_code == EXIT_SUCCESS


def test_renders_invocation_failed_with_error_type_and_detail() -> None:
    rendered = _render_one(
        "InvocationFailed",
        {
            "error_type": "TimeoutError",
            "error_detail": "LLM gateway timed out",
            "duration_ms": 30000,
            "partial_audit_chain_state": ["a" * 64],
        },
    )
    assert "FAILED" in rendered
    assert "TimeoutError" in rendered
    assert "LLM gateway timed out" in rendered


def test_renders_invariant_blocked_with_classification_and_tool() -> None:
    rendered = _render_one(
        "InvariantBlocked",
        {
            "classification": "financial",
            "blocked_tool_name": "stripe_charge",
            "audit_chain_hashes": ["a" * 64, "b" * 64],
        },
    )
    assert "BLOCKED" in rendered
    assert "financial" in rendered
    assert "stripe_charge" in rendered


def test_unknown_event_type_does_not_crash_renderer() -> None:
    # Forward compatibility: a future event type the CLI does not
    # know about should be silently skipped, not crash the run.
    rendered = _render_one("FutureEventType", {"foo": "bar"})
    assert rendered == ""


# ---------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------


def test_exit_code_is_success_when_terminal_is_invocation_completed() -> None:
    events = [
        ParsedEvent("InvocationStarted", {"agent_template_id": "a"}),
        ParsedEvent(
            "InvocationCompleted",
            {
                "termination_reason": "content",
                "total_cost_usd": "0.001",
                "duration_ms": 100,
                "final_result": "x",
                "audit_chain_hashes": ["a", "b"],
            },
        ),
    ]
    _rendered, exit_code = render_events_to_string(events, user_input="x")
    assert exit_code == EXIT_SUCCESS


def test_exit_code_is_failed_when_terminal_is_invocation_failed() -> None:
    events = [
        ParsedEvent("InvocationStarted", {"agent_template_id": "a"}),
        ParsedEvent(
            "InvocationFailed",
            {
                "error_type": "X",
                "error_detail": "y",
                "duration_ms": 1,
                "partial_audit_chain_state": [],
            },
        ),
    ]
    _rendered, exit_code = render_events_to_string(events, user_input="x")
    assert exit_code == EXIT_FAILED


def test_exit_code_is_invariant_blocked_when_terminal_is_invariant_blocked() -> None:
    events = [
        ParsedEvent("InvocationStarted", {"agent_template_id": "a"}),
        ParsedEvent(
            "InvariantBlocked",
            {
                "classification": "financial",
                "blocked_tool_name": "stripe_charge",
                "audit_chain_hashes": ["a", "b"],
            },
        ),
    ]
    _rendered, exit_code = render_events_to_string(events, user_input="x")
    assert exit_code == EXIT_INVARIANT_BLOCKED


def test_exit_code_is_failed_when_stream_ends_without_terminal_event() -> None:
    # Protocol failure: the stream ended mid-iteration.
    events = [
        ParsedEvent("InvocationStarted", {"agent_template_id": "a"}),
        ParsedEvent("IterationStarted", {"iteration_index": 1}),
    ]
    _rendered, exit_code = render_events_to_string(events, user_input="x")
    assert exit_code == EXIT_FAILED


# ---------------------------------------------------------------------
# Tee-style output capture
# ---------------------------------------------------------------------


def test_tee_writer_writes_to_both_primary_and_secondary_streams() -> None:
    primary = io.StringIO()
    secondary = io.StringIO()
    renderer = StreamRenderer(
        writer=primary, user_input="x", output_file=secondary
    )
    renderer.consume(
        ParsedEvent(
            "ContentDelta", {"iteration_index": 1, "text_fragment": "hello"}
        )
    )
    assert primary.getvalue() == "hello"
    assert secondary.getvalue() == "hello"
