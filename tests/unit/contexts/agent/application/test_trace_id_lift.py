"""Unit tests for the OTel trace_id lift helper at use_cases.py (D27, D101 area).

The helper at ``_current_otel_trace_id_hex`` reads the active OTel
span's trace_id, formats as 32-character lowercase hex, and returns
``None`` when no recording tracer/span is in scope. D27 commits the
trace_id as the join key between the Postgres runs row and the
Langfuse trace lookup; S35a closes the propagation gap S35's demo
surfaced (runs.trace_id was NULL despite Langfuse-web healthy).

Three concerns:

1. No active span: helper returns None (the unit-test path with no
   SDK-configured tracer provider exercises this).

2. Active span: helper returns a 32-character lowercase hex string
   matching ``format(span_context.trace_id, '032x')``.

3. INVALID_TRACE_ID (zero): helper returns None even when a span is
   technically returned (the no-op span path).
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from contexts.agent.application.use_cases import _current_otel_trace_id_hex


def test_helper_returns_none_when_no_recording_provider_configured() -> None:
    # The default OTel ProxyTracer returns INVALID_TRACE_ID when no
    # provider is configured. The helper maps that to None.
    span = trace.get_current_span()
    assert span.get_span_context().trace_id == trace.INVALID_TRACE_ID
    assert _current_otel_trace_id_hex() is None


def test_helper_returns_32_char_lowercase_hex_inside_active_span() -> None:
    # Install a real TracerProvider so spans get genuine trace IDs.
    # Idempotent at module-level for the test isolation: subsequent
    # tests in this module observe the same provider.
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer("test.trace_id_lift")

    with tracer.start_as_current_span("test.span") as span:
        result = _current_otel_trace_id_hex()
        assert result is not None
        assert len(result) == 32
        assert result == result.lower()
        # The hex string round-trips back to the integer trace_id.
        assert int(result, 16) == span.get_span_context().trace_id


def test_helper_format_conversion_matches_otel_spec() -> None:
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer("test.trace_id_lift")

    with tracer.start_as_current_span("test.span") as span:
        result = _current_otel_trace_id_hex()
        # The conventional OTel hex format is `format(trace_id, '032x')`
        # — 32 lowercase hex characters with leading-zero padding.
        expected = format(span.get_span_context().trace_id, "032x")
        assert result == expected
