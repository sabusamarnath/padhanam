"""Composition wiring for the Padhanam CLI (S18).

The CLI is the first apps/* member to wire the evaluation harness
end-to-end. apps/api wires inference + audit + tenancy + auth for
HTTP requests; the CLI wires evaluation + inference + observability
for the eval harness's replay → cost-aggregate → render flow.

Phase 1 dev shape: tenant resolution accepts a short label
('a' or 'b') or a UUID and resolves to a TenantContext via the
hardcoded test-set mapping. Per-tenant Postgres connection details
come from ``TenantPostgresSettings.for_tenant(label)`` rather than
through the registry; production CLI wiring (Phase 2) routes
through ``contexts.tenancy``'s session-factory cache and
``reveal_connection_config``, mirroring apps/api's composition.
The dev shape is honest about its limitation — the test set is
two tenants and the connection details are environment-driven
through ``.env``.

OTel initialisation: the CLI is a bare-script driver. The S17a
e2e test established the pattern that bare-Python paths outside
FastAPI need their own ``TracerProvider`` setup; without it the
LiteLLMAdapter's span carries trace_id=0 and Completion.trace_id
is None, so the cost-rollup path has nothing to query. The
``init_tracing`` helper here mirrors apps/api/main.py's
``_configure_tracing`` shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from padhanam.config import ObservabilitySettings, TenantPostgresSettings
from shared_kernel import TenantContext


_TENANT_UUID_BY_LABEL: dict[str, str] = {
    "a": "00000000-0000-4000-8000-00000000a001",
    "b": "00000000-0000-4000-8000-00000000b002",
}


def resolve_tenant_context(tenant_id: str) -> tuple[TenantContext, str]:
    """Resolve a CLI ``--tenant-id`` argument to (TenantContext, label).

    Accepts either a short label ('a', 'b') or a UUID present in the
    test-set mapping. Returns the TenantContext used for OTel and
    cross-tenant filtering, alongside the short label needed to
    construct the per-tenant Postgres settings via
    ``TenantPostgresSettings.for_tenant``.

    Phase 1 dev limitation: only the two seeded test tenants are
    resolvable. Production wiring (Phase 2) replaces this with a
    registry lookup; the CLI gains a different ``--tenant-id`` shape
    when the production deployment context arrives.
    """
    arg = tenant_id.lower()
    if arg in _TENANT_UUID_BY_LABEL:
        uuid = _TENANT_UUID_BY_LABEL[arg]
        label = arg
    else:
        # Reverse-lookup by UUID; non-test-set UUIDs raise.
        match = next(
            (lbl for lbl, value in _TENANT_UUID_BY_LABEL.items() if value == arg),
            None,
        )
        if match is None:
            raise ValueError(
                f"unknown --tenant-id {tenant_id!r}; Phase 1 dev CLI "
                f"resolves only the seeded test-set tenants "
                f"(labels: {sorted(_TENANT_UUID_BY_LABEL)})"
            )
        uuid = arg
        label = match
    return (
        TenantContext(
            tenant_id=uuid,
            jurisdiction="eu-west",
            cost_attribution_id=uuid,
        ),
        label,
    )


def session_factory_for_tenant(
    label: str,
) -> tuple[AsyncEngine, async_sessionmaker]:
    """Construct an async sessionmaker bound to the tenant's data plane.

    Returns the engine alongside the sessionmaker so the caller can
    dispose the engine cleanly at exit.
    """
    settings = TenantPostgresSettings.for_tenant(label)
    url = (
        "postgresql+asyncpg://"
        f"{settings.user}:{settings.password}"
        f"@{settings.host}:{settings.port}/{settings.db}"
    )
    engine = create_async_engine(url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def init_tracing(service_name: str = "padhanam-cli") -> TracerProvider:
    """Wire the OTel TracerProvider for bare-script trace emission.

    Returns the configured TracerProvider so the caller can invoke
    ``force_flush`` before the CLI exits, ensuring the BatchSpanProcessor
    flushes pending spans to the Langfuse OTLP receiver. Mirrors
    apps/api/main.py's ``_configure_tracing`` shape.

    The provider is set globally via ``trace.set_tracer_provider``;
    repeat calls within the same Python process update the global
    provider, which is fine for a CLI invocation but would be a
    threading-vs-state hazard in a long-lived app. The CLI process
    is ephemeral so the global-state shape is honest.
    """
    obs = ObservabilitySettings()
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=obs.otlp_endpoint,
                headers={"Authorization": obs.otlp_basic_auth_header},
            )
        )
    )
    trace.set_tracer_provider(provider)
    return provider


@dataclass(frozen=True)
class TenantWiring:
    """The wiring bundle a CLI command needs to invoke an eval flow."""

    tenant_context: TenantContext
    label: str
    engine: AsyncEngine
    session_factory: async_sessionmaker


def build_tenant_wiring(tenant_id: str) -> TenantWiring:
    """Resolve the tenant and construct its session factory."""
    tenant_context, label = resolve_tenant_context(tenant_id)
    engine, factory = session_factory_for_tenant(label)
    return TenantWiring(
        tenant_context=tenant_context,
        label=label,
        engine=engine,
        session_factory=factory,
    )
