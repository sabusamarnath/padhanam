"""Padhanam FastAPI application factory.

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
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from apps.api._auth_errors import register_auth_error_handlers
from apps.api._errors import (
    register_audit_error_handlers,
    register_run_history_error_handlers,
)
from apps.api.middleware import AuthenticationMiddleware, CorrelationIdMiddleware
from apps.api.routers import agent as agent_router
from apps.api.routers import audit as audit_router
from apps.api.routers import health as health_router
from apps.api.routers import inference as inference_router
from apps.api.routers import run_history as run_history_router
from apps.api.routers import tenant_audit as tenant_audit_router
from apps.api.routers.agent import AgentRuntimeComposition
from contexts.audit.ports.reader import AuditEventReader
from contexts.run_history.ports.reader import RunHistoryReader
from contexts.audit.adapters.outbound.postgres.audit import PostgresAuditAdapter
from contexts.audit.domain.ports import AuditPort
from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from contexts.inference.ports import InferencePort
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
)
from contexts.tenancy.adapters.outbound.sqlalchemy.session_factory import (
    SqlAlchemyTenantSessionFactory,
)
from contexts.tenancy.api import TenantSessionFactoryCache
from contexts.tenancy.application.use_cases import OPERATOR_ROLE
from shared_kernel import TenantId as SharedTenantId
from padhanam.config import (
    ControlPlaneSettings,
    InferenceSettings,
    Neo4jSettings,
)
from padhanam.events import DomainEvent, SynchronousEventBus
from padhanam.observability import init_tracing, install_credential_scrub
from padhanam.observability.security_events import (
    SecurityEventLogger,
    file_security_event_logger,
)
from padhanam.security import Principal

# httpx instrumentation propagates the W3C traceparent header through
# every outbound HTTP call. LiteLLM's Python SDK uses httpx internally,
# so this is what makes the gateway-emitted span land as a child of the
# adapter span rather than starting a separate trace (D27 propagation).
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor as _HTTPXInstr

_log = logging.getLogger("padhanam.api")


@dataclass(frozen=True)
class AppCompositions:
    """The seams the factory exposes for tests to substitute.

    Fields with no default are load-bearing for every flow exercised in
    P2 (inference + auth + trace propagation). The S12 additions
    (audit, tenant registry, routing cache) default to ``None`` so
    pre-existing tests that don't exercise the audit-and-routing path
    can keep their narrow factory invocations; the production wiring
    in ``_build_default_compositions`` populates all of them.
    """

    inference_port: InferencePort
    event_bus: SynchronousEventBus
    audit_port: AuditPort | None = None
    tenant_registry: PostgresTenantRegistry | None = None
    session_factory_cache: TenantSessionFactoryCache | None = None
    # S29b (D90): optional agent runtime composition for the SSE
    # endpoint. Defaults to None so apps without the agent stack
    # (existing inference + audit + tenancy clients, test fixtures) can
    # keep their narrow factory invocations; commit 9's integration
    # test populates this for the live-stack end-to-end run.
    agent_runtime: AgentRuntimeComposition | None = None
    # S34 (D98): optional run-history reader for the GET /runs* routes.
    # Defaults to None so test fixtures without the run-history stack
    # can keep their narrow factory invocations; production wiring in
    # _build_default_compositions populates this.
    run_history_reader: RunHistoryReader | None = None
    # S34 (D98): the shared security-event logger surfaced for the
    # run-history routes (which fire TENANT_SCOPE_VIOLATION events on
    # 404s from GET /runs/{run_id}). Existing routes consume the same
    # logger via the auth middleware constructor; this field surfaces
    # it on app.state for route-handler-level access.
    security_events: SecurityEventLogger | None = None
    # S37 (D103): optional audit event reader for the GET /audit/* and
    # GET /platform/audit/* routes. Defaults to None so test fixtures
    # without the audit stack can keep their narrow factory
    # invocations; production wiring in _build_default_compositions
    # populates this from build_audit_event_reader.
    audit_event_reader: AuditEventReader | None = None


def _build_default_compositions() -> AppCompositions:
    inference_settings = InferenceSettings()
    cp_settings = ControlPlaneSettings()
    sec = file_security_event_logger()

    # Tenancy: registry + per-tenant routing cache. The registry adapter
    # holds the control-plane engine; the cache lazily resolves per-
    # tenant sessionmakers via reveal_connection_config (operator-context
    # system actor) per D36.
    session_factory_cache = TenantSessionFactoryCache(
        SqlAlchemyTenantSessionFactory()
    )

    # Audit: real Postgres adapter (D37) replaces the no-op since S5.
    # The resolver bridges the AuditPort's tenant_id parameter into the
    # tenancy routing layer's operator-context get path.
    operator_principal = Principal(
        subject="system:audit",
        tenant_id=SharedTenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="system:audit",
    )

    # The registry adapter is constructed below because PostgresAuditAdapter
    # needs only the control-plane settings; the resolver closure captures
    # registry by name once both are constructed.
    registry: PostgresTenantRegistry  # forward declaration for the closure

    async def _resolve_per_tenant(tenant_id):
        return await session_factory_cache.get(
            tenant_id=tenant_id,
            principal=operator_principal,
            registry=registry,
            security_events=sec,
        )

    audit_adapter = PostgresAuditAdapter.from_settings(
        control_plane_settings=cp_settings,
        per_tenant_sessionmaker_resolver=_resolve_per_tenant,
    )
    registry = PostgresTenantRegistry.from_settings(
        settings=cp_settings,
        audit=audit_adapter,
        security_events=sec,
    )

    inference_port = LiteLLMAdapter(settings=inference_settings)

    # S30b: production-shaped agent runtime composition for the SSE
    # endpoint at apps/api/routers/agent.py. The S29b commit shipped
    # the endpoint plus the AgentRuntimeComposition dataclass on
    # app.state but left the default factory with agent_runtime=None;
    # S30b wires the production composition so the new
    # `padhanam agent run` CLI (and any future SSE consumer) reaches a
    # real runtime through the standard API entry point.
    from apps.api._agent_runtime_wiring import (
        build_agent_runtime_composition,
        build_audit_event_reader,
        build_run_history_reader,
    )

    agent_runtime = build_agent_runtime_composition(
        inference_port=inference_port,
        audit_port=audit_adapter,
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
        control_plane_settings=cp_settings,
        neo4j_settings=Neo4jSettings(),
    )

    # S34: run-history reader for the GET /runs* routes. Mirrors the
    # writer wiring in build_agent_runtime_composition (same session
    # factory cache, same operator principal, same security-event
    # logger).
    run_history_reader = build_run_history_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )

    # S37: audit event reader for the GET /audit/* and GET
    # /platform/audit/* routes. Shares the control-plane
    # sessionmaker with the write-side audit adapter so reads and
    # writes pool against the same engine.
    audit_event_reader = build_audit_event_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
        control_plane_sessionmaker=audit_adapter.control_plane_sessionmaker,
    )

    return AppCompositions(
        inference_port=inference_port,
        event_bus=SynchronousEventBus(),
        audit_port=audit_adapter,
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        agent_runtime=agent_runtime,
        run_history_reader=run_history_reader,
        security_events=sec,
        audit_event_reader=audit_event_reader,
    )


def _configure_tracing(service_name: str = "padhanam-api") -> None:
    """Thin wrapper around the shared init_tracing helper (S19
    promotion). Kept as a one-liner so tests that patch
    _configure_tracing keep working without churn; new callers
    import init_tracing directly per S19 commit 7.
    """
    init_tracing(service_name)


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

    # Defense-in-depth around plaintext credential leakage (D34
    # control (a)). Installed before any registry-touching adapter has
    # a chance to log; idempotent so test fixtures may invoke it too.
    install_credential_scrub()

    if configure_tracing:
        _configure_tracing()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        _log.info("padhanam-api starting up")
        yield
        _log.info("padhanam-api shutting down")

    app = FastAPI(
        title="Padhanam API",
        version="0.0.0",
        lifespan=lifespan,
    )

    # Auth middleware FIRST so it wraps the router from the ASGI side
    # — including 404 and 422 handlers. Order of add_middleware calls
    # is reverse-applied at request time (last added is outermost), so
    # CorrelationIdMiddleware added last sits outermost, generating a
    # correlation_id before AuthenticationMiddleware reads it for the
    # AUTH_FAILURE security event.
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    # S34 (D98): error handlers translate run-history exceptions into
    # the new ErrorResponse body shape. Existing routes keep using
    # FastAPI's default HTTPException 422 / 404 / 500 shapes until they
    # refresh to the new shape.
    register_run_history_error_handlers(app)

    # S38 (D104): authentication-cross-cutting error handlers.
    # PrincipalTypeMismatchError (403 with AUTHZ_DENIAL security
    # event) relocated from register_audit_error_handlers at S38 so
    # each new router consuming get_tenant_context or
    # get_platform_operator_principal inherits the 403 path without
    # coupling to audit. Registered ahead of audit registration so
    # the auth-cross-cutting surface is wired first.
    register_auth_error_handlers(app)

    # S37 (D103) refined at S38 (D104): audit error handlers cover
    # audit-specific exception classes only after the S38 relocation.
    # Covers AuditEventNotFoundError (404), InvalidAuditFilterError
    # (400), AuditMalformedCursorError (400), AuditQueryRoutingError
    # (400). PrincipalTypeMismatchError moved to
    # register_auth_error_handlers per D104.
    register_audit_error_handlers(app)

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
    app.include_router(tenant_audit_router.router)
    app.include_router(agent_router.router)
    app.include_router(run_history_router.router)
    # S37 (D103): two audit route trees — /audit/* under
    # principal-derived tenant context; /platform/audit/* under the
    # new platform-operator principal type.
    app.include_router(audit_router.tenant_router)
    app.include_router(audit_router.platform_router)

    # Composition exposure: routers fetch dependencies from app.state.
    app.state.inference_port = compositions.inference_port
    app.state.event_bus = compositions.event_bus
    app.state.audit_port = compositions.audit_port
    app.state.tenant_registry = compositions.tenant_registry
    app.state.session_factory_cache = compositions.session_factory_cache
    app.state.agent_runtime = compositions.agent_runtime
    app.state.run_history_reader = compositions.run_history_reader
    app.state.security_events = compositions.security_events
    app.state.audit_event_reader = compositions.audit_event_reader

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
