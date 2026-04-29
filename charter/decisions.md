# Architectural Decisions

Append-only log. One entry per decision. Reviewed at phase audits.

Format:
- **Decision N: [name]** (Package P, Session S)
  - Choice: [what was decided]
  - Reasoning: [one or two sentences]
  - Alternatives considered: [if relevant]

## Phase 1 baseline decisions

These were made before Session 1 and form the starting architecture.

- **D1: Tenancy model is database-per-tenant.** Strongest isolation. V1 runs one tenant locally; architecture is forward-built for many.
- **D2: No sub-workspaces inside a tenant in V1.** Tenant is the unit of organization. Workspaces deferred to V2 if needed.
- **D3: Identity is Keycloak in V1 Docker Compose.** Reference open-source IdP, OIDC + SAML + SCIM. ~1GB RAM cost accepted.
- **D4: LLM access via LiteLLM gateway.** No vendor SDKs in domain code. Ollama default in dev.
- **D5: Retrieval is hybrid, configured per agent.** Vector via pgvector and graph via Neo4j, both behind `RetrievalClient`. Strategy fixed at agent config in V1; runtime selection deferred to V2.
- **D6: Orchestration is LangGraph behind `AgentOrchestrator` interface.** CrewAI or custom orchestrators swappable later.
- **D7: Trace store is self-hosted Langfuse 3, behind an interface.** OpenTelemetry GenAI conventions used throughout.
- **D8: V1 metric scope is bounded.** Cache hit rate, output token distribution, context length trajectory, tool call patterns, cost per successful task, latency components decomposed, model substitution similarity scores. New metrics require documented decisions they inform.
- **D9: Optimization output is recommendation-shaped.** Every dashboard view ties to a recommended action.
- **D10: Stack versions pinned.** Python 3.14, Node 24 LTS, Postgres 17 with pgvector, Neo4j 5 Community, Keycloak 26, Redis 7, Vite 6, React 19, React Router 7, FastAPI, SQLAlchemy 2.0 async, LangGraph current, LiteLLM current, Langfuse 3.

## Session decisions

Appended as sessions produce them. New entries below this line.

---

- **D11: Scaffold grows incrementally** (Package P1, Session 1)
  - Choice: Each package adds the Compose services it requires. P1 ships repo structure, charter docs, and structural tooling. Compose at P1 close contains only services exercised by P1 or P2.
  - Reasoning: Big-bang scaffold front-loads complexity before any service has earned a use case, contradicting the learning-sprint framing of Phase 1. Incremental scaffold reaches agent work faster and prevents unused-service drift.
  - Alternatives considered: Big-bang scaffold (Postgres, Neo4j, Keycloak, Redis, LiteLLM, Langfuse all at P1 close). Rejected on learning-value and drift grounds.

- **D12: Jurisdiction is a first-class architectural attribute** (Pre-S2 charter edit)
  - Choice: Tenant context carries jurisdiction from P3 onward. Every component that touches customer data (databases, object storage, identity, trace store, LLM endpoints) is built to be regionally partitionable. Phase 1 deploys a single region; the architecture does not assume a single region anywhere in code.
  - Reasoning: Retrofitting jurisdiction across forty tables and every interface signature later is a quarter of work and a migration risk. Building it in from inception is free at the data-model layer and cheap at the interface layer. The discipline is "by construction, not by policy", which is the framing enterprise procurement and auditors require.
  - Alternatives considered: Treat jurisdiction as a Phase 2 concern and add it when the first non-default-region tenant arrives. Rejected on retrofit-cost grounds.

- **D13: Tenant onboarding is configuration, not deployment** (Pre-S2 charter edit)
  - Choice: Per-tenant decisions (jurisdiction, identity federation, classification policy, model endpoints, retention) live in the tenant registry as configuration. The application reads the registry; no code path hardcodes per-tenant behaviour. Adding a tenant to an existing regional stack is an idempotent provisioning workflow. Adding a region is a separate infrastructure event, scoped explicitly when a customer's residency requirement crosses an existing region boundary.
  - Reasoning: Onboarding through configuration scales; onboarding through deployment does not. The architectural commitment that adding a tenant requires no code changes is what makes the platform sellable to enterprise customers with custom IdP, jurisdiction, and classification requirements. Distinguishing tenant-add from region-add prevents over-claiming.
  - Alternatives considered: Conflate tenant and region provisioning into one workflow. Rejected because they have different actors, different lifecycles, and different cost profiles.

- **D14: Customer-specific behaviour is configuration; capability extensions are bounded** (Pre-S2 charter edit)
  - Choice: The platform exposes parameters, schemas, and tool integration points that cover the large majority of per-tenant requirements. Tools (external services called by the platform on the tenant's behalf) are the primary mechanism for customer-supplied logic and are configuration, not code. Extension points exist for the residual cases where logic must run inside the platform with access to internal state; extensions are versioned, sandboxed, and isolated per tenant, and are bounded to a small named set of interfaces (RetrievalClient, scorer, pre-processor). Forking the platform codebase for customer-specific logic is forbidden.
  - Reasoning: Configuration-only positions cannot survive contact with enterprise customers; codebase-forking destroys the platform. The middle path (configuration first, tool calls for most customer logic, sandboxed extensions for the residue) is the position every mature platform vendor converges on. Setting the boundary now prevents the rot.
  - Alternatives considered: Pure configuration with no extension surface (insufficient for enterprise). Open extension surface with arbitrary plugin points (becomes a fork farm). Rejected.

- **D15: Default development model is Qwen 2.5 7B** (Package P2, pre-S6)
  - Choice: Qwen 2.5 7B served via Ollama is the default model for development and the eval harness baseline.
  - Reasoning: Tool-calling fidelity matters once the agent surface lands, and Qwen 2.5's tool-call behaviour is more reliable than Llama 3.1 at comparable memory cost. Reversible if the eval harness surfaces problems.
  - Alternatives considered: Llama 3.1 8B (conservative default, weaker tool calling). Rejected on tool-call grounds.

- **D16: Codebase structure is bounded contexts on hexagonal, with platform / contexts / shared_kernel separation and import-linter enforcement** (Package P2, pre-S7)
  - Choice: The codebase organizes around bounded contexts at the top level (`contexts/`), with cross-cutting platform concerns (`platform/`), a strictly bounded `shared_kernel/`, and deployable units (`apps/`) that compose contexts and adapters into runnables. Each context internally follows hexagonal layers (`domain/`, `application/`, `ports/`, `adapters/inbound/`, `adapters/outbound/`). Boundaries are enforced by `import-linter` contracts in CI, not by convention. The `shared_kernel/` contains only types that must be referentially equal across contexts (TenantId, Jurisdiction) and forbids Pydantic imports to prevent framework version coupling. Packaging uses uv workspaces, with per-context `pyproject.toml` files added when a context first acquires a third-party dependency that should not bleed across boundaries. The observability split (`platform/observability/` is mechanism, `contexts/observability/` is intelligence) is deliberate: span emission is infrastructure every context uses; trace analysis and recommendation generation are a product feature with their own domain model.
  - Reasoning: Enterprise architecture review requires the answer to "where does retrieval live" to be a single folder, "how is multi-tenancy enforced" to be a build-time invariant, and "how do we swap a vendor" to be a port contract. Organizing by technical layer at the top level fails all three; organizing by bounded context with hexagonal layers within each passes all three. The platform / contexts / shared_kernel split keeps the import graph a DAG. Import-linter turns the architectural rules into CI failures rather than review comments.
  - Alternatives considered: Top-level layered structure (`domain/`, `application/`, `adapters/` at the root). Rejected: scatters each business concern across four directories and produces the modular-monolith-becomes-hairball failure mode. Top-level `ports/` directory. Rejected: ports are owned by the domain that needs them, not global. Pure flat package. Rejected: structurally indefensible at enterprise audit.

- **D17: Contexts communicate via published query APIs for reads and a domain event bus for state changes** (Package P2, pre-S7)
  - Choice: Each bounded context exposes a single `api.py` module at its root containing read-only query methods other contexts may call. State-changing interactions flow through a domain event bus in `platform/events/`: contexts publish events from their domain or application layer, other contexts subscribe through wiring in `apps/`. No context imports another context's internals. The bus is synchronous in-process in Phase 1; the interface is broker-ready so Phase 2 can swap to a real event broker without changing context code. `import-linter` enforces the rule that `contexts/X/*` may import only `contexts/Y/api`, never `contexts/Y/domain` or `contexts/Y/adapters`.
  - Reasoning: "Contexts communicate through ports or shared_kernel" is too vague to defend at audit. The hybrid (queries direct, commands eventful) is the pattern mature platform vendors converge on after the fact and is cheap to adopt now. It reflects Meridian's actual data flow: observability queries trace state on the hot path (read-shaped, latency-sensitive) and reacts to inference completions for recommendation generation (event-shaped, decoupled). Forcing reads through events adds latency without benefit; forcing writes through direct calls couples contexts that should stay separable.
  - Alternatives considered: Direct synchronous calls only (modular monolith, couples deployment). Events for everything (latency on the hot path, no benefit). Rejected on the trade-offs above.

- **D18: Redis is shared between Meridian application use and Langfuse ingestion in development; production Redis topology is deferred** (Package P2, Session 4)
  - Choice: A single Redis instance serves both Meridian application caching and queueing (DB 0) and Langfuse ingestion queueing (DB 1) in the local Compose stack. The configuration interface (per `platform/config/`, landing in S5) is structured so production deployments can resolve Meridian Redis and Langfuse Redis to either the same instance or separate instances by configuration, without code change.
  - Reasoning: Local development cost favours sharing; production posture depends on factors (queue depth, eviction policy compatibility, security boundary requirements) that are not yet known. Forcing a production decision now would commit on missing information. The architecture commits to the configuration interface that defers the decision cleanly.
  - Alternatives considered: Separate Redis instance for Langfuse from inception. Rejected: doubles development cost without benefit at this stage. Shared instance hardcoded with no config swap path. Rejected: forces production into a posture that may not fit.
