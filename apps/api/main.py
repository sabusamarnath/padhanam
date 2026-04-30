"""Vadakkan FastAPI application factory.

The factory owns composition: it instantiates the InferencePort
adapter, registers the auth middleware so it sits in front of every
route, wires OTel instrumentation, registers the event bus with one
example subscription, and includes the routers.

The factory exists so tests can build an app with substitute adapters
(fake InferencePort, mock security event logger) without touching
module-level globals. The Uvicorn entrypoint at the bottom calls
create_app() once for the production-shaped composition.

Auth middleware is added via app.add_middleware so it sits at the
ASGI layer above the FastAPI router. Starlette processes middleware
before routing, so unmatched paths (404s) and validation errors
(422s) still pass through auth first and return 401 if the request
is unauthenticated. test_auth_coverage.py asserts this property by
enumerating every registered route.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from apps.api.middleware import AuthenticationMiddleware
from apps.api.routers import health as health_router
from apps.api.routers import inference as inference_router
from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from contexts.inference.ports import InferencePort
from vadakkan.config import InferenceSettings, ObservabilitySettings
from vadakkan.events import DomainEvent, SynchronousEventBus

# httpx instrumentation propagates the W3C traceparent header through
# every outbound HTTP call. LiteLLM's Python SDK uses httpx internally,
# so this is what makes the gateway-emitted span land as a child of the
# adapter span rather than starting a separate trace (D27 propagation).
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor as _HTTPXInstr

_log = logging.getLogger("vadakkan.api")


@dataclass(frozen=True)
class AppCompositions:
    """The seams the factory exposes for tests to substitute."""

    inference_port: InferencePort
    event_bus: SynchronousEventBus


def _build_default_compositions() -> AppCompositions:
    inference_settings = InferenceSettings()
    return AppCompositions(
        inference_port=LiteLLMAdapter(settings=inference_settings),
        event_bus=SynchronousEventBus(),
    )


def _configure_tracing(service_name: str = "vadakkan-api") -> None:
    """Wire OTel SDK with OTLP/HTTP export to the Langfuse endpoint.

    The endpoint comes from ObservabilitySettings (D19). The exporter
    uses HTTP/protobuf because that's the protocol Langfuse 3 ingests;
    gRPC is not supported (S6 reconciliation finding).
    """
    observability = ObservabilitySettings()
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )
    exporter = OTLPSpanExporter(
        endpoint=observability.otlp_endpoint,
        headers={"Authorization": observability.otlp_basic_auth_header},
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def create_app(
    *,
    compositions: AppCompositions | None = None,
    configure_tracing: bool = True,
) -> FastAPI:
    """Construct the FastAPI app with all middleware, routers, and wiring.

    Tests pass a custom AppCompositions to substitute the InferencePort;
    they also pass configure_tracing=False to suppress OTel exporter
    setup (the SDK's default no-op tracer is fine for unit tests).
    """
    compositions = compositions or _build_default_compositions()

    if configure_tracing:
        _configure_tracing()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        _log.info("vadakkan-api starting up")
        yield
        _log.info("vadakkan-api shutting down")

    app = FastAPI(
        title="Vadakkan API",
        version="0.0.0",
        lifespan=lifespan,
    )

    # Auth middleware FIRST so it wraps the router from the ASGI side
    # — including 404 and 422 handlers. Order of add_middleware calls
    # is reverse-applied at request time (last added is outermost), so
    # this single auth middleware is the only one and sits at the
    # outside.
    app.add_middleware(AuthenticationMiddleware)

    # OTel FastAPI instrumentation populates a server span around every
    # request. The instrumentation must run after middleware is
    # registered so span context propagates into the auth-middleware
    # frame and into the router handler frame.
    FastAPIInstrumentor.instrument_app(app)

    # httpx instrumentation injects the W3C traceparent header into
    # every outbound HTTP call so the LiteLLM gateway picks up the
    # request's trace context and the gateway-emitted span lands as a
    # grandchild of the FastAPI request span (D27 propagation). The
    # instrumentor is process-global; instrumenting once is enough.
    if not _HTTPXInstr().is_instrumented_by_opentelemetry:
        _HTTPXInstr().instrument()

    # Routers.
    app.include_router(health_router.router)
    app.include_router(inference_router.router)

    # Composition exposure: routers fetch dependencies from app.state.
    app.state.inference_port = compositions.inference_port
    app.state.event_bus = compositions.event_bus

    # Example event-bus subscription per the prompt — the wiring shape
    # is the asset, not the example logger. Replaced with real audit
    # and observability subscribers as those land.
    def _example_subscriber(event: DomainEvent) -> None:
        _log.info("domain_event id=%s ts=%s", event.event_id, event.occurred_at)

    compositions.event_bus.subscribe(DomainEvent, _example_subscriber)

    return app


def _asgi_app() -> FastAPI:
    """Lazy uvicorn entrypoint.

    Constructed on first attribute access so importing this module
    (in tests, in import-linter graphs, in the AST enforcement
    walkers) does not bring up the full OTel exporter and reach for
    the Langfuse endpoint. uvicorn's ``--factory`` flag picks this up
    when the app is started in production: ``uvicorn apps.api.main:app
    --factory`` calls _asgi_app() once at boot.

    For backward compatibility, ``apps.api.main.app`` resolves to the
    constructed instance via ``__getattr__`` below.
    """
    return create_app()


def __getattr__(name: str) -> object:
    if name == "app":
        global _cached_app
        try:
            return _cached_app
        except NameError:
            _cached_app = _asgi_app()
            return _cached_app
    raise AttributeError(f"module {__name__} has no attribute {name!r}")
