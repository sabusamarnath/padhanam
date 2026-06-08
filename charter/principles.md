# Engineering Principles

Read every session. Kept tight on purpose.

For architectural synthesis with diagrams, see `charter/architecture.md`. For full reasoning behind each architectural commitment, see `charter/decisions.md` (active phase) or `docs/archive/decisions/phase-N.md` (archived phases). For build discipline, see `charter/methodology.md`.

## Architectural

- Hexagonal throughout. External systems behind interfaces. Domain code never imports vendor SDKs (per D4, D16).
- Vendor flexibility. External dependencies — LLM provider, embedding model, database backend, vector store, graph store, audit target, observability target — sit behind ports; vendor swap is configuration or adapter replacement, never domain change. Procurement-grade commitment: vendor lock-in is not architectural. Operationalised at the producer-context level through MetricCalculator and RecommendationRule pluggable domain abstractions (Phase 1, D111); ported domain-layer pluggability is the same principle applied to pluggable evaluation techniques and recommendation rules. The procurement-facing claim is "vendor swap is one adapter, not a rebuild," not "pluggable today": Phase 2-A ports ship one adapter each and the second adapter is built at the second-vendor threshold, not pre-built (the two-threshold rule).
- Local-first. Full stack runs on the laptop. Production swap is configuration, not refactor.
- Database-per-tenant. No code path assumes a single shared database (per D1, D32).
- LLM-provider-agnostic via LiteLLM. Default development model is Ollama (per D4, D15).
- Hybrid retrieval. Vector via pgvector and graph via Neo4j, both behind a unified interface (per D5).
- Observability is foundation, not feature. Trace capture from the first LLM call (per D7).
- Tenant onboarding is configuration, not deployment. Per-tenant decisions (jurisdiction, identity federation, classification policy, model endpoints, retention) live in the tenant registry. Adding a tenant to an existing regional stack is an idempotent workflow. Adding a region is a separate infrastructure event (per D13).
- Jurisdiction is a first-class attribute. Tenant context carries jurisdiction from P3 onward. Every component that touches customer data (databases, object storage, identity, trace store, LLM endpoints) is built to be regionally partitionable. Phase 1 deploys a single region; the architecture does not assume a single region anywhere in code (per D12).
- Customer-specific behaviour is configuration. Tools (external services called by the platform on the tenant's behalf) cover most customer-supplied logic. Extensions exist for the residual cases at named interfaces (RetrievalClient, scorer, pre-processor), sandboxed per tenant. The platform is designed so forking is unnecessary; observed forks signal extension surface failure to be addressed upstream (per D14, D76).
- When an agent adopts a methodology, the methodology is embedded as defaults for tuning surfaces and as envelopes for security, budget, and scope surfaces per D81. Defaults activate at decision points, encode the right thing for the chosen methodology, and yield to user intent at low cost. Envelopes bind hard and are validated at agent write time. The product surface treats user intent as primary for tuning; envelopes are non-overridable by the agent and exist to protect the tenant and the platform. Agents created without methodology lineage skip the methodology layer entirely; they remain bound by platform invariants per the User safety section.
- Bounded contexts at the top of the codebase, hexagonal layers within. Cross-cutting concerns live in `padhanam/` (the cross-cutting implementation package per D28). The `shared_kernel/` is tiny and policed: only types that must be referentially equal across contexts, never Pydantic. Contexts communicate via published query APIs for reads and a domain event bus for state changes; direct cross-context imports are forbidden by `import-linter` in CI (per D16, D17, D28).
- Architectural commitments to specific protocols or standards require demonstrated cross-vendor consolidation, not announcement-level adoption. OTel for observability is committed (consolidated). Other emerging standards (MCP for tool exposition, agent protocols, workflow definition standards) are supported via adapters where appropriate but not committed as architectural assumptions until consolidation is real. The architecture commits to abstractions; protocol choices are configuration above the abstractions.
- *Integration protocol choice is scenario-driven and vendor-readiness-modulated.* Different integration scenarios have different architectural first-choice protocols: agent-to-tool integration defaults to MCP per the deferred-decisions Tool abstraction entry; service-to-service runtime integration defaults to vendor SDK; cross-vendor LLM abstraction is via LiteLLM; observability is via OpenTelemetry. The scenario's first choice is the architectural default; vendor readiness at the chosen protocol determines whether the default is the actual framing-time disposition. An Alpha-stage protocol implementation in a scenario where it would be the architectural default still loses to a production-grade alternative until the implementation reaches production-readiness. Disposition happens per-integration at framing time.
- *Architectural commitments evolve as the protocol and vendor landscape shifts.* No protocol choice is permanent. As standards mature, vendors improve, and new options emerge, Padhanam re-evaluates committed choices. The port-and-adapter discipline is the structural commitment that makes re-evaluation possible; ongoing investment in port-level verification (contract harnesses, configuration-driven swap tests, vendor-agnostic integration evidence) is the operational commitment that keeps swap-readiness real rather than aspirational.
- Role-first agent identity. Roles are the primary identity for agents; the agent's job is the role it occupies. Methodologies are playbooks the role applies (situationally); skills are granular capabilities the agent invokes. Per D86.
- Binding specifications live in charter. Brand identity (`charter/brand-guidelines.md`, `charter/brand/tokens.css`) and bounded-context architecture (`charter/contexts/*`) are commitments the platform stands behind, not implementation detail. Implementation reads specification; specification does not live in implementation. Per D91.

## Security posture

- Compliance targets are SOC 2 Type II and ISO 27001 from Phase 1. Sector-specific frameworks are treated as additive: the architecture commits to a floor strict enough that any reasonable framework tightens configuration rather than requiring re-architecture. The set of additive frameworks is open-ended; specific sectors are not committed at Phase 1 and will be named when tenant sector commitments are made.
- Encryption in transit is mandatory on every network hop in production. Local development uses mkcert TLS at the edge and accepts plaintext inside the Compose network. Production deploys with mTLS internally. The architecture does not assume the production posture; it requires the production swap to enable it through `padhanam/config/` (per D20).
- Encryption at rest is mandatory for every persistent volume in production, provided by the platform (cloud KMS, infrastructure-managed disk encryption). Field-level encryption is application-implemented for specific categories: per-tenant credentials, customer PII, audit log integrity hashes. Field-level crypto uses envelope encryption via `padhanam/security/crypto.py`.
- Secrets are read through `padhanam/config/` exclusively. No code path uses `os.getenv` or reads `.env` directly. Local backend is Pydantic Settings reading `.env`. Production backend is a secret manager, vendor deferred until production deployment context exists, interface fixed now (per D19).
- Audit logging captures every state change on tenant-scoped data: actor, tenant ID, jurisdiction, timestamp, action verb, resource, before-state, after-state, request correlation ID. Append-only storage with hash chaining for tamper-evidence. Audit is a bounded context (`contexts/audit/`), not cross-cutting plumbing (per D26).
- Authentication and authorization are platform concerns. No endpoint ships without authentication middleware in front of it. Authorization is policy-driven and tenant-aware. Privileged actions log separately and additionally (per D23).
- Tenant isolation is verified by `tests/contract/tenant_isolation/` against every adapter touching tenant-scoped data. Cross-tenant access tests are red-team shaped: they attempt unauthorized access and assert the access fails. Adapters do not ship without isolation tests (per D24).
- Supply chain is pinned and scanned. Container images pin to digests. Python dependencies pin via uv lockfile. Vulnerability scanning runs on every build. SBOM generated per release (per D25).
- Security events log separately from application logs via `padhanam/observability/security_events.py`. Categories: auth failure, authorization denial, configuration change, tenant-scope violation, privileged action. Production routes to SIEM.
- Compliance is shared responsibility, not platform-authored. Padhanam maintains its own platform-level compliance documentation as living charter artefacts (Layer A) at `charter/compliance/`. Per-tenant evidence about a tenant's use of the platform is generated from runtime artefacts (Layer B). Per-tenant compliance documentation about products built on Padhanam (Layer C) is tenant-owned, scaffolded by workflow compliance frames that ship with methodology templates as defaults. Workflow frames carry both data-protection scaffolds (C1) and framework-attestation inheritance maps (C2) that compress the tenant's audit work by inheriting platform-level controls and naming the residual tenant-operated controls explicitly. The platform never authors documents that attest to tenant-operated controls.

## Engineering practice

- Tests are part of the build, not a follow-up.
- Schema changes update `charter/schema.md` in the same commit.
- New observability metrics require a documented decision they will inform (per D8).
- Optimization output is recommendation-shaped, not chart-shaped (per D9).
- Security as default: HTTPS via mkcert, secrets in `.env`, RLS on tenant-scoped tables, Pydantic validation on every endpoint, audit log on state changes.
- Conventional commits referencing package and session number.
- New components that touch tenant data accept jurisdiction as a parameter or column from inception. Adding it later is a refactor, not configuration (per D12).
- Methodology is measured against DORA and CORE4 per D40. Definitions and cadence live in `charter/methodology.md`, the active living-hypothesis surface per D113 (superseding D39's pending-authorship framing). Session-log entries include the structured tagging block.
- Throughput pressure is information about scope, not a license to delegate decisions. The first response to operator-capacity constraints is to cut scope, not to automate the work that builds fluency.
- PRD-shaped documentation surfaces (phase PRDs, package epic notes, user stories, PRFAQ) are living artefacts. Original draft is preserved alongside as-built reality; delta capture is the audit deliverable. Append-only at the version level, per D43.
- Reflection density distinguishes session-log entries by conversation type. Strategic conversations produce shorter entries focused on what was decided. Build sessions produce longer entries with substantive reflection on what was learned. The mix of conversation types over time is signal at phase audits (per D47).
- Each session-log entry carries a one-line `roles:` tag naming which of the five role-functions (analyst, PM, architect, engineer, technical writer) were exercised, per D46. The distribution over time surfaces functional atrophy.
- Coach consistency is binding. The agent's voice and identity stay stable when methodologies (playbooks) switch. The user feels they are talking to the same coach whether the agent is applying LVT, RICE, Kano, or McKinsey 7-Step. Per-methodology overrides layer guidance on the agent; they do not replace the agent's identity (per D86).
- Light UX as authoring discipline. Each playbook authored gets a "is this the lightest path to the outcome?" pass at brief time. Each agent-creation flow gets a "would a non-expert reach success without help?" pass. Phase audits review UX feel against these prompts.
- Safety surface per playbook. Each playbook authoring includes a safety-surface pass: what can go wrong; what platform invariants per D82 need to fire; what consent the user gives at each step. Phase audits verify the safety surface against the playbooks shipped in the phase.

## User safety

Padhanam treats user safety as load-bearing principle for the platform's runtime behaviour. See D82 for the underlying commitment. Six dimensions anchor the safety surface: privacy, integrity, reversibility, transparency, control, auditability. Adding a new invariant requires naming which dimensions it serves; removing an invariant requires demonstrating the dimensions are still served by other means.

### Padhanam-as-intelligence-layer

The platform produces recommendations, analyses, and drafts. Consequential actions on the user's behalf require user-in-the-loop authorization at appropriate granularity per the invariants and the consent-granularity principle. This positioning differentiates Padhanam from autonomous-agent platforms; it extends the existing "Optimization output is recommendation-shaped, not chart-shaped" principle from the optimisation layer to the agent layer.

### Platform invariants

Five danger-targeted invariants at Phase 1 close. The set is the platform's dynamic capability posture; capabilities promote in over time as guardrails strengthen.

1. **No financial execution without explicit per-transaction authorization.** Tool-layer classification at P8 prevents financial-execution tools from invoking without per-transaction user confirmation. Dimensions: reversibility, control.

2. **No outbound communication to third parties without explicit per-invocation authorization.** Tools that send to non-Padhanam recipients require user review and confirmation per send; user sees content and recipient before send. Dimensions: control, transparency.

3. **No acceptance of legal commitments without explicit user action.** Tools accepting terms, signing agreements, agreeing to contracts require deliberate user action. Dimensions: control, integrity.

4. **No auto-modification or auto-deletion of user-authored content within Padhanam's storage.** Sources, methodology templates, agent revisions, workflow templates, audit records: append-only or immutable per D26 and D31. Edits create new revisions; deletes are user-initiated only. Dimensions: reversibility, integrity.

5. **No transmission of tenant data outside tenant-configured tool paths.** Tenant data flows only through tools the tenant has configured per D14. Dimensions: privacy, control.

### Consent granularity is proportionate to danger

Per-transaction for financial. Per-invocation for outbound communication. Explicit user action for legal commitments. Standing consent at tool configuration for routine reversible actions, optionally with per-invocation review where the tool's classification specifies.

### Content framing for high-stakes domains

When an agent's output relates to medical, legal, or safety matters, the framing is informational rather than actionable instruction. Information for the user to discuss with qualified professionals, not advice the user should follow directly. Distinct from the capability invariants; sits in this section as a content principle.

### No silent operation

Padhanam does not operate silently on tenant or user state. Every platform action that mutates state surfaces to the user via either real-time review (Tier 1 per the three-tier consent-and-awareness framework at D116) or user-controlled digest review cadence (Tier 2). Tier 3 silent operation does not exist. Combined with the platform invariants and the consent-granularity-proportionate-to-danger principle above, this commits the platform to user-visibility as a foundational property rather than as a configurable preference. Per D121.

### Evolution discipline

The invariant set is versioned in this file per the existing append-only principle. Promotions in (adding capabilities) and promotions out (loosening invariants) are recorded as charter commits with the dimension-justification reasoning. An audit at a point in time captures the invariant set as it stood; future audits compare against the trajectory of evolution.

## Decision discipline

- Strategic placement uses the bet → phase → package → session tree (the strategic-tree artefact lives at `charter/roadmap.md` per D44). Used at framing and at phase audits.
- Option assessment uses Kano. D-entries that select between alternatives carry a Kano category field at the bottom of the entry (must-have, performance, delighter, indifferent, reverse). Per D42.
- Sequencing uses RICE (Reach, Impact, Confidence, Effort). Recorded explicitly on packages and on implementation backlog items where sequencing involves real choice. Per D42.
- Each framework operates at its own moment of the work. Conflating them produces ceremony without reasoning value.
- Phase audits review Kano-category distribution (too many must-haves suggests conflation with default), RICE-score defensibility (forecasts versus post-hoc rationalisations), and roadmap reasoning-category distribution per D44.
- Phase audits review UX-and-safety verification alongside Kano-category distribution and RICE-score defensibility. The cadence inherits the phase-audit pattern; verification artefacts live in `briefs/p<n>/phase-audit.md` at audit time.
- Any D-entry that narrows or reverses a prior clause names the superseded clause in its title and the prior entry's index line is annotated `(… clause superseded by D-n)`. Precedent: D149's "supersedes D148's receive-side sync clause."

## Token discipline

- Claude Code reads only what the session needs.
- Files over 200 lines are read in ranges, not whole.
- Working files (`current-package.md`, `log/sessions.md`) stay tight. `current-package.md` content archives to `docs/archive/packages/p<n>.md` at package close. `log/sessions.md` entries archive to `docs/archive/sessions/p<n>.md` at package close per D107. Never deletes.
- Log entries are one line where possible. Prose only when reasoning is non-obvious.
- Strategic mode and build mode are different work modes, not different UIs. Mode declaration at conversation start is the standing discipline (per D47). Distinct deliverables (strategic produces charter edits, session prompts, or roadmap version updates; build produces code commits and session-log entries) and distinct commit conventions (`docs(charter): ...` or `docs(pN/<boundary-name>): ...` for strategic; `feat(pN/sN): ...` or `docs(pN/sN): ...` for build) carry the separation regardless of which UI is active. Charter files bridge the two modes.
- Architectural commitments deferred to future sessions live in `charter/deferred-decisions.md`. They are inherited by sessions when their context activates and are reviewed at phase audits.
- Exploratory notes and unresolved design questions live in /docs/notes/. Not read in normal sessions; consulted only when explicitly relevant.

## Phase 2 principles

### Frontend and backend separation

Frontend talks to backend only through a versioned HTTP API plus an SSE event stream. No direct database access from the frontend. No shared types via runtime code-sharing (TypeScript types may be generated from backend schema at build time but the generation is one-way). The boundary is a contract surface, not a leaky abstraction.

Origin: karma prior-art product specification §11.3, transplanted at P13 framing per Decision 6 option (c). Karma's enterprise-scale frontend (Studio plus Portal SPA) operates against this boundary; Padhanam's Phase 2-A messaging-first delivery defers SPA to Phase 2-B+ but commits the boundary discipline from inception.

### Audit trail as source of truth

The audit trail is the canonical record of what happened in the system. Every state change on tenant-authored canonical state emits an audit event before persistence completes. Per D155 this clause is scoped: external-source mutable caches (the calendar and email stores) are excluded and carry a re-pull-plus-citation-snapshot provenance model instead of chained cache churn. Derived state (rendered views, cached aggregates, analytical projections) reconstructs from the audit trail when needed. The audit trail is queryable, immutable, and hash-chained.

Origin: karma prior-art product specification §11.5, transplanted at P13 framing per Decision 6 option (c). Padhanam P3 already commits the hash-chained append-only audit substrate; this principle elevates the substrate to a charter-grade discipline that binds every subsequent surface design decision.

### Originals never erased

Persisted artefacts (assertions, intake records, gate decisions, messages, attachments) are never deleted. Updates create new versions; user-initiated removal marks artefacts as archived but does not erase them. The Revisable Protocol per D114 carries this discipline at the entity level; this principle carries it at the system level. Per D155 this binds tenant-authored canonical originals; eviction of an external-source mutable cache row (for example, the calendar tombstone purging an uncited cancelled meeting's content) is not erasure of an original, because the row is a cache whose source of truth is external.

Origin: karma prior-art product specification §11.5, transplanted at P13 framing per Decision 6 option (c). The discipline supports two requirements that the platform's commercial positioning depends on: audit-grade defensibility under regulatory review, and trust-relationship preservation when the user revises positions over time.

### Authority and certainty are independent

A data point carries both an authority (who said it, where it came from) and a certainty (how confident the platform is that it remains current). Authority is fixed at creation; certainty decays with time and is re-evaluated against observed evidence. The two dimensions do not collapse into one another; high authority does not imply high certainty, and high certainty does not require high authority.

Origin: karma prior-art product specification §11.5, transplanted at P13 framing per Decision 6 option (c). The two-vector decay primitive per D118 implements certainty decay against this principle. Authority binding lands at the ActorContext extension at S44.

### Private assistant communication discipline

The Padhanam Private Assistant communicates with the user according to six binding patterns. Every user-facing surface honours these patterns regardless of channel (messaging, dashboard, daily briefing, voice).

1. **Declarative, never imperative.** The assistant tells the user what is, not what to do. "Nestor moved to Margies Travel in March." Not "you should reach out to Nestor."
2. **Suggestion-as-question.** When the assistant proposes an action, the proposal is phrased as a question. "Want me to draft an email?" Not "I'll draft an email for you."
3. **Subtle, not pushy.** When the assistant notices a gap, it surfaces the gap once. The assistant does not follow up, repeat, or escalate. The user decides whether to act.
4. **Specific over generic.** Surfaced content references particular people, deals, conversations, commitments. Generic prompts decay into wallpaper and lose attention.
5. **Visible reasoning.** The user can see why the assistant surfaced something. Selection logic is inspectable, not opaque.
6. **No compliance language.** The assistant does not measure whether the user acted on suggestions, does not track follow-through, does not chide. Compliance tracking converts a priming relationship into a pressure relationship; the platform refuses this conversion structurally.

Origin: the attentional-assistant product brief shared during P13 framing substantive conversation, plus the suggestion-as-question pattern surfaced at the same conversation. The brief frames the platform's category as attentional infrastructure (a fourth category distinct from task assistants, information assistants, and operational prompts). The communication discipline is the load-bearing surface expression of that positioning.

Surfaces this principle binds at Phase 2-A: Twilio messaging at P13; calendar-read, email-read, and to-do-app integration at P14; Slack messaging at P15; the daily briefing email at P15+; the dashboard surface at P15+. Every Phase 2-A surface design decision references this principle.

### Channel-shaped rendering of channel-agnostic domain output

Per D135. The cell or any ConversationFlow implementer produces response content in channel-agnostic shape carrying citation fields per D131 plus confidence-state per D134 plus response prose. The channel adapter translates the content into the channel's affordances at the messaging context. The cell never knows which channel renders; the channel never reaches into domain logic. This principle binds at every Phase 2-A and Phase 2-B+ surface that produces user-facing responses (the manual entry cell at S47; audit-conversation and mirror-conversation ConversationFlow implementers at P14; daily-briefing email at P15+; Slack channel at P15; dashboard at P15+; future voice and Copilot channels).

Origin: convergence-session settlement at S47 cross-cutting concerns 2 (provenance-aware rendering) and 3 (confidence-aware rendering) and setting the contract for concern 1 (multi-channel UX architectural primitives at D136). The pattern's first instance is the WhatsApp channel-adapter rendering of the manual entry cell's three-case response at S47. The pattern's second instance arrives at P14 audit-conversation and mirror-conversation implementers; the structural enforcement surface (shared-kernel base type) emerges at the second instance per the build-at-second-instance discipline.
### Assess, do not replace

Padhanam does not replace the tools a user already keeps their work in. It reads them and supplies what they lack. For every external source it ingests, task tools, calendar, email, message channels, Padhanam reads read-only per the D148 and D155 external-cache model and overlays the layer no source holds: the goal the work serves and the causal read of whether the work advances it.

Padhanam also correlates across sources to assemble a unit of work that no single source holds whole: the origin in a message, the tracking in a task, the time in a calendar block, the purpose in a Padhanam-native goal.

The platform's edge is this assessment across the user's own tools, not a unified store that asks the user to switch. The moment Padhanam becomes the one tool that holds everything, it competes on UX with the time-blockers. Assessing across the tools the user keeps is the differentiated position, and it governs every connector the platform will ever add.
