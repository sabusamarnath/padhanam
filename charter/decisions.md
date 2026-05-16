# Architectural Decisions

Append-only log. One entry per decision. Reviewed at phase audits.

D-entries from closed phases archive to `docs/archive/decisions/phase-<n>.md` per the methodology document's per-phase decisions archival pattern (see `charter/methodology.md` under "Per-phase decisions archival pattern"). Phase 1 (D1 through D113) archived at post-P12 charter-discipline hygiene, 2026-05-16. New D-entries in Phase 2 land below until Phase 2 close.

Summary format below: `**D<n>: <title>** (Package, Session, date)`. Full Choice / Reasoning / Alternatives / Kano content lives in the archive.

## Phase 1 baseline decisions (D1-D10)

Made before Session 1 and form the starting architecture. Full content at [docs/archive/decisions/phase-1.md](../docs/archive/decisions/phase-1.md).

- **D1: Tenancy model is database-per-tenant.**
- **D2: No sub-workspaces inside a tenant in V1.**
- **D3: Identity is Keycloak in V1 Docker Compose.** Superseded by D52 (Phase 2 deferral).
- **D4: LLM access via LiteLLM gateway. No vendor SDKs in domain code.**
- **D5: Retrieval is hybrid, configured per agent.**
- **D6: Orchestration is LangGraph behind `AgentOrchestrator` interface.**
- **D7: Trace store is self-hosted Langfuse 3, behind an interface.**
- **D8: V1 metric scope is bounded; new metrics require documented decisions they inform.**
- **D9: Optimization output is recommendation-shaped.**
- **D10: Stack versions pinned.**

## Phase 1 session decisions (D11-D113)

Full content at [docs/archive/decisions/phase-1.md](../docs/archive/decisions/phase-1.md).

- **D11: Scaffold grows incrementally** (P1, S1)
- **D12: Jurisdiction is a first-class architectural attribute** (Pre-S2 charter edit)
- **D13: Tenant onboarding is configuration, not deployment** (Pre-S2 charter edit)
- **D14: Customer-specific behaviour is configuration; capability extensions are bounded** (Pre-S2 charter edit). Forking phrasing later refined by D76.
- **D15: Default development model is Qwen 2.5 7B** (P2, pre-S6)
- **D16: Codebase structure is bounded contexts on hexagonal, with platform / contexts / shared_kernel separation and import-linter enforcement** (P2, pre-S7)
- **D17: Contexts communicate via published query APIs for reads and a domain event bus for state changes** (P2, pre-S7)
- **D18: Redis is shared between Quorum application use and Langfuse ingestion in development; production Redis topology is deferred** (P2, S4)
- **D19: Configuration is read through `platform/config/` exclusively, no direct `os.getenv` or `.env` reads** (P2, S5)
- **D20: TLS configuration is read through `platform/config/`, dev plaintext, prod mTLS with no plaintext escape hatch** (P2, S5)
- **D21: Field-level encryption uses envelope encryption via `platform/security/crypto.py`** (P2, S5)
- **D22: Audit logging is a bounded context (`contexts/audit/`) with hash-chained append-only storage** (P2, S5)
- **D23: Authentication and authorization are platform concerns; no endpoint ships without auth middleware** (P2, S5)
- **D24: Tenant isolation is verified by `tests/contract/tenant_isolation/` against every adapter touching tenant-scoped data** (P2, S5)
- **D25: Supply chain hardening — image digest pins, dependency lockfiles, vulnerability scanning, SBOM, scheduled monitoring** (P2, S5)
- **D26: Security events log separately from application logs via `platform/observability/security_events.py`** (P2, S5)
- **D27: OTel is the observability portability boundary; vendor-specific observability code is confined to adapters** (P2, S5)
- **D28: Python package named `zephyr` to decouple implementation namespace from product name** (P2, pre-S6). Superseded in spirit by D38 rename to padhanam.
- **D29: Product name changes from Quorum to Zephyr** (P2, post-S6). Later renamed to padhanam at D38.
- **D30: uv workspace topology — root pyproject is cross-cutting platform package; bounded contexts and apps are workspace members** (P2, S7)
- **D31: Package-level archive document at every package close from P2 forward** (P2, retrospective)
- **D32: Per-tenant Postgres instance topology — separate instances, two at P3 open for the test set, instance creation deferred until production deployment context** (P3, S9)
- **D33: Control-plane database lives on a dedicated Postgres instance, separate from tenant data planes** (P3, S9)
- **D34: Credential encryption integration shape and three-control leak prevention** (P3, S10)
- **D35: Audit destination convention promoted from S10 reflection** (P3, S11)
- **D36: Per-tenant connection routing layer with cached session factories and two-phase migration runner** (P3, S11)
- **D37: Audit adapter shape with hash-chain concurrency control and cache deferred** (P3, S12)
- **D38: Project reframe as learning sprint and rename zephyr → padhanam** (P3, S13)
- **D39: Project framing reframed from learning sprint to product-led AI-assisted enterprise development case study** (P3 post-close strategic session). Pending-authorship framing on methodology.md superseded by D113.
- **D40: Methodology measured against DORA Four Keys and CORE4 dimensions** (P3 post-close strategic session)
- **D41: Cost capture and per-tenant attribution committed as Phase 1 architectural commitment** (P3, post-close strategic session)
- **D42: Decision-discipline frameworks — Kano on D-entries, RICE on prioritisation** (P3, post-close strategic session)
- **D43: Living-document discipline for PRDs, package epic notes, and user stories** (P3, post-close strategic session)
- **D44: Living roadmap as canonical strategic-tree artefact with versioned reasoning categories** (P3, post-close strategic session)
- **D45: PRFAQ as living external-voice artefact, refreshed at every phase audit** (P3, post-close strategic session). Voice/audience superseded by D51.
- **D46: Role-function audit categories integrated into phase audits and per-session tagging** (P3, post-close strategic session)
- **D47: Two-surface mode separation maintained by declaration discipline rather than UI separation** (P3, post-close strategic session)
- **D48: Mid-session capture surface for stray thoughts** (P3, post-close strategic session)
- **D49: Cost-capture wiring shape** (P4, S14)
- **D50: TenantContext value object — shape, location, and propagation** (P4, S15)
- **D51: PRFAQ voice and audience supersede D45's case-study framing** (P4-post, carryover-cleanup strategic session). Later superseded for methodology-as-product audience by D93.
- **D52: Identity foundation deferred to Phase 2, supersession of D3** (P4-post, carryover-cleanup strategic session)
- **D53: P5 evaluation harness framing — scoring sheet primitive, per-tenant storage, appliers-as-data, Reading-C human-oversight posture** (P5, P5-open strategic block, 2026-05-06)
- **D54: Applier port shape — single polymorphic async ApplierPort with applier_type dispatch in the adapter** (P5, S16, 2026-05-06)
- **D55: Score representation on rubric_applications — text with criterion-level interpretation** (P5, S16, 2026-05-06)
- **D56: TraceQueryPort method shape — interface segregation, separate methods per access pattern** (P5, S17b, 2026-05-06)
- **D57: Cost-query path — two-layer abstraction (evaluation → observability use case → trace store port)** (P5, S17b, 2026-05-06)
- **D58: Regression report shape — single-baseline comparison, per-criterion success-rate deltas, aggregate-only cost-per-task, text and JSON output** (P5, S18, 2026-05-06)
- **D59: Langfuse trace-ingestion asynchrony — polling-with-timeout at the cost-query path** (P5, S18, 2026-05-06)
- **D60: P6 source-ingestion framing — asynchronous pipeline shape, one ingestion bounded context** (P6, P6-open strategic block, 2026-05-07)
- **D61: Parsing scope at P6 close — markdown and plain text at S19; PDF, DOCX, HTML defer** (P6, S19, 2026-05-07)
- **D62: Embedding model default and chunk-embedding column shape — nomic-embed-text via Ollama, single column on chunks, HNSW cosine** (P6, S20, 2026-05-07)
- **D63: Neo4j topology — shared instance with tenant-property scoping enforced through a tenant-scoped session wrapper plus contract tests** (P6, S21, 2026-05-07)
- **D64: Graph extraction shape — Qwen 2.5 7B via LiteLLM structured output, single `:Entity` node, free-form `entity_type`, no taxonomy commitment** (P6, S21, 2026-05-07)
- **D65: RetrievalClient port surface, cross-track readiness, and ChunkEmbedder task-hint refinement** (P6, S22, 2026-05-07)
- **D66: Hybrid composition architecture — agent-runtime-executed composition with layered strategy selection and a three-strategy starter catalogue** (Data-retrieval design session, between-packages strategic block, 2026-05-07). `parallel_rrf` deferred per deferred-decisions entry.
- **D67: Filter expression architecture — typed Boolean tree with bounded leaf operator vocabulary, scope-pre-composition / cut-off-post-composition pipeline split, and a six-operator starter set** (Data-retrieval design session, between-packages strategic block, 2026-05-07)
- **D68: P7 agent-CRUD framing — two bounded contexts (methodology and agent) with revision-shaped hash-chain audit; methodology templates on control plane; agents per-tenant; tool allowlist as opaque strings deferring registry to P8** (P7, P7-open strategic block, 2026-05-08)
- **D69: Prompt injection threat model and agent-runtime defences** (P7 strategic block)
- **D70: Cryptographic erasure for right-to-erasure under append-only audit chains** (P7 strategic block)
- **D71: Tool execution sandboxing** (P7 strategic block)
- **D72: Image signing and SLSA build-provenance attestation** (P7 strategic block)
- **D73: Post-quantum cryptography readiness** (P7 strategic block)
- **D74: Methodology aggregate shape, hash-chain content surface, repository interface, and CLI shape** (P7 S24). Revised at D81 (v2, multi-role refinement).
- **D75: Agent aggregate shape, methodology lineage, hash-chain helper promotion, repository interface, auth posture, and CLI shape** (P7 S24/S25)
- **D76: Principle refinement on forking, in supersession of D14's prior "forbidden" phrasing** (P7 mid-package strategic block, consumer-direction placement, 2026-05-09)
- **D77: Consumer-direction placement — discharge through personal-use deployment, no pivot, no expansion, no separate consumer build** (P7 mid-package strategic block, 2026-05-09)
- **D78: Personal-use deployment of public Padhanam as evidence of D14's customer-deployment scenario** (P7 mid-package strategic block, 2026-05-09)
- **D79: Cross-context create_agent_from_methodology flow shape — agent-owned cloning via callable api-facade ports, MethodologyView and SourceLookup as consumer-side abstractions** (P7 S25, 2026-05-10)
- **D80: Four-layer constraint stack — platform invariants, methodology, workflow, agent** (P8 framing, topology design session, 2026-05-11)
- **D81: Methodology aggregate v2 — multi-role refinement with per-field binding mode** (P8 framing, topology design session, 2026-05-11; v2 to D74)
- **D82: Platform invariants and Padhanam-as-intelligence-layer** (P8 framing, topology design session, 2026-05-11)
- **D83: Workflow as architectural primitive — `contexts/workflow/` commitments and Phase 2 implementation** (P8 framing, topology design session, 2026-05-11)
- **D84: P8 agent runtime adapter shape and LangGraph deferral to Phase 2** (P8 framing, topology design session, 2026-05-11)
- **D85: McKinsey 7-Step methodology authoring placement** (P8 framing, topology design session, 2026-05-11)
- **D86: Role-first architectural model — roles as primary first-class aggregates; methodologies as playbooks composing roles with workflow specification; skills as Phase 2 orthogonal capability concept** (Strategic-mode, P8 pre-build, 2026-05-11)
- **D87: Override-mode space and structured on-disk overrides — augment, replace, tighten; per-field default modes; authoring projection from flat to structured** (P8, S26b, 2026-05-12; refinement of D86 sub-commitments (b) and (e))
- **D88: Agent runtime architecture — AgentExecutor port, AgentLoopExecutor adapter, tool-call extension to InferencePort, agent-context retrieval and overrides ports, D87 resolver at agent context, retrieval-as-only-callable at Phase 1** (P8, S27b, 2026-05-12). Sync signature later revised by D90 to streaming.
- **D89: Tool registry aggregate, classification-to-invariant mapping, two-thin-ports replacement of retrieval branch, backward-compatibility stub at revision creation, Phase 1 authoring prohibition on high-classification tools** (P8 framing, S28b, 2026-05-12)
- **D90: Streaming runtime architecture — structured event vocabulary at domain layer, streaming as only executor pathway, nested OTel span hierarchy with simple audit, transport-neutral runtime with SSE adapter** (P8 framing, S29b, 2026-05-12; revises D88 to streaming-only)
- **D91: Brand specification as charter-grade — placement under `charter/brand/`** (Brand-as-charter-grade strategic block, 2026-05-13)
- **D92: Phase 1 scope confirmed at P1 through P12 with P9-P12 reframed as backend-only substrate; UI elements deferred to Phase 2** (Phase 1 / Phase 2 boundary strategic block, 2026-05-13)
- **D93: Phase 2 direction is methodology-as-product positioning with focus purely on UX/UI** (Phase 1 / Phase 2 boundary strategic block, 2026-05-13)
- **D94: P9 run-history substrate framing; per-tenant Postgres canonical with snapshot citations, single-transaction completion seam, new `contexts/run_history/` bounded context, consumer-defined UX-shaped query port** (P9, P9-open strategic block, 2026-05-13)
- **D95: P9 run-history concrete schema for `runs`, `run_chunk_citations`, `run_entity_citations`; FK-deletion-behaviour commitments preserve snapshot fidelity; write-timing commitment yields terminal event before projection write; audit-chain partial-state shape preserves projection for recorded-activity-but-chain-incomplete invocations** (P9, S31, 2026-05-13)
- **D96: Citation surface — agent-context-owned candidate types, ToolCallCompleted event extension, single-transaction multi-table write, source_snapshot JSONB schema revision, within-run deduplication** (P9, S32, 2026-05-13)
- **D97: P9 run-history read surface — RunHistoryReader port, RunRecord-as-aggregate, four-filter list vocabulary, cursor pagination, storage-versus-render discipline at read surface** (P9, S33, 2026-05-13)
- **D98: P9 run-history HTTP read surface — response DTOs mirror RunRecord 1:1, six-parameter query vocabulary, error response body shape with eleven-path map, principal-derived tenant context per S29b** (P9, S34, 2026-05-14)
- **D99: Two-tier integration test strategy — default tier excludes real-LLM tests; live-LLM tier runs on opt-in cadence** (P9 carryover, S35a, 2026-05-14)
- **D100: CLI settings flow through composition root, not fresh from environment per command** (P9 carryover, S35a, 2026-05-14)
- **D101: Tenant registry carries actor provenance via `created_by_user_id` column for fixture-guard symmetry with methodology/role/tool tables** (P9 carryover, S35a, 2026-05-14)
- **D102: P10 audit log read substrate framing — extension of existing audit context, two-destination model, chain integrity verified on read at page granularity reusing compute_event_hash primitives, HTTP transport with separately authorized routes, ingestion management HTTP API absorbed at P10** (P10, P10-open strategic block, 2026-05-14)
- **D103: Platform-operator principal type as discriminator-field claim on D23 signed-token backend, complementary to existing `Principal.roles`; HTTP transport for audit reader with two route trees and 403 path extension on error response** (P10, S37 commit 1, 2026-05-14)
- **D104: Auth error handler cross-cutting registration via `register_auth_error_handlers` at `apps/api/_auth_errors.py`; HTTP transport for ingestion management with three read routes consuming the ingestion application layer directly via Path A (extend `SourceRepositoryPort` with `list_sources` + add `list_sources` application use case); under principal-derived tenant context** (P10, S38 commit 1, 2026-05-14)
- **D105: P11 retrieval-evaluation framing covering new bounded context, tenant-authored gold sets, recall and precision and MRR starter metrics, and no-retrieval gap closure at P11 open** (Retrieval-evaluation design session, between-packages strategic block ahead of P11, 2026-05-14)
- **D106: Reserved and not used.** No decision committed at this number. The numbering gap between D105 and D107 reflects a number reserved at P11-open framing or pre-P11 hygiene work that did not land as a numbered D-entry. The gap is preserved rather than back-filled per the append-only discipline; the next available number was used (D107).
- **D107: Session log archival cadence shifts to per-package on close** (Pre-P11 hygiene, S38b, 2026-05-15)
- **D108: P11 optimization-engine framing covering new bounded context, four-session split, recommendation aggregate shape, four-category recommendation set, allowlist closure at S39, HTTP transports at S42** (P11 framing, between-packages strategic block ahead of S39, 2026-05-15)
- **D109: Retrieval evaluation gold-set domain shape commits to revision-with-hash-chain aggregate following the methodology-context precedent; lifecycle ships at application-layer granularity for the first time in Phase 1** (P11 S39, 2026-05-15)
- **D110: Retrieval-evaluation runner co-located with gold-set substrate, ships per-query plus aggregated result records, invokes retrieval client directly via the agent-level adapter with audit-context-event-level tamper-evidence absorption** (P11 S40, 2026-05-15)
- **D111: Optimization layer substrate ships OptimizationRun and Recommendation aggregates, pluggable RecommendationRule and MetricCalculator domain abstractions, discriminated evidence citations with structured caveat annotations, and audit-chain-absorbed tamper-evidence across the engine-invocation and recommendation lifecycles** (P11 S41, 2026-05-15)
- **D112: HTTP transport surface ships routes for the retrieval_evaluation and optimization producer-context substrates with JWT-resolved tenancy, cursor pagination, Pydantic discriminated-union DTOs, and OpenAPI specification as procurement-grade Phase 2 UX-consumer documentation, all under the existing flat-module router convention** (P11 S42, 2026-05-15)
- **D113: Methodology document is the active living-hypothesis surface; supersedes D39's "pending operator authorship" framing without rewriting D39** (P12 Phase 1 close audit, 2026-05-16)

## Phase 2 decisions

New entries below this line.

---
