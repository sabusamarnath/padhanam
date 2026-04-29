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
