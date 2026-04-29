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
