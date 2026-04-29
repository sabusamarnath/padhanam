# Engineering Principles

Read every session. Kept tight on purpose.

## Architectural

- Hexagonal throughout. External systems behind interfaces. Domain code never imports vendor SDKs.
- Local-first. Full stack runs on the laptop. Production swap is configuration, not refactor.
- Database-per-tenant. No code path assumes a single shared database.
- LLM-provider-agnostic via LiteLLM. Default development model is Ollama.
- Hybrid retrieval. Vector via pgvector and graph via Neo4j, both behind a unified interface.
- Observability is foundation, not feature. Trace capture from the first LLM call.
- Tenant onboarding is configuration, not deployment. Per-tenant decisions (jurisdiction, identity federation, classification policy, model endpoints, retention) live in the tenant registry. Adding a tenant to an existing regional stack is an idempotent workflow. Adding a region is a separate infrastructure event.
- Jurisdiction is a first-class attribute. Tenant context carries jurisdiction from P3 onward. Every component that touches customer data (databases, object storage, identity, trace store, LLM endpoints) is built to be regionally partitionable. Phase 1 deploys a single region; the architecture does not assume a single region anywhere in code.
- Customer-specific behaviour is configuration. Tools (external services called by the platform on the tenant's behalf) cover most customer-supplied logic. Extensions exist for the residual cases at named interfaces (RetrievalClient, scorer, pre-processor), sandboxed per tenant. Forking the platform codebase is forbidden.
- Bounded contexts at the top of the codebase, hexagonal layers within. Cross-cutting concerns live in `platform/`. The `shared_kernel/` is tiny and policed: only types that must be referentially equal across contexts, never Pydantic. Contexts communicate via published query APIs for reads and a domain event bus for state changes; direct cross-context imports are forbidden by `import-linter` in CI.

## Engineering practice

- Tests are part of the build, not a follow-up.
- Schema changes update `charter/schema.md` in the same commit.
- New observability metrics require a documented decision they will inform.
- Optimization output is recommendation-shaped, not chart-shaped.
- Security as default: HTTPS via mkcert, secrets in `.env`, RLS on tenant-scoped tables, Pydantic validation on every endpoint, audit log on state changes.
- Conventional commits referencing package and session number.
- New components that touch tenant data accept jurisdiction as a parameter or column from inception. Adding it later is a refactor, not configuration.

## Token discipline

- Claude Code reads only what the session needs.
- Files over 200 lines are read in ranges, not whole.
- Working files (`current-package.md`, session log entries) stay tight. Old content moves to archive at audit time, never deletes.
- Log entries are one line where possible. Prose only when reasoning is non-obvious.
- Strategic decisions and audits happen in Claude.ai. Build and test happen in Claude Code. Decisions written to local files bridge the two.
