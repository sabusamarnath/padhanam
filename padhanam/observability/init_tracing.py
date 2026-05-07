"""Shared OTel TracerProvider initialisation (S19 promotion).

The bare-script driver and FastAPI app initialisation patterns
converged across S17a/S17b/S18 and now S19. The S18 reflection
named the third-instance threshold for promotion to a shared
helper; S19's ingestion worker is the fourth caller, justifying
the lift per the structural-promotion-threshold convention's
asymmetric rule (helpers promote on fourth instance with a
confirmed consumer; comment-level rules promote on third).

Callers at S19:
  - apps/api/main.py — FastAPI app at request-handling time.
  - apps/cli/_runtime.py — the eval CLI's bare-script driver.
  - apps/cli/_ingest.py — the ingestion worker's bare-script
    driver (S19's new caller; the fourth instance).
  - tests/integration/evaluation/test_*_e2e.py — the eval e2e
    scripts that run inside the container via docker compose
    exec and need their own TracerProvider for the bare-script
    flow.

The helper sets the TracerProvider globally via
``trace.set_tracer_provider`` and returns it so the caller can
invoke ``force_flush`` before exit (the BatchSpanProcessor needs
the explicit flush in short-lived drivers; the FastAPI lifespan
covers the long-running case).

The enforcement test at
``tests/_enforcement/test_tracer_provider_setup.py`` asserts
this is the only production-path TracerProvider construction
site; in-memory test-only TracerProviders (for span-capture
assertions) are allowlisted explicitly.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from padhanam.config import ObservabilitySettings


def init_tracing(service_name: str) -> TracerProvider:
    """Wire the OTel SDK with OTLP/HTTP export to Langfuse and set
    the provider globally.

    Returns the configured TracerProvider so the caller can invoke
    ``force_flush`` before the process exits, ensuring the
    BatchSpanProcessor emits pending spans to the OTLP receiver.

    The endpoint and Authorization header come from
    ObservabilitySettings (D19). The exporter uses HTTP/protobuf
    because that is the protocol Langfuse 3 ingests; gRPC is not
    supported (S6 reconciliation finding).

    Repeat calls within the same Python process update the global
    provider, which is fine for a CLI invocation but would be a
    threading-vs-state hazard in a long-lived app — the FastAPI
    side calls this once at app construction.
    """
    settings = ObservabilitySettings()
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=settings.otlp_endpoint,
                headers={"Authorization": settings.otlp_basic_auth_header},
            )
        )
    )
    trace.set_tracer_provider(provider)
    return provider
