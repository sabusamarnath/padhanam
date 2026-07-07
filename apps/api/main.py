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
    register_ingestion_error_handlers,
    register_intake_error_handlers,
    register_optimization_error_handlers,
    register_portfolio_error_handlers,
    register_retrieval_evaluation_error_handlers,
    register_run_history_error_handlers,
)
from apps.api._internal_secret import register_internal_secret_error_handlers
from apps.api._messaging_errors import register_messaging_error_handlers
from apps.api._messaging_wiring import MessagingComposition
from apps.api.middleware import AuthenticationMiddleware, CorrelationIdMiddleware
from apps.api.routers import agent as agent_router
from apps.api.routers import audit as audit_router
from apps.api.routers import auth as auth_router
from apps.api.routers import connections as connections_router
from apps.api.routers import conversation as conversation_router
from apps.api.routers import daily_driver as daily_driver_router
from apps.api.routers import health as health_router
from apps.api.routers import inference as inference_router
from apps.api.routers import ingestion as ingestion_router
from apps.api.routers import messaging as messaging_router
from apps.api.routers import optimization as optimization_router
from apps.api.routers import intake as intake_router
from apps.api.routers import portfolio as portfolio_router
from apps.api.routers import retrieval_evaluation as retrieval_evaluation_router
from apps.api.routers import run_history as run_history_router
from apps.api.routers import tenant_audit as tenant_audit_router
from apps.api.routers import triggers as triggers_router
from apps.api.routers.agent import AgentRuntimeComposition
from contexts.audit.ports.reader import AuditEventReader
from contexts.optimization.ports.optimization_run_reader import (
    OptimizationRunReader,
)
from contexts.optimization.ports.optimization_run_repository import (
    OptimizationRunRepository,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationReader,
)
from contexts.optimization.ports.recommendation_repository import (
    RecommendationRepository,
)
from contexts.portfolio.ports import PortfolioReader
from contexts.intake.ports.intake_repository import IntakeRepository
from contexts.intake.application.ports.portfolio_writer import PortfolioWriter
from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunReader,
)
from contexts.retrieval_evaluation.ports.evaluation_run_repository import (
    EvaluationRunRepository,
)
from contexts.retrieval_evaluation.ports.reader import GoldSetReader
from contexts.retrieval_evaluation.ports.repository import GoldSetRepository
from contexts.retrieval_evaluation.ports.retrieval_runner import (
    RetrievalRunnerPort,
)
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
    # S38 (D104): optional source repository for the GET /ingestion/*
    # routes. Defaults to None so test fixtures without the ingestion
    # stack can keep their narrow factory invocations; production
    # wiring in _build_default_compositions populates this from
    # build_source_repository.
    source_repository: object | None = None
    # S42 (D112): retrieval-evaluation surface — gold-set authoring,
    # evaluation-run kickoff, and the discovery candidates route.
    # Default to None so test fixtures without the retrieval-evaluation
    # stack can keep their narrow factory invocations; production wiring
    # populates each via the builders in _agent_runtime_wiring.py.
    gold_set_repository: GoldSetRepository | None = None
    gold_set_reader: GoldSetReader | None = None
    evaluation_run_repository: EvaluationRunRepository | None = None
    evaluation_run_reader: EvaluationRunReader | None = None
    # Top-level retrieval client and runner port for the discovery
    # endpoint and the synchronous evaluation-run kickoff. Separate
    # instances from the agent-runtime composition's internal client;
    # both share the same TenantSessionFactoryCache and tenant registry
    # so per-tenant routing produces identical connections regardless
    # of which surface invokes search.
    retrieval_client: object | None = None
    retrieval_runner_port: RetrievalRunnerPort | None = None
    # S42 (D112): optimization surface — engine kickoff plus recommendation
    # read and lifecycle write routes.
    optimization_run_repository: OptimizationRunRepository | None = None
    optimization_run_reader: OptimizationRunReader | None = None
    recommendation_repository: RecommendationRepository | None = None
    recommendation_reader: RecommendationReader | None = None
    # S43b (D124): portfolio context read surface for the
    # GET /api/v1/portfolio/cases* routes.
    portfolio_reader: PortfolioReader | None = None
    # S44b (D127): intake write surface — the intake repository and
    # the PortfolioWriter consumer-port adapter behind the portfolio
    # and intake write routes.
    intake_repository: IntakeRepository | None = None
    portfolio_writer: PortfolioWriter | None = None
    # S45 (D129): messaging composition — the Message repository
    # adapter, the selected delivery adapter, the MessageWriter
    # consumer-port adapter, and the inbound-webhook configuration.
    messaging: MessagingComposition | None = None
    # S54 (D146): daily-briefing DailyBriefingReader consumer-port
    # adapter composing intake + audit + portfolio reads. Defaults to
    # None so test fixtures without the daily-briefing stack keep their
    # narrow factory invocations; production wiring populates it.
    daily_briefing_reader: object | None = None
    # S58 (D157): daily-driver context seams — the CommitmentRepository
    # and DayRepository per-request-tenant routers and the OpenCasesReader
    # consumer adapter composing portfolio list_cases (OPEN filter).
    # Default to None so narrow test fixtures keep working; production
    # wiring populates each via the builders in _daily_driver_wiring.py.
    daily_driver_commitment_repository: object | None = None
    daily_driver_day_repository: object | None = None
    daily_driver_open_cases_reader: object | None = None
    # S60 (D159): the calendar consumer adapter composing the calendar
    # MeetingReader, filtered to today. None when unwired (the list
    # degrades to Cases + Commitments).
    daily_driver_calendar_reader: object | None = None
    # S61 (D162): the configured drop-candidate quiet-window threshold N.
    # None when unconfigured (the list degrades to the S60 view, no nudge).
    daily_driver_drop_candidate_quiet_days: int | None = None
    # S62 (D163): the goal-layer graph reader/raiser over the shared Neo4j.
    daily_driver_goal_graph: object | None = None
    daily_driver_cdd_drafter: object | None = None
    daily_driver_jd_extractor: object | None = None
    # S103af (D238): the CV parser (pdfplumber) + skills-profile extractor over the
    # structured-output seam — matching-engine leg 2.
    daily_driver_cv_parser: object | None = None
    daily_driver_cv_extractor: object | None = None
    # S103ag (D239): the match — confirmed profile vs a role's selection criteria over
    # the structured-output seam — matching-engine leg 3.
    daily_driver_match_port: object | None = None
    # S65 (D167): the Tasks-view reader over the ingested tasks cache. None
    # when unwired (the /tasks view degrades to an empty list).
    daily_driver_tasks_reader: object | None = None
    # S66 (D168): the work-unit correlation seams — the FacetSource over the
    # three caches and the UnitGraphPort over the shared Neo4j. None when
    # unwired (the /units view degrades to an empty list).
    daily_driver_facet_source: object | None = None
    daily_driver_email_job_search_source: object | None = None
    daily_driver_email_source_metadata: object | None = None
    daily_driver_email_content_source: object | None = None
    daily_driver_unit_graph: object | None = None
    # S103c (D203): the audit port for capturing CDD-evidence corrections
    # (relink/unlink) as the append-only learning signal. None when unwired.
    daily_driver_audit_port: object | None = None
    # S60 (D159): the Connections page status reader (design-language §9).
    connections_status_reader: object | None = None
    # S60b (D160): the login verifier (token-exchange seam; dev wired,
    # google operator-gated).
    login_verifier: object | None = None
    # S60c (D161): the Google OIDC client (initiate/callback mechanics) and
    # the Google login verifier (callback resolves the code → identity →
    # tenant through it). Both None until the OAuth client is configured.
    google_oidc: object | None = None
    google_login_verifier: object | None = None
    # S60b (D160): the calendar connect initiator (Nango, operator-gated)
    # and the connect-callback connection store (writes the per-tenant
    # connection + triggers the first sync).
    calendar_connect_initiator: object | None = None
    connection_store: object | None = None


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
        build_source_repository,
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

    # S38 (D104): per-tenant routing source repository for the
    # GET /ingestion/* routes. Resolves the per-tenant session
    # factory at call time via the shared TenantSessionFactoryCache
    # — same shape as TenantRoutingRetrievalClient and the
    # writer/reader factories above.
    source_repository = build_source_repository(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )

    # S42 (D112): retrieval-evaluation + optimization HTTP transport
    # surface. The gold-set + evaluation-run + recommendation read and
    # write surfaces all share the per-tenant session factory cache
    # plus the operator principal plus the security-events logger.
    # The retrieval_client is a fresh TenantRoutingRetrievalClient
    # instance (separate from the one inside the agent runtime
    # composition); both back onto the same cache and registry so
    # per-tenant routing produces identical connections.
    from apps.api._agent_runtime_wiring import (
        build_evaluation_run_reader,
        build_evaluation_run_repository,
        build_gold_set_reader,
        build_gold_set_repository,
        build_optimization_run_reader,
        build_optimization_run_repository,
        build_portfolio_reader,
        build_recommendation_reader,
        build_recommendation_repository,
        build_retrieval_client,
        build_retrieval_runner_port,
    )
    from apps.api._intake_wiring import (
        build_intake_repository,
        build_portfolio_writer,
    )
    from apps.api._messaging_wiring import build_messaging_composition

    gold_set_repository = build_gold_set_repository(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    gold_set_reader = build_gold_set_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    evaluation_run_repository = build_evaluation_run_repository(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    evaluation_run_reader = build_evaluation_run_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    retrieval_client = build_retrieval_client(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
        neo4j_settings=Neo4jSettings(),
    )
    retrieval_runner_port = build_retrieval_runner_port(
        retrieval_client=retrieval_client,
    )
    optimization_run_repository = build_optimization_run_repository(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    optimization_run_reader = build_optimization_run_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    recommendation_repository = build_recommendation_repository(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    recommendation_reader = build_recommendation_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    portfolio_reader = build_portfolio_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    intake_repository = build_intake_repository(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    portfolio_writer = build_portfolio_writer(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
        audit_port=audit_adapter,
    )
    messaging = build_messaging_composition(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
        audit_port=audit_adapter,
        structured_output_port=inference_port,
        audit_event_reader=audit_event_reader,
    )

    # S54 (D146): daily-briefing DailyBriefingReader adapter composing
    # the intake repository, the audit event reader, and the portfolio
    # list_cases read; plus the LLM composer, the outbound notifier, and
    # the BroadcastFlow implementer registered against the messaging
    # composition's BroadcastFlow registry with trigger_type=DAILY_SCHEDULED.
    from apps.api._daily_briefing_wiring import (
        BriefingNotifierAdapter,
        build_daily_briefing_implementer,
        build_daily_briefing_reader,
    )
    from contexts.daily_briefing.adapters.llm.litellm_daily_briefing_composer_adapter import (  # noqa: E501
        LiteLLMDailyBriefingComposerAdapter,
    )
    from padhanam.config import MessagingSettings
    from shared_kernel.broadcast_flow import BroadcastTriggerType

    daily_briefing_reader = build_daily_briefing_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
        intake_repository=intake_repository,
        audit_event_reader=audit_event_reader,
    )
    _messaging_settings = MessagingSettings()
    daily_briefing_implementer = build_daily_briefing_implementer(
        reader=daily_briefing_reader,
        composer=LiteLLMDailyBriefingComposerAdapter(
            structured_output_port=inference_port,
        ),
        notifier=BriefingNotifierAdapter(
            repository=messaging.repository,
            delivery_port=messaging.delivery_port,
            audit_port=audit_adapter,
            channel_resolver=messaging.channel_resolver,
            from_address=messaging.from_address,
        ),
        jurisdiction=_messaging_settings.webhook_jurisdiction,
        window_hours=_messaging_settings.daily_briefing_window_hours,
    )
    messaging.broadcast_flow_registry.register(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        implementer=daily_briefing_implementer,
    )

    # S57 (D153): the proactive threshold arc. The ThresholdEvaluator
    # (SCHEDULED_EVALUATION) refreshes calendar then evaluates over the
    # calendar STATE store and emits THRESHOLD_CROSSED through the
    # FireTrigger idempotency flow; the threshold-briefing implementer
    # (THRESHOLD_CROSSED) composes and dispatches. Phase 2-A binds the
    # evaluator's state-read + refresh to the single broadcast tenant.
    from apps.api._threshold_briefing_wiring import (
        ActiveRuleRefreshAdapter,
        ThresholdCrossedEmitterAdapter,
        ThresholdNotifierAdapter,
        build_calendar_state_reader,
    )
    from contexts.threshold_briefing.adapters.llm.litellm_threshold_briefing_composer_adapter import (  # noqa: E501
        LiteLLMThresholdBriefingComposerAdapter,
    )
    from contexts.threshold_briefing.application.rule_config import phase_2a_rules
    from contexts.threshold_briefing.application.threshold_briefing_implementer import (  # noqa: E501
        ThresholdBriefingImplementer,
    )
    from contexts.threshold_briefing.application.threshold_evaluator import (
        ThresholdEvaluator,
    )

    _broadcast_tenant = _messaging_settings.webhook_tenant_id
    threshold_evaluator = ThresholdEvaluator(
        state_reader=build_calendar_state_reader(tenant_id=_broadcast_tenant),
        emitter=ThresholdCrossedEmitterAdapter(
            fired_triggers_repository=messaging.fired_triggers_repository,
            audit_port=audit_adapter,
            broadcast_dispatch=messaging.broadcast_dispatch,
            jurisdiction=_messaging_settings.webhook_jurisdiction,
            operator_timezone=_messaging_settings.operator_timezone,
        ),
        rules=phase_2a_rules(),
        jurisdiction=_messaging_settings.webhook_jurisdiction,
        refresh_port=ActiveRuleRefreshAdapter(tenant_id=_broadcast_tenant),
    )
    threshold_briefing_implementer = ThresholdBriefingImplementer(
        composer=LiteLLMThresholdBriefingComposerAdapter(
            structured_output_port=inference_port,
        ),
        notifier=ThresholdNotifierAdapter(
            repository=messaging.repository,
            delivery_port=messaging.delivery_port,
            audit_port=audit_adapter,
            channel_resolver=messaging.channel_resolver,
            from_address=messaging.from_address,
        ),
        jurisdiction=_messaging_settings.webhook_jurisdiction,
    )
    messaging.broadcast_flow_registry.register(
        trigger_type=BroadcastTriggerType.SCHEDULED_EVALUATION,
        implementer=threshold_evaluator,
    )
    messaging.broadcast_flow_registry.register(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        implementer=threshold_briefing_implementer,
    )

    # S58 (D157): daily-driver context — the CommitmentRepository and
    # DayRepository per-request-tenant routers plus the OpenCasesReader
    # consumer adapter (the D17 seam composing portfolio list_cases,
    # OPEN filter). All share the per-tenant session factory cache,
    # operator principal, and security-events logger.
    from apps.api._daily_driver_wiring import (
        build_calendar_events_reader,
        build_commitment_repository,
        build_day_repository,
        build_email_content_source,
        build_email_job_search_source,
        build_email_source_metadata,
        build_cdd_drafter,
        build_cv_extractor,
        build_jd_extractor,
        build_match,
        build_facet_source,
        build_goal_graph,
        build_open_cases_reader,
        build_tasks_reader,
        build_unit_graph,
    )
    from padhanam.config.calendar import CalendarSettings

    daily_driver_commitment_repository = build_commitment_repository(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    daily_driver_day_repository = build_day_repository(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    daily_driver_open_cases_reader = build_open_cases_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    _calendar_domain_tag = CalendarSettings().calendar_domain_tag
    daily_driver_calendar_reader = build_calendar_events_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
        domain_tag=_calendar_domain_tag,
    )
    # S61 (D162): the drop-candidate quiet-window threshold, config-driven.
    from padhanam.config.daily_driver import DailyDriverSettings

    daily_driver_drop_candidate_quiet_days = (
        DailyDriverSettings().drop_candidate_quiet_days
    )
    # S62 (D163): the goal-layer graph reader over the shared Neo4j (process-shared).
    daily_driver_goal_graph = build_goal_graph()
    # S102 (D200): the CDD drafter over the structured-output seam (Ollama dev
    # model by default), the authored-layer LLM draft.
    daily_driver_cdd_drafter = build_cdd_drafter(
        structured_output_port=inference_port
    )
    # S103ad (D236): the JD extractor over the same structured-output seam — drafts
    # three qualification fields from a pasted job description (matching-engine leg 1).
    daily_driver_jd_extractor = build_jd_extractor(
        structured_output_port=inference_port
    )
    # S103af (D238): the CV parser (pdfplumber, text-layer + multi-column) and the
    # skills-profile extractor over the same structured-output seam — matching-engine
    # leg 2. The parser has no vendor SDK in domain; the extractor drafts suggestions.
    from apps.api._cv_parser import build_cv_parser

    daily_driver_cv_parser = build_cv_parser()
    daily_driver_cv_extractor = build_cv_extractor(
        structured_output_port=inference_port
    )
    # S103ag (D239): the match over the same structured-output seam — per-criterion
    # coverage of the confirmed profile against a role's selection criteria (leg 3).
    daily_driver_match_port = build_match(
        structured_output_port=inference_port
    )
    # S65 (D167): the Tasks-view reader over the ingested tasks cache.
    daily_driver_tasks_reader = build_tasks_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    # S66 (D168): the work-unit correlation seams — the FacetSource over the
    # three caches and the UnitGraphPort over the shared Neo4j (process-shared).
    daily_driver_facet_source = build_facet_source(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    # D183/S89: the rule-confirmed job-search emails (the persisted classifier
    # verdict) — feeds the moat's count-by-kind fold + the active reading.
    daily_driver_email_source_metadata = build_email_source_metadata(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    daily_driver_email_job_search_source = build_email_job_search_source(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    # D212: the verification drawer's openable read-only source (email content).
    daily_driver_email_content_source = build_email_content_source(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
    )
    daily_driver_unit_graph = build_unit_graph()
    from apps.api._connections_wiring import build_connections_status_reader

    connections_status_reader = build_connections_status_reader(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
        domain_tag=_calendar_domain_tag,
    )
    from apps.api._auth_login_wiring import (
        build_google_login_verifier,
        build_login_verifier,
    )
    from apps.api._google_oidc import build_google_oidc

    # S60c (D161): the Google OIDC login. build_google_oidc returns None until
    # the OAuth client is configured (operator-gated); the verifier then raises
    # and the initiate/callback routes 503. login_verifier still selects the
    # passphrase route's backend (dev wired by default).
    google_oidc = build_google_oidc()
    google_login_verifier = (
        build_google_login_verifier(oidc=google_oidc)
        if google_oidc is not None
        else None
    )
    login_verifier = build_login_verifier(oidc=google_oidc)
    from apps.api._calendar_connect_wiring import (
        build_calendar_connect_initiator,
        build_connection_store,
    )

    calendar_connect_initiator = build_calendar_connect_initiator()
    connection_store = build_connection_store(
        tenant_registry=registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=sec,
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
        source_repository=source_repository,
        gold_set_repository=gold_set_repository,
        gold_set_reader=gold_set_reader,
        evaluation_run_repository=evaluation_run_repository,
        evaluation_run_reader=evaluation_run_reader,
        retrieval_client=retrieval_client,
        retrieval_runner_port=retrieval_runner_port,
        optimization_run_repository=optimization_run_repository,
        optimization_run_reader=optimization_run_reader,
        recommendation_repository=recommendation_repository,
        recommendation_reader=recommendation_reader,
        portfolio_reader=portfolio_reader,
        intake_repository=intake_repository,
        portfolio_writer=portfolio_writer,
        messaging=messaging,
        daily_briefing_reader=daily_briefing_reader,
        daily_driver_commitment_repository=daily_driver_commitment_repository,
        daily_driver_day_repository=daily_driver_day_repository,
        daily_driver_open_cases_reader=daily_driver_open_cases_reader,
        daily_driver_calendar_reader=daily_driver_calendar_reader,
        daily_driver_drop_candidate_quiet_days=(
            daily_driver_drop_candidate_quiet_days
        ),
        daily_driver_goal_graph=daily_driver_goal_graph,
        daily_driver_cdd_drafter=daily_driver_cdd_drafter,
        daily_driver_jd_extractor=daily_driver_jd_extractor,
        daily_driver_cv_parser=daily_driver_cv_parser,
        daily_driver_cv_extractor=daily_driver_cv_extractor,
        daily_driver_match_port=daily_driver_match_port,
        daily_driver_tasks_reader=daily_driver_tasks_reader,
        daily_driver_facet_source=daily_driver_facet_source,
        daily_driver_email_source_metadata=daily_driver_email_source_metadata,
        daily_driver_email_content_source=daily_driver_email_content_source,
        daily_driver_email_job_search_source=(
            daily_driver_email_job_search_source
        ),
        daily_driver_unit_graph=daily_driver_unit_graph,
        daily_driver_audit_port=audit_adapter,
        connections_status_reader=connections_status_reader,
        login_verifier=login_verifier,
        google_oidc=google_oidc,
        google_login_verifier=google_login_verifier,
        calendar_connect_initiator=calendar_connect_initiator,
        connection_store=connection_store,
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

    # S38 (D104): ingestion management error handlers. Covers
    # IngestionSourceNotFoundError (404) and the ingestion-side
    # MalformedCursorError (400). Mirror of the audit and
    # run-history registration shape per the additive composition
    # discipline.
    register_ingestion_error_handlers(app)

    # S42 (D112): retrieval-evaluation and optimization error handlers.
    # Cover the gold-set + evaluation-run + recommendation lifecycle
    # exception classes plus the InvalidOptimizationFilterError surfaced
    # by the recommendations list query parser. Same additive shape as
    # the existing registrations.
    register_retrieval_evaluation_error_handlers(app)
    register_optimization_error_handlers(app)

    # S43b (D124): portfolio HTTP error handlers — case_not_found (404),
    # malformed_portfolio_cursor (400), invalid_portfolio_filter (400).
    register_portfolio_error_handlers(app)

    # S44b (D127): intake HTTP error handlers — intake_not_found (404),
    # malformed_intake_cursor (400), invalid_intake_filter (400).
    register_intake_error_handlers(app)

    # S45 (D129): messaging HTTP error handlers — message_not_found
    # (404), malformed_messaging_cursor (400), invalid_messaging_filter
    # (400), webhook_signature_invalid (403). A dedicated module per
    # the redirect-away-from-over-budget-files discipline.
    register_messaging_error_handlers(app)

    # S54 (D145, D147): internal-secret error handler — internal_secret_invalid
    # (401) for the HTTP trigger endpoint. The endpoint bypasses bearer
    # auth; the X-Internal-Secret header is its authentication.
    register_internal_secret_error_handlers(app)

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
    # S38 (D104): ingestion management routes under principal-derived
    # tenant context. Three read endpoints: list sources, get source,
    # get source status.
    app.include_router(ingestion_router.router)

    # S42 (D112): retrieval-evaluation transport surface — three routers
    # (gold-sets, retrieval-candidates discovery, evaluation-runs).
    app.include_router(retrieval_evaluation_router.gold_set_router)
    app.include_router(retrieval_evaluation_router.discovery_router)
    app.include_router(retrieval_evaluation_router.evaluation_run_router)

    # S42 (D112): optimization transport surface — two routers
    # (optimization-runs, recommendations).
    app.include_router(optimization_router.optimization_run_router)
    app.include_router(optimization_router.recommendation_router)

    # S43b (D124): portfolio read-surface routes under principal-derived
    # tenant context — GET /api/v1/portfolio/cases and /cases/{case_id}.
    app.include_router(portfolio_router.router)

    # S44b (D127): intake routes — POST /api/v1/intakes plus the GET
    # single and list surfaces, under principal-derived actor context.
    app.include_router(intake_router.router)

    # S45 (D129): messaging routes — POST /send, the POST /inbound
    # Twilio WhatsApp webhook (bearer-auth-bypassed, signature-verified),
    # and the GET single and list surfaces.
    app.include_router(messaging_router.router)

    # S54 (D145, D147): HTTP trigger endpoint — POST
    # /api/v1/internal/triggers/fire (bearer-auth-bypassed,
    # internal-secret-verified). The deployment's external scheduler
    # fires platform-initiated broadcasts here.
    app.include_router(triggers_router.router)

    # S58 (D157): daily-driver routes — GET /today, POST /commitments,
    # POST /commitments/{id}/completions, PUT /today/order, POST
    # /today/done (all under principal-derived actor context), plus the
    # served operator surface GET /app (auth-exempt per _PUBLIC_PATHS).
    app.include_router(daily_driver_router.router)
    app.include_router(daily_driver_router.ui_router)

    # S59 (D158): the live conversational-turn-over-HTTP surface — POST
    # /api/v1/daily-driver/conversation/open and /turn run the existing
    # portfolio mirror-conversation cell over HTTP (principal-derived
    # actor context; stateless per turn, the cell threaded via the shared
    # messaging composition). Replaces the S58 read-only open-into-context.
    app.include_router(conversation_router.router)

    # S60 (D159): the in-product Connections page — GET /api/v1/connections
    # (tenant connection status, principal-derived actor context) plus the
    # served page GET /connections (auth-exempt per _PUBLIC_PATHS).
    app.include_router(connections_router.router)
    app.include_router(connections_router.ui_router)

    # S60b (D160): the login surface — POST /api/v1/auth/login (public
    # token-exchange) plus the served login page at GET / and /login
    # (auth-exempt per _PUBLIC_PATHS). Closes the paste-a-dev-token UX
    # backdoor; the data routes stay bearer-authed.
    app.include_router(auth_router.router)
    app.include_router(auth_router.ui_router)

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
    app.state.source_repository = compositions.source_repository
    # S42 (D112): retrieval-evaluation and optimization composition seams.
    app.state.gold_set_repository = compositions.gold_set_repository
    app.state.gold_set_reader = compositions.gold_set_reader
    app.state.evaluation_run_repository = compositions.evaluation_run_repository
    app.state.evaluation_run_reader = compositions.evaluation_run_reader
    app.state.retrieval_client = compositions.retrieval_client
    app.state.retrieval_runner_port = compositions.retrieval_runner_port
    app.state.optimization_run_repository = (
        compositions.optimization_run_repository
    )
    app.state.optimization_run_reader = compositions.optimization_run_reader
    app.state.recommendation_repository = compositions.recommendation_repository
    app.state.recommendation_reader = compositions.recommendation_reader
    app.state.portfolio_reader = compositions.portfolio_reader
    # S45 (D129): messaging composition seam.
    app.state.messaging = compositions.messaging
    # S54 (D146): daily-briefing reader composition seam.
    app.state.daily_briefing_reader = compositions.daily_briefing_reader
    # S58 (D157): daily-driver composition seams.
    app.state.daily_driver_commitment_repository = (
        compositions.daily_driver_commitment_repository
    )
    app.state.daily_driver_day_repository = (
        compositions.daily_driver_day_repository
    )
    app.state.daily_driver_open_cases_reader = (
        compositions.daily_driver_open_cases_reader
    )
    app.state.daily_driver_calendar_reader = (
        compositions.daily_driver_calendar_reader
    )
    # S61 (D162): the drop-candidate quiet-window threshold.
    app.state.daily_driver_drop_candidate_quiet_days = (
        compositions.daily_driver_drop_candidate_quiet_days
    )
    # S62 (D163): the goal-layer graph reader/raiser.
    app.state.daily_driver_goal_graph = compositions.daily_driver_goal_graph
    app.state.daily_driver_cdd_drafter = compositions.daily_driver_cdd_drafter
    app.state.daily_driver_jd_extractor = compositions.daily_driver_jd_extractor
    app.state.daily_driver_cv_parser = compositions.daily_driver_cv_parser
    app.state.daily_driver_cv_extractor = compositions.daily_driver_cv_extractor
    app.state.daily_driver_match_port = compositions.daily_driver_match_port
    app.state.daily_driver_tasks_reader = (
        compositions.daily_driver_tasks_reader
    )
    # S66 (D168): the work-unit correlation seams.
    app.state.daily_driver_facet_source = (
        compositions.daily_driver_facet_source
    )
    # D183/S89: the rule-confirmed job-search email source for the moat view.
    app.state.daily_driver_email_source_metadata = (
        compositions.daily_driver_email_source_metadata
    )
    # D212: the verification drawer's openable read-only email source.
    app.state.daily_driver_email_content_source = (
        compositions.daily_driver_email_content_source
    )
    app.state.daily_driver_email_job_search_source = (
        compositions.daily_driver_email_job_search_source
    )
    app.state.daily_driver_unit_graph = compositions.daily_driver_unit_graph
    # The CDD audit port (D203 correction capture, S103v warming steps): the
    # compositions field was never exposed on app.state, so get_cdd_audit_port
    # always read None — correction capture silently no-op'd and warming steps 503'd.
    # Wiring it here fixes both (S103v).
    app.state.daily_driver_audit_port = compositions.daily_driver_audit_port
    app.state.connections_status_reader = (
        compositions.connections_status_reader
    )
    app.state.login_verifier = compositions.login_verifier
    app.state.google_oidc = compositions.google_oidc
    app.state.google_login_verifier = compositions.google_login_verifier
    app.state.calendar_connect_initiator = (
        compositions.calendar_connect_initiator
    )
    app.state.connection_store = compositions.connection_store
    # S44b (D127): intake write-surface composition seams.
    app.state.intake_repository = compositions.intake_repository
    app.state.portfolio_writer = compositions.portfolio_writer

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
