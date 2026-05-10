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
- Customer-specific behaviour is configuration. Tools (external services called by the platform on the tenant's behalf) cover most customer-supplied logic. Extensions exist for the residual cases at named interfaces (RetrievalClient, scorer, pre-processor), sandboxed per tenant. The platform is designed so forking is unnecessary; observed forks signal extension surface failure to be addressed upstream.
- Methodology is embedded as defaults, not gated as workflow steps. Defaults activate at decision points, encode the right thing for the chosen methodology, and yield to user intent at low cost. The product surface treats user intent as primary; methodology is the smart default that the user can override without friction.
- Bounded contexts at the top of the codebase, hexagonal layers within. Cross-cutting concerns live in `padhanam/` (the cross-cutting implementation package per D28). The `shared_kernel/` is tiny and policed: only types that must be referentially equal across contexts, never Pydantic. Contexts communicate via published query APIs for reads and a domain event bus for state changes; direct cross-context imports are forbidden by `import-linter` in CI.
- Architectural commitments to specific protocols or standards require demonstrated cross-vendor consolidation, not announcement-level adoption. OTel for observability is committed (consolidated). Other emerging standards (MCP for tool exposition, agent protocols, workflow definition standards) are supported via adapters where appropriate but not committed as architectural assumptions until consolidation is real. The architecture commits to abstractions; protocol choices are configuration above the abstractions.

## Security posture

- Compliance targets are SOC 2 Type II and ISO 27001 from Phase 1. Sector-specific frameworks are treated as additive: the architecture commits to a floor strict enough that any reasonable framework tightens configuration rather than requiring re-architecture. The set of additive frameworks is open-ended; specific sectors are not committed at Phase 1 and will be named when tenant sector commitments are made.
- Encryption in transit is mandatory on every network hop in production. Local development uses mkcert TLS at the edge and accepts plaintext inside the Compose network. Production deploys with mTLS internally. The architecture does not assume the production posture; it requires the production swap to enable it through `padhanam/config/`.
- Encryption at rest is mandatory for every persistent volume in production, provided by the platform (cloud KMS, infrastructure-managed disk encryption). Field-level encryption is application-implemented for specific categories: per-tenant credentials, customer PII, audit log integrity hashes. Field-level crypto uses envelope encryption via `padhanam/security/crypto.py`.
- Secrets are read through `padhanam/config/` exclusively. No code path uses `os.getenv` or reads `.env` directly. Local backend is Pydantic Settings reading `.env`. Production backend is a secret manager, vendor deferred until production deployment context exists, interface fixed now.
- Audit logging captures every state change on tenant-scoped data: actor, tenant ID, jurisdiction, timestamp, action verb, resource, before-state, after-state, request correlation ID. Append-only storage with hash chaining for tamper-evidence. Audit is a bounded context (`contexts/audit/`), not cross-cutting plumbing.
- Authentication and authorization are platform concerns. No endpoint ships without authentication middleware in front of it. Authorization is policy-driven and tenant-aware. Privileged actions log separately and additionally.
- Tenant isolation is verified by `tests/contract/tenant_isolation/` against every adapter touching tenant-scoped data. Cross-tenant access tests are red-team shaped: they attempt unauthorized access and assert the access fails. Adapters do not ship without isolation tests.
- Supply chain is pinned and scanned. Container images pin to digests. Python dependencies pin via uv lockfile. Vulnerability scanning runs on every build. SBOM generated per release.
- Security events log separately from application logs via `padhanam/observability/security_events.py`. Categories: auth failure, authorization denial, configuration change, tenant-scope violation, privileged action. Production routes to SIEM.
- Compliance is shared responsibility, not platform-authored. Padhanam maintains its own platform-level compliance documentation as living charter artefacts (Layer A) at `charter/compliance/`. Per-tenant evidence about a tenant's use of the platform is generated from runtime artefacts (Layer B). Per-tenant compliance documentation about products built on Padhanam (Layer C) is tenant-owned, scaffolded by workflow compliance frames that ship with methodology templates as defaults. Workflow frames carry both data-protection scaffolds (C1) and framework-attestation inheritance maps (C2) that compress the tenant's audit work by inheriting platform-level controls and naming the residual tenant-operated controls explicitly. The platform never authors documents that attest to tenant-operated controls.

## Engineering practice

- Tests are part of the build, not a follow-up.
- Schema changes update `charter/schema.md` in the same commit.
- New observability metrics require a documented decision they will inform.
- Optimization output is recommendation-shaped, not chart-shaped.
- Security as default: HTTPS via mkcert, secrets in `.env`, RLS on tenant-scoped tables, Pydantic validation on every endpoint, audit log on state changes.
- Conventional commits referencing package and session number.
- New components that touch tenant data accept jurisdiction as a parameter or column from inception. Adding it later is a refactor, not configuration.
- Methodology is measured against DORA and CORE4 per D40. Definitions and cadence will live in `charter/methodology.md` (pending operator authorship per D39). Session-log entries include the structured tagging block.
- Throughput pressure is information about scope, not a license to delegate decisions. The first response to operator-capacity constraints is to cut scope, not to automate the work that builds fluency.
- PRD-shaped documentation surfaces (phase PRDs, package epic notes, user stories, PRFAQ) are living artefacts. Original draft is preserved alongside as-built reality; delta capture is the audit deliverable. Append-only at the version level, per D43.
- Reflection density distinguishes session-log entries by conversation type. Strategic conversations produce shorter entries focused on what was decided. Build sessions produce longer entries with substantive reflection on what was learned. The mix of conversation types over time is signal at phase audits.
- Each session-log entry carries a one-line `roles:` tag naming which of the five role-functions (analyst, PM, architect, engineer, technical writer) were exercised, per D46. The distribution over time surfaces functional atrophy.

## Decision discipline

- Strategic placement uses the bet → phase → package → session tree (the strategic-tree artefact lives at `charter/roadmap.md` per D44). Used at framing and at phase audits.
- Option assessment uses Kano. D-entries that select between alternatives carry a Kano category field at the bottom of the entry (must-have, performance, delighter, indifferent, reverse). Per D42.
- Sequencing uses RICE (Reach, Impact, Confidence, Effort). Recorded explicitly on packages and on implementation backlog items where sequencing involves real choice. Per D42.
- Each framework operates at its own moment of the work. Conflating them produces ceremony without reasoning value.
- Phase audits review Kano-category distribution (too many must-haves suggests conflation with default), RICE-score defensibility (forecasts versus post-hoc rationalisations), and roadmap reasoning-category distribution per D44.

## Token discipline

- Claude Code reads only what the session needs.
- Files over 200 lines are read in ranges, not whole.
- Working files (`current-package.md`, session log entries) stay tight. Old content moves to archive at audit time, never deletes.
- Log entries are one line where possible. Prose only when reasoning is non-obvious.
- Strategic mode and build mode are different work modes, not different UIs. Mode declaration at conversation start is the standing discipline (per D47). Distinct deliverables (strategic produces charter edits, session prompts, or roadmap version updates; build produces code commits and session-log entries) and distinct commit conventions (`docs(charter): ...` or `docs(pN/<boundary-name>): ...` for strategic; `feat(pN/sN): ...` or `docs(pN/sN): ...` for build) carry the separation regardless of which UI is active. Charter files bridge the two modes.
- Architectural commitments deferred to future sessions live in `charter/deferred-decisions.md`. They are inherited by sessions when their context activates and are reviewed at phase audits.
- Exploratory notes and unresolved design questions live in /docs/notes/. Not read in normal sessions; consulted only when explicitly relevant.