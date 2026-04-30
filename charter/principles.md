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
- Bounded contexts at the top of the codebase, hexagonal layers within. Cross-cutting concerns live in `vadakkan/` (the cross-cutting implementation package per D28). The `shared_kernel/` is tiny and policed: only types that must be referentially equal across contexts, never Pydantic. Contexts communicate via published query APIs for reads and a domain event bus for state changes; direct cross-context imports are forbidden by `import-linter` in CI.
- Architectural commitments to specific protocols or standards require demonstrated cross-vendor consolidation, not announcement-level adoption. OTel for observability is committed (consolidated). Other emerging standards (MCP for tool exposition, agent protocols, workflow definition standards) are supported via adapters where appropriate but not committed as architectural assumptions until consolidation is real. The architecture commits to abstractions; protocol choices are configuration above the abstractions.

## Security posture

- Compliance targets are SOC 2 Type II and ISO 27001 from Phase 1. Sector-specific frameworks are treated as additive: the architecture commits to a floor strict enough that any reasonable framework tightens configuration rather than requiring re-architecture. The set of additive frameworks is open-ended; specific sectors are not committed at Phase 1 and will be named when tenant sector commitments are made.
- Encryption in transit is mandatory on every network hop in production. Local development uses mkcert TLS at the edge and accepts plaintext inside the Compose network. Production deploys with mTLS internally. The architecture does not assume the production posture; it requires the production swap to enable it through `vadakkan/config/`.
- Encryption at rest is mandatory for every persistent volume in production, provided by the platform (cloud KMS, infrastructure-managed disk encryption). Field-level encryption is application-implemented for specific categories: per-tenant credentials, customer PII, audit log integrity hashes. Field-level crypto uses envelope encryption via `vadakkan/security/crypto.py`.
- Secrets are read through `vadakkan/config/` exclusively. No code path uses `os.getenv` or reads `.env` directly. Local backend is Pydantic Settings reading `.env`. Production backend is a secret manager, vendor deferred until production deployment context exists, interface fixed now.
- Audit logging captures every state change on tenant-scoped data: actor, tenant ID, jurisdiction, timestamp, action verb, resource, before-state, after-state, request correlation ID. Append-only storage with hash chaining for tamper-evidence. Audit is a bounded context (`contexts/audit/`), not cross-cutting plumbing.
- Authentication and authorization are platform concerns. No endpoint ships without authentication middleware in front of it. Authorization is policy-driven and tenant-aware. Privileged actions log separately and additionally.
- Tenant isolation is verified by `tests/contract/tenant_isolation/` against every adapter touching tenant-scoped data. Cross-tenant access tests are red-team shaped: they attempt unauthorized access and assert the access fails. Adapters do not ship without isolation tests.
- Supply chain is pinned and scanned. Container images pin to digests. Python dependencies pin via uv lockfile. Vulnerability scanning runs on every build. SBOM generated per release.
- Security events log separately from application logs via `vadakkan/observability/security_events.py`. Categories: auth failure, authorization denial, configuration change, tenant-scope violation, privileged action. Production routes to SIEM.

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
- Architectural commitments deferred to future sessions live in `charter/deferred-decisions.md`. They are inherited by sessions when their context activates and are reviewed at phase audits.
- Exploratory notes and unresolved design questions live in /docs/notes/. Not read in normal sessions; consulted only when explicitly relevant.