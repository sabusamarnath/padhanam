"""SSE-consuming agent run subcommand support (S30b, D90).

The ``padhanam agent run`` Typer subcommand (registered at
``apps/cli/_agent.py``) is the first product-form transport consumer of
the SSE endpoint at ``POST /agents/{agent_id}/invoke``. This module owns
the wire-side work: building the dev token, opening the streaming
request, parsing SSE blocks per the wire format produced by
``apps/api/adapters/sse_event_translator.py``, and dispatching each
parsed event to the per-type renderer.

Three architectural shapes worth naming:

1. **Renderers as methods on a stateful consumer.** The renderer needs
   to thread per-stream state (the user-input echo from
   ``InvocationStarted``, an iteration count derived from
   ``IterationCompleted`` events, the terminal event's type for
   exit-code mapping). A free-function renderer table would surface
   the state via globals or argument-threading; a small stateful
   ``_StreamRenderer`` class keeps the state local and the renderers
   tidy.

2. **Pure SSE parser surfaces independently.** ``parse_sse_block``
   takes a single SSE block's text and returns a ``ParsedEvent`` (or
   None); the live path streams lines from ``httpx`` and accumulates
   into blocks at the blank-line boundary. Unit tests exercise the
   parser without httpx.

3. **No new dependency.** ``httpx>=0.27`` is already present; SSE is
   line-oriented over an ordinary HTTP response, so
   ``client.stream("POST", ...).aiter_lines()`` plus a five-line
   accumulator suffices. ``httpx-sse`` and ``sseclient-py`` would add
   no leverage at this wire format.

Exit-code mapping per D90's three terminal-event types:
- ``InvocationCompleted`` → 0
- ``InvariantBlocked`` → 2 (distinguishes from generic failure)
- ``InvocationFailed`` or stream ends without a terminal → 1
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import IO, AsyncIterator, Iterable, Optional

import httpx

from apps.cli._runtime import resolve_tenant_context
from padhanam.security.auth import issue_dev_token


DEFAULT_API_URL = "http://localhost:8000"
EXIT_SUCCESS = 0
EXIT_FAILED = 1
EXIT_INVARIANT_BLOCKED = 2

TERMINAL_EVENT_TYPES: frozenset[str] = frozenset(
    {"InvocationCompleted", "InvocationFailed", "InvariantBlocked"}
)


@dataclass(frozen=True)
class ParsedEvent:
    """One SSE event parsed from the wire."""

    event_type: str
    data: dict


def parse_sse_block(block_text: str) -> Optional[ParsedEvent]:
    """Parse a single SSE block (text between blank-line separators).

    Returns None when the block has no ``event:`` line or no ``data:``
    line (the W3C EventSource spec admits comment-only blocks; we
    skip them rather than error).
    """
    event_type: str | None = None
    data_lines: list[str] = []
    for line in block_text.splitlines():
        if line.startswith("event: "):
            event_type = line[len("event: ") :]
        elif line.startswith("data: "):
            data_lines.append(line[len("data: ") :])
    if event_type is None or not data_lines:
        return None
    payload_text = "".join(data_lines)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return ParsedEvent(event_type=event_type, data=payload)


def parse_sse_body(body: str) -> list[ParsedEvent]:
    """Parse a complete SSE body into a list of events.

    Used by unit tests; production reads lines from httpx incrementally
    via ``_iter_sse_events_from_lines``.
    """
    events: list[ParsedEvent] = []
    for raw_block in body.split("\n\n"):
        if not raw_block.strip():
            continue
        parsed = parse_sse_block(raw_block)
        if parsed is not None:
            events.append(parsed)
    return events


async def _iter_sse_events_from_lines(
    lines: AsyncIterator[str],
) -> AsyncIterator[ParsedEvent]:
    """Accumulate SSE lines into events at blank-line boundaries."""
    event_type: str | None = None
    data_lines: list[str] = []
    async for line in lines:
        if line == "":
            if event_type is not None and data_lines:
                payload_text = "".join(data_lines)
                try:
                    payload = json.loads(payload_text)
                except json.JSONDecodeError:
                    event_type = None
                    data_lines = []
                    continue
                if isinstance(payload, dict):
                    yield ParsedEvent(event_type=event_type, data=payload)
            event_type = None
            data_lines = []
            continue
        if line.startswith("event: "):
            event_type = line[len("event: ") :]
        elif line.startswith("data: "):
            data_lines.append(line[len("data: ") :])


class _TeeWriter:
    """Writer that fans out to a primary stream and an optional file."""

    def __init__(self, primary: IO[str], secondary: IO[str] | None) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, s: str) -> None:
        self._primary.write(s)
        if self._secondary is not None:
            self._secondary.write(s)

    def flush(self) -> None:
        self._primary.flush()
        if self._secondary is not None:
            self._secondary.flush()


class StreamRenderer:
    """Stateful consumer that renders parsed events to a writer.

    The renderer tracks per-stream state (the user-input echo, an
    iteration count derived from ``IterationCompleted``, the terminal
    event for exit-code mapping) so the renderer methods can stay
    method-shaped and the consumer surface stays minimal.
    """

    def __init__(
        self,
        *,
        writer: IO[str],
        user_input: str,
        output_file: IO[str] | None = None,
    ) -> None:
        self._writer = _TeeWriter(writer, output_file)
        self._user_input = user_input
        self._iteration_count = 0
        self._terminal: ParsedEvent | None = None

    @property
    def iteration_count(self) -> int:
        return self._iteration_count

    @property
    def terminal_event(self) -> ParsedEvent | None:
        return self._terminal

    @property
    def exit_code(self) -> int:
        """Map the observed terminal event to a CLI exit code (D90)."""
        if self._terminal is None:
            # Stream ended without a terminal event — protocol failure.
            return EXIT_FAILED
        et = self._terminal.event_type
        if et == "InvocationCompleted":
            return EXIT_SUCCESS
        if et == "InvariantBlocked":
            return EXIT_INVARIANT_BLOCKED
        return EXIT_FAILED

    def consume(self, event: ParsedEvent) -> None:
        if event.event_type == "IterationCompleted":
            self._iteration_count += 1
        if event.event_type in TERMINAL_EVENT_TYPES:
            self._terminal = event

        handler = _DISPATCH.get(event.event_type)
        if handler is None:
            return
        handler(self, event.data)
        self._writer.flush()

    # ------------------------------------------------------------------
    # Per-event renderers. Each takes the event's data dict and writes
    # human-readable text via the renderer's writer. Renderers are
    # registered in the _DISPATCH table below.
    # ------------------------------------------------------------------

    def _render_invocation_started(self, data: dict) -> None:
        tenant = (data.get("tenant_context") or {}).get("tenant_id")
        self._writer.write(
            f"[invocation] agent={data.get('agent_template_id')} "
            f"tenant={tenant} "
            f"model={data.get('model_name')}\n"
        )
        self._writer.write(f"[input] {self._user_input}\n")

    def _render_iteration_started(self, data: dict) -> None:
        self._writer.write(f"\n[iteration {data.get('iteration_index')}]\n")

    def _render_llm_call_started(self, data: dict) -> None:
        self._writer.write(
            f"  generating... (message_count={data.get('message_count')})\n"
        )

    def _render_content_delta(self, data: dict) -> None:
        # Deltas accumulate without a newline so the model's text
        # reconstructs as it streams.
        self._writer.write(data.get("text_fragment", ""))

    def _render_tool_call_proposed(self, data: dict) -> None:
        self._writer.write(
            f"\n  [tool proposed] {data.get('tool_name')} "
            f"({data.get('classification')}) "
            f"arguments={data.get('arguments')}\n"
        )

    def _render_tool_call_executing(self, data: dict) -> None:
        self._writer.write(f"  [tool executing] {data.get('tool_name')}\n")

    def _render_tool_call_completed(self, data: dict) -> None:
        status = "ok" if data.get("success") else "ERROR"
        self._writer.write(
            f"  [tool done] {data.get('tool_name')} status={status} "
            f"duration_ms={data.get('duration_ms')} "
            f"summary={data.get('result_summary')}\n"
        )

    def _render_iteration_completed(self, data: dict) -> None:
        self._writer.write(
            f"\n[iteration {data.get('iteration_index')} done] "
            f"signal={data.get('termination_signal')} "
            f"duration_ms={data.get('duration_ms')} "
            f"cost_usd={data.get('cost_usd')}\n"
        )

    def _render_invocation_completed(self, data: dict) -> None:
        self._writer.write(
            f"\n[invocation done] "
            f"termination_reason={data.get('termination_reason')} "
            f"iterations={self._iteration_count} "
            f"total_cost_usd={data.get('total_cost_usd')} "
            f"duration_ms={data.get('duration_ms')}\n"
        )

    def _render_invocation_failed(self, data: dict) -> None:
        self._writer.write(
            f"\n[invocation FAILED] "
            f"error_type={data.get('error_type')} "
            f"error_detail={data.get('error_detail')} "
            f"duration_ms={data.get('duration_ms')}\n"
        )

    def _render_invariant_blocked(self, data: dict) -> None:
        self._writer.write(
            f"\n[invocation BLOCKED] "
            f"invariant_classification={data.get('classification')} "
            f"blocked_tool={data.get('blocked_tool_name')}\n"
        )


_DISPATCH: dict[str, "callable"] = {
    "InvocationStarted": StreamRenderer._render_invocation_started,
    "IterationStarted": StreamRenderer._render_iteration_started,
    "LLMCallStarted": StreamRenderer._render_llm_call_started,
    "ContentDelta": StreamRenderer._render_content_delta,
    "ToolCallProposed": StreamRenderer._render_tool_call_proposed,
    "ToolCallExecuting": StreamRenderer._render_tool_call_executing,
    "ToolCallCompleted": StreamRenderer._render_tool_call_completed,
    "IterationCompleted": StreamRenderer._render_iteration_completed,
    "InvocationCompleted": StreamRenderer._render_invocation_completed,
    "InvocationFailed": StreamRenderer._render_invocation_failed,
    "InvariantBlocked": StreamRenderer._render_invariant_blocked,
}


def _dev_token_for_tenant(tenant_uuid: str) -> str:
    """Issue an HS256 dev token carrying the tenant UUID and the
    ``agent.invoke`` role required by the SSE endpoint's tenant-
    context resolver (S15) and the route's principal check.

    Phase 1 dev posture: the dev backend at
    ``padhanam.security.auth.issue_dev_token`` reads its signing key
    from ``SecuritySettings``; the CLI runs inside the padhanam-api
    container so the env-loaded settings match the API process's. The
    production swap (Keycloak-issued tokens) lives in the same Phase-2
    deferral the rest of the CLI inherits.
    """
    return issue_dev_token(
        subject="cli-operator",
        tenant_id=tenant_uuid,
        roles=["agent.invoke"],
    )


async def run_invocation(
    *,
    tenant_label: str,
    agent_id: str,
    user_input: str,
    api_url: str = DEFAULT_API_URL,
    output_file: Optional[Path] = None,
    writer: IO[str] | None = None,
    http_client_factory=None,
) -> int:
    """Open the SSE stream, render the events, return the exit code.

    Parameters mirror the CLI surface. ``writer`` defaults to
    ``sys.stdout``; the parameter exists so tests can substitute a
    StringIO. ``http_client_factory`` defaults to ``httpx.AsyncClient``;
    the parameter exists so integration tests can substitute a
    transport that serves canned responses.
    """
    tenant_context, _label = resolve_tenant_context(tenant_label)
    token = _dev_token_for_tenant(str(tenant_context.tenant_id))

    writer_io = writer if writer is not None else sys.stdout

    output_handle: IO[str] | None = None
    if output_file is not None:
        output_handle = output_file.open("w", encoding="utf-8")

    renderer = StreamRenderer(
        writer=writer_io,
        user_input=user_input,
        output_file=output_handle,
    )

    factory = http_client_factory or (lambda: httpx.AsyncClient(timeout=None))

    try:
        async with factory() as client:
            url = f"{api_url.rstrip('/')}/agents/{agent_id}/invoke"
            async with client.stream(
                "POST",
                url,
                json={"user_input": user_input},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "text/event-stream",
                },
            ) as response:
                if response.status_code >= 400:
                    body_text = await response.aread()
                    writer_io.write(
                        f"\n[invocation FAILED] "
                        f"http_status={response.status_code} "
                        f"body={body_text.decode('utf-8', errors='replace')}\n"
                    )
                    return EXIT_FAILED
                async for event in _iter_sse_events_from_lines(
                    response.aiter_lines()
                ):
                    renderer.consume(event)
    finally:
        if output_handle is not None:
            output_handle.close()

    return renderer.exit_code


def render_events_to_string(
    events: Iterable[ParsedEvent], *, user_input: str
) -> tuple[str, int]:
    """Synchronously render an event sequence to a string + exit code.

    Helper for unit tests; the production path goes through
    ``run_invocation``.
    """
    import io

    buf = io.StringIO()
    renderer = StreamRenderer(writer=buf, user_input=user_input)
    for event in events:
        renderer.consume(event)
    return buf.getvalue(), renderer.exit_code


__all__ = [
    "DEFAULT_API_URL",
    "EXIT_SUCCESS",
    "EXIT_FAILED",
    "EXIT_INVARIANT_BLOCKED",
    "TERMINAL_EVENT_TYPES",
    "ParsedEvent",
    "StreamRenderer",
    "parse_sse_block",
    "parse_sse_body",
    "render_events_to_string",
    "run_invocation",
]
