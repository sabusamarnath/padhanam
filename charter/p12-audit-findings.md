# P12 audit findings

This document is the Phase 1 close audit's consolidated deliverable. Findings are organised into three sections: top-down findings from D-entry verification, bottom-up findings from the codebase tour, and audit-inputs dispositions for the 14 entries at `charter/p12-audit-inputs.md`.

Each finding cross-references where its resolution lives (D-entry number for charter amendments, principle reference for principle modifications, deferred-decisions entry for Phase 2 deferrals, methodology section for methodology updates, or explicit non-action with reasoning). Code-level corrections from audit findings land at follow-on sessions; this document is the synthesis artefact.

The audit reads against the canonical charter set at the time the file landed (D1 through D112; principles.md including the User safety section per D82 and the Vendor flexibility principle per D111; schema.md at the post-S41 + post-S42 state; deferred-decisions.md including the graph-extract reliability entry per pre-P12 hygiene Finding 1) and against the as-built reality at `contexts/`, `apps/`, `padhanam/`, `tests/` at pre-P12 hygiene close (commit afabe7a). The 14 audit-inputs entries are quoted by index from `charter/p12-audit-inputs.md`.

## Section 1: Top-down findings (D-entry verification)

D-entries D1 through D112 verified against as-built. Findings below capture drift requiring disposition; D-entries that verified cleanly are not enumerated. Substantive drift is rare; most P11 D-entries shipped tightly against their commitments.

### Finding T1: D109's "S39 implementation correction" preserves audit trail of pre-write reconciliation miss

D109 commits the gold-set domain shape and includes a strategic-mode plan for compute_chained_payload_hash extraction inside `contexts/audit/domain/events.py` (commit 2.5 in the S39 brief). The plan did not ship. Mid-build reconciliation surfaced the existing `padhanam/security/hash_chain.py` primitive (promoted from `contexts/methodology/` at S24 commit 8 per D75) and the gold-set substrate reuses it directly without triggering an audit-context refactor.

The D-entry handles the drift correctly: the body of D109 stands as the strategic-mode plan; an explicit "S39 implementation correction (appended at session close, 2026-05-15)" section names the three concrete corrections (the audit-context refactor did not land; the primitive already existed at the platform layer; substitution rule for the body) and provides cross-references to the methodology line in the S39 session log entry and the smoke document's "Deviations from the brief" section.

**Disposition.** Non-action at P12. The append-only correction discipline is the structurally honest pattern; the body-plus-correction shape is what the audit-trail commitment requires. The methodology surface absorbs the pattern (mid-build pre-write reconciliation as a distinct sub-pattern of pre-write reconciliation) at Section 3 entry 1's disposition.

### Finding T2: D39 stale framing "(pending operator authorship)" remains active across charter files despite methodology.md being authored and actively maintained

D39 (P3-era) committed methodology.md as a deliverable pending operator authorship. Methodology.md exists, was authored at v1 (P3 post-close per its own version log), and has been the canonical surface throughout Phase 1. The pre-P12 hygiene README expansion repositioned the language from "pending operator authorship per D39" to "methodology framing as living hypothesis" but did not propagate the rebrand into the rest of the charter.

As-built drift sites where the stale "(pending operator authorship per D39)" framing remains:
- `charter/principles.md` line 45 (in the Engineering practice section: "Methodology is measured against DORA and CORE4 per D40. Definitions and cadence will live in `charter/methodology.md` (pending operator authorship per D39).").
- `CLAUDE.md` "Methodology capture" section (refers to "pending operator authorship per D39" and the gap "tracked as a carryover in `current-package.md`"; no such carryover exists post-P11).
- `charter/deferred-decisions.md` "Methodology metrics" entry (refers to "the tagging format that will be specified in `methodology.md` (pending operator authorship per D39)").
- `charter/deferred-decisions.md` "Methodology mechanical-enforcement upgrades" preamble naming `methodology.md` content as the principle landings.
- `charter/methodology.md` version log v1 entry self-referentially names "fulfilling the methodology-document commitment in D39."

**Disposition.** Charter amendment via a new D-entry confirming methodology.md is the active living-hypothesis surface forward, superseding D39's "pending operator authorship" framing without rewriting D39. The principles.md line 45 amends in place at the same commit. Other sites (CLAUDE.md, deferred-decisions.md preamble) update at hygiene moments rather than as part of P12 since they are doc-content rather than binding-specification surface; the new D-entry is the binding correction. Resolution at Section 3's audit-amendments commit chain (commits 5 and 6 in the audit's commit-shape sequence).

### Finding T3: D66's three-strategy catalogue versus the two-strategy as-built adapter — already dispositioned at D110 + deferred-decisions

D66 catalogues three retrieval strategies (vector_only, graph_only, parallel_rrf); the `AgentRetrievalClientAdapter` ships two; `parallel_rrf` is unimplemented at the adapter. D110 alternative (i) explicitly rejected rewriting D66, and the `parallel_rrf` deferred-decisions entry holds the gap with activation trigger language.

**Disposition.** Non-action at P12. The charter-track resolution is already in place via D110 alternative (i) plus the deferred-decisions entry. The audit-inputs entry 9 disposition (Section 3) confirms the parked state holds and refreshes the activation trigger language with the P12-audit-completed verdict on procurement-grade need for three-strategy comparison: not surfaced at Phase 1 close, deferral continues to Phase 2.

### Finding T4: D14's "Forking the platform codebase is forbidden" phrasing was superseded explicitly by D76

D14 originally carried "Forking the platform codebase is forbidden" as a principle. D76 (P7 mid-package strategic block, 2026-05-09) refined the phrasing to "The platform is designed so forking is unnecessary; observed forks signal extension surface failure to be addressed upstream." The principles.md file at line 16 carries the refined wording.

**Disposition.** Non-action at P12. Supersession was explicit, the refinement holds, and the audit trail is preserved. No drift.

### Finding T5: D89's "per-tenant tool authoring deferred to Phase 2" — tool storage at control plane, not per-tenant, despite P8 epic note framing

D89 commits tools and tool_revisions to the control-plane Postgres instance, against the P8 epic note's "per-tenant per D32 (tenants configure their own tools per D14)" framing. D89's reasoning paragraph explicitly resolves the cross-plane reference problem: control-plane `role_revisions.tool_allowlist` cannot durably pin per-tenant tool UUIDs. The per-tenant tool authoring lift defers to Phase 2 via consumer-evidence-driven trajectory.

**Disposition.** Non-action at P12. The deferral was explicit at D89 alternative (h); the architectural reasoning was sound; D78's personal-use deployment provides the eventual consumer-evidence path. No drift.

### Finding T6: D90's streaming-only `AgentExecutor` shipped against the original D88 sync `AgentExecutor` signature with explicit revision

D88 (S27b) committed `AgentExecutor.execute(context) -> AgentResult` as the original Protocol shape. D90 (S29b) revised to `execute(context) -> AsyncIterator[AgentEvent]` with the method name preserved. The revision is documented in D90's body and the as-built `contexts/agent/ports/executor.py` carries the streaming signature.

**Disposition.** Non-action at P12. The revision was explicit; D88 stands with the substrate intent; D90 carries the streaming-only refinement under explicit supersession framing. No drift.

### Finding T7: D107 session-log archival cadence — bootstrap landed, per-package archival on P11 close is in flight at P12

D107 commits per-package session-log archival on package close, forward from P11 close, with a one-time S38b bootstrap covering P0 through P10. The bootstrap shipped at S38b (verified). P11's session entries (S39 through S42 plus pre-P12 hygiene plus the upcoming P12 entry) remain in the live `log/sessions.md` and archive at P11 close, not before.

**Disposition.** Non-action at P12. The cadence is honoured; P11 close lands at the audit-close commit chain. The audit's own session log entry lands in the live file and travels with the rest of P11 to the package archive at the package-close commit.

### Finding T8: D111's MetricCalculator and RecommendationRule pluggable domain abstractions operationalise the vendor-flexibility principle at consumption-pattern granularity

D111 ships pluggable RecommendationRule and MetricCalculator Protocol abstractions; the vendor-flexibility principle at `charter/principles.md` landed alongside D111 with explicit "Procurement-grade commitment: vendor lock-in is not architectural" language and naming of MetricCalculator + RecommendationRule as the operationalisation pattern. The audit-inputs entry 4 frames the verdict and proposes either explicit principle paragraph addition or session-log evidence reliance.

**Disposition.** Non-action at P12. The principle text in place at S41 is structurally honest and already names the operationalisation; no further amendment needed at audit time. The methodology document captures the pattern at Section 3 entry 4's disposition.

### Finding T9: D112's flat-module router convention reinforced as principle-versus-framing-drift instance

D112 explicitly committed the flat-module router convention against the brief's per-context-subdirectory framing (Finding 5 deviation caught at session open). The convention reinforcement is recorded in D112's body and alternatives (a)/(b)/(c) of D112 explicitly reject the subdirectory shape. The methodology candidate at audit-inputs entry 2 (principle-versus-framing drift) absorbs this as the third P11 instance.

**Disposition.** Non-action on the D-entry; the methodology candidate carries forward per Section 3 entry 2's disposition.

### Findings not surfaced: D-entries that verified cleanly without drift

D1 through D108 (excluding D14/D39/D66/D88 noted above) verified cleanly against as-built. The bet's substrate commitments (hexagonal architecture per D16, no-vendor-SDKs-in-domain per D4, audit-as-bounded-context per D26, database-per-tenant per D32, jurisdiction-as-first-class per D12, tenant-isolation contract tests per D24, charter touch-points per CLAUDE.md, append-only logs per D29, decision discipline per D42, methodology-aggregate evolution from D74 → D81 → D86 → D87 → D89, agent runtime architecture per D88 → D90, four-context P11 substrate per D108 → D109 → D110 → D111 → D112) all ship in code matching the D-entry shape.

The four-context P11 substrate scaffold is structurally complete (`contexts/retrieval_evaluation/`, `contexts/run_history/`, `contexts/audit/`, `contexts/optimization/`) and the consumer HTTP surface for all four ships at S34, S37, and S42. The bet's success criterion 4 (the trace capture layer surfaces optimization recommendations, not just data) holds end-to-end at substrate level; the Phase 2 UX deliverable closes the criterion fully per D93.

## Section 2: Bottom-up findings (as-built tour)

Tour covered `contexts/`, `apps/`, `padhanam/`, `tests/`, and `padhanam/persistence/migrations/`. Findings below capture work that ships in code without a clear D-entry authorisation, accumulated conventions worth naming, or data shapes worth promoting to schema.md.

### Finding B1: Twelve bounded contexts in `contexts/` — fully authorised, count exceeds rough expectations

The codebase has twelve bounded contexts: agent, audit, evaluation, inference, ingestion, methodology, observability, optimization, retrieval_evaluation, run_history, tenancy, tools. Each maps cleanly to D-entry authorisation: agent (D86, D88, D90), audit (D26, D102), evaluation (D8, D53, D55), inference (D4, D88 extension), ingestion (D5, D60, D62, D63, D64, D65), methodology (D74, D81, D86, D87), observability (D49, D57; the observability *bounded context* per D16's reading distinct from the platform-cross-cutting observability primitives at `padhanam/observability/`), optimization (D108, D111), retrieval_evaluation (D105, D109, D110), run_history (D94, D95, D97), tenancy (D32, D34, D36, D101), tools (D89). The split between `contexts/observability/` (analysis-layer domain logic) and `padhanam/observability/` (span emission infrastructure) is structurally honest per D16 and the principles file: cross-cutting plumbing belongs in `padhanam/`, domain logic belongs in `contexts/`.

**Disposition.** Non-action. The count is correct, every context is charter-authorised, the split is principled. The observation lands as documentation that the count is twelve, not nine; future audit conversations inherit the count without rediscovery.

### Finding B2: Tenant audit HTTP route at `/tenant/{tenant_id}/audit/test-event` is a session-scoped operator utility not enumerated in HTTP-surface D-entries

`apps/api/routers/tenant_audit.py` exposes a `POST /tenant/{tenant_id}/audit/test-event` endpoint per S12-era integration testing requirements. The endpoint is operator-context-gated via `OPERATOR_ROLE` and emits a probe audit event to verify the per-tenant audit chain. D-entries that frame HTTP surface (D98 run-history, D103 audit reader, D104 ingestion management, D112 retrieval_evaluation + optimization) do not enumerate this endpoint; its existence traces to the integration-testing carryover from S12.

**Disposition.** Non-action at P12. The endpoint is operationally legitimate (verifies audit-chain-write path with operator-context authorisation), the security gating is correct (OPERATOR_ROLE plus operator-context principal), and absence from the HTTP-surface D-entries reflects that those D-entries scope to Phase 2-UX-consumer surfaces, not operator utilities. Documentation gap is minor and does not affect procurement-grade defensibility; future hygiene session could append the endpoint to `apps/api/routers/` documentation if the surface grows.

### Finding B3: `TenantContext` shared-kernel value object and `ErrorResponse` HTTP-layer DTO not formally enumerated in schema.md

`shared_kernel/tenant_context.py` defines `TenantContext` as a frozen value object with three fields (tenant_id, jurisdiction, cost_attribution_id) per D34 + D50. `apps/api/_errors.py` defines `ErrorResponse` Pydantic shape with fields (error_code, message, correlation_id, details) per D98 narrative.

Both shapes cross multiple bounded contexts and ship to procurement-grade consumer surfaces (OpenAPI specification renders `ErrorResponse` as the canonical error wire format). Neither appears in `charter/schema.md`'s formal enumeration; their existence and shape are documented narratively across D34, D50, and D98 but not in the binding-specification surface.

**Disposition.** Non-action at P12 with a documentation note for hygiene at Phase 2 entry. The shapes are structurally well-defined in code, the narrative D-entries cover the design rationale, and adding them to schema.md is hygiene work, not audit-disposition work. Phase 2 entry's brief drafts a schema-supplement workitem covering these shapes plus the canonical cursor codec shape from S33 (which is similarly shape-defined in code without schema.md formalisation). The audit-surfaced entry 17 captures this.

### Finding B4: 27 import-linter contracts + 11 AST enforcement tests + 148 tenant-isolation contract scenarios + 18 HTTP contract scenarios + 33 integration API tests

Numbers verified by the tour. Architectural enforcement count breakdown:
- Import-linter contracts: 27 (12 hexagonal-layers-per-context + 3 cross-context-independence + 1 platform-isolation + 1 domain-purity + 1 shared-kernel + 9 vendor-SDK-confinement + 2 agent-isolation including the new `layers-optimization` contract from S41).
- AST enforcement tests at `tests/_enforcement/`: 11 files covering invariants import-linter cannot express (no-os.getenv-outside-config, no-plaintext-in-state, no-raw-neo4j-sessions, no-vendor-SDKs-in-domain, no-Dockerfile-workspace-misses, port-bindings, OTel-provider-setup, and others).
- Tenant-isolation contract scenarios: 148 covering every adapter touching tenant-scoped data per D24 red-team shape.
- HTTP-layer contract scenarios at `tests/contract/http/`: 18 covering cursor pagination and error-response body shape canonicalisation across the four list endpoints per S42.
- Integration API tests at `tests/integration/api/`: 33 across eight test files post-S42.

**Disposition.** Non-action. The enforcement count is healthy and trending upward (the discipline-adherence metric the methodology document names as substrate). The phase-audit assessment of the enforcement layer is "the architectural surface keeps up with the growing codebase as the principles file commits to."

### Finding B5: Test harness conventions accumulated without explicit D-entry coverage

Three conventions surfaced at tour time:
- Shared fixture pattern at `tests/contract/tenant_isolation/conftest.py` providing `tenant_a_principal` / `tenant_b_principal` / synthetic dual-tenant fixtures.
- Discriminated-union `ErrorResponse` shape with `error_code` discriminator across all HTTP error paths (D98 narrative; structurally consistent across S34/S37/S38/S42).
- Cursor codec at base64-encoded JSON across `contexts/run_history/application/cursor.py`, `contexts/audit/application/cursor.py`, `contexts/retrieval_evaluation/application/cursors.py`, `contexts/optimization/application/cursors.py`. Identical structural shape; module-naming is `cursor.py` for run_history + audit and `cursors.py` for retrieval_evaluation + optimization (S40+S41 framing convention).

**Disposition.** Non-action at P12. The conventions evolved during shipping and are structurally consistent across consumers, which is the right indication that the conventions are valid. The cursor codec naming inconsistency (singular vs plural) is hygiene noise; not worth a corrective session. Future audit conversations may surface a candidate methodology-document entry for "test harness conventions evolve in code rather than charter; structural consistency is the success criterion."

### Finding B6: Migration counts confirmed — 13 control-plane + 15 per-tenant

Control-plane Alembic migrations: 13 (through `0013_lvtguide_reseed` plus the S39b-era migrations). Per-tenant Alembic migrations: 15 (through `0015_optimization_substrate`). Each migration ties to a charter-authorising D-entry or to a documented session log entry; no migration ships without authorisation.

**Disposition.** Non-action. Numbers verified; migration discipline holds; no drift.

### Finding B7: No code-level drift from charter substrate commitments surfaced at tour

The codebase faithfully implements D1 through D112 with no unauthorized extensions. Operationally significant findings (the Makefile targets at S41 plus their S42 fix; the observability split at D16) are all explicitly chartered. No code shipped without charter authorisation; no architectural shortcuts surfaced that contradict existing D-entries.

**Disposition.** Non-action. This is the load-bearing verdict for Section 1's "Findings not surfaced" framing: the bet's commitments ship in code, the principles file's commitments hold against the codebase, and the methodology's "architectural discipline survives AI-assisted implementation" load-bearing claim holds at Phase 1 close.

## Section 3: Audit-inputs dispositions

Each of the 14 entries at `charter/p12-audit-inputs.md` gets explicit disposition per the four shapes the brief frames (charter amendment / methodology document / deferred-decisions / explicit non-action). Entries that map cleanly are dispositioned tersely; entries that require operator-engagement reasoning are dispositioned with full alternative-considered framing.

### Entry 1: Pre-write reconciliation as architectural discovery (beyond promotion threshold)

**Disposition.** Methodology document entry. The pattern has five-plus P11 instances on top of the prior P7-P10 reinforcement count; recurrence is well beyond the methodology-document promotion threshold. The methodology document's substantive update (commit 8 in the audit's commit chain) lands "Pre-write reconciliation as architectural discovery" as a Patterns-observed entry with the operationalisation mechanism (read every file the brief names before writing code; surface inconsistencies; raise user-question; resolve with explicit dispositions) and the recurrence trail (sixteen-plus instances spanning S6 LiteLLM env-var quirks through S42 Finding 5 DTO placement).

Sub-pattern: **mid-build pre-write reconciliation as a distinct subtype.** The D109 correction at S39 surfaced this — pre-write reconciliation can fire at session-open (the standard pattern) or mid-build when import statements reveal cross-codebase context the session-open read surface missed (the S39 case where importing the `padhanam.security.hash_chain` primitive surfaced the platform-layer-vs-context-layer-helper distinction). Methodology document captures both surfaces under the single Patterns-observed entry's operationalisation paragraph.

### Entry 2: Principle-versus-framing drift as distinct methodology candidate

**Disposition.** Methodology document entry. Distinct from entry 1's pre-write reconciliation because the mitigation surface differs: pre-write reconciliation catches brief-vs-codebase drift via reading; principle-versus-framing drift catches brief-vs-principles drift via writing-and-watching-imports. Three P11 instances (S41 commit 4 rules placement; S41 commit 8 import-linter TYPE_CHECKING edge; S42 Finding 5 DTO placement) plus the S40b graph-extract substrate-gap surface count as a fourth structurally-similar instance.

Methodology document's substantive update lands "Principle-versus-framing drift" as a sibling Patterns-observed entry to entry 1. The mitigation discipline is "check the framing against the principles file before writing the prompt" plus the build-time discovery surface ("writing the code and watching the import pattern surface the principle violation catches the drift"). The third P11 instance at S42 reinforces; methodology document carries the entry forward to Phase 2 audit for further recurrence-rate observation.

### Entry 3: Scope-check-at-substrate-application-boundary as candidate substrate-session default

**Disposition.** Explicit non-action at P12; recurrence test continues. The single-instance observation at S41 is not yet beyond the promotion threshold (Padhanam's convention per the methodology document's "Start simple; refactor at the structural-promotion threshold" — three instances). The candidate stays in `charter/p12-audit-inputs.md` (carried forward without disposition annotation) until a second instance fires at the next substrate session or the candidate ages out.

Operator-engagement criterion declined here per the brief's autonomous-disposition rule for non-substantive-drift findings: single-instance observation does not warrant default-codification. The scope-check moment was operator-driven at S41 and remains operator-driven at the next substrate session; codifying as default risks ceremonialising what was structurally honest as operator judgement.

### Entry 4: Bridge-session pattern (two confirmed instances)

**Disposition.** Methodology document entry as a *named session shape* (not as a Patterns-observed entry — different category). Two instances at P11 (S39b, S40b) plus an implicit third instance via the pre-P12 hygiene session which sits at the boundary between substrate-session-bridge and end-of-package-hygiene. The methodology document's substantive update lands a "Session shapes" sub-section with five shapes named: substrate, bridge, transport, hygiene, audit. Each shape gets a distinguishing-characteristics paragraph plus indicator-for-planning framing.

Audit verdict on the open question "should Phase 2 plan bridge sessions in advance when substrate scope creates verification debt, or remain reactive to substrate-close findings?": the methodology document is currently agnostic on the planning question — the shape is named for recognition value, not for forward-planning prescription. Phase 2 substrate sessions inherit the framing without commitment to mandatory bridging. The recurrence test continues at Phase 2 substrate sessions; if Phase 2 substrate work consistently produces bridge sessions, the planning surface promotes.

### Entry 5: Vendor-flexibility principle operationalisation verdict

**Disposition.** Charter-positive non-action at P12. The principle text at `charter/principles.md` already names MetricCalculator + RecommendationRule as the consumption-pattern-granularity operationalisation pattern. No further principle amendment needed at audit time. The methodology document's substantive update captures the broader pattern (vendor flexibility extends from vendor ports to pluggable domain-layer abstractions) as part of the "Vendor flexibility" architectural-discipline framing without adding a new principle.

### Entry 6: Container-image-lag pattern resolved at S41 close; lesson generalises

**Disposition.** Methodology document entry as a Patterns-observed entry plus explicit non-action on the underlying friction (resolved at session-close). The transferable methodology candidate is "smoke-time verification of dev-workflow tooling at the same session that ships it" — this lands as a separate Patterns-observed sub-pattern. The S42 instance (post-S41 `make build-api` target broken by docker compose build's digest-tag rejection) plus the S42-fix inline holding through the pre-P12 hygiene refresh constitutes recurrence-test-positive at first verification cycle.

Promotion threshold question: should "ship-tooling-with-smoke-exercise" be a structural discipline expectation (third-instance promotion to mechanical enforcement) or a methodology-document Patterns-observed entry (descriptive)? Audit verdict: Patterns-observed at P12, with recurrence test continuing at Phase 2's first dev-workflow tooling addition. Mechanical enforcement would require an AST or CI check that's structurally hard to express; methodology entry is the right altitude.

### Entry 7: MRR threshold structural understanding

**Disposition.** Methodology document entry as a Patterns-observed entry. The pattern is "metric-threshold expectations need structural-understanding grounding rather than gut-intuition framing" with the S40b instance as the named evidence (MRR>0.9 implicit assumption was wrong because the evaluation setup made MRR structurally non-discriminating; the structural surface was recall@k at @3). Forward-relevance: when adding a new metric or threshold, ground the expectation in the structural shape of the comparison surface.

Phase 2 implication: the optimization layer's threshold values (0.15 recall@3 delta; $0.10 cost-per-successful-task) are currently starter-value commits in D111. Phase 2 tuning grounds in production-grade structural understanding (real consumer evidence accumulation; the cost-threshold tuning entry per `charter/deferred-decisions.md`).

### Entry 8: Cost-threshold tuning under production LLM regime (deferred pending consumer evidence)

**Disposition.** Non-action at P12; deferred-decisions entry holds with refreshed activation trigger language. The threshold-vs-actual gap is roughly 400x at the local Ollama development regime; Phase 2 production deployment activates the tuning conversation. No specific scenario surfaces at audit time that requires earlier tuning.

The audit refreshes the deferred-decisions activation trigger language to name the procurement-grade-readiness criterion explicitly: a tenant operating against vendor APIs at non-trivial cost rates with a real cost-per-successful-task aggregation surface across at least one full month of run history. The audit's verdict at P12: parked state holds.

### Entry 9: parallel_rrf retrieval-strategy implementation deferral

**Disposition.** Non-action at P12; deferred-decisions entry holds. Activation trigger ("P12 audit surfaces a Phase 1 procurement-grade need for three-strategy comparison") evaluated explicitly: P12 audit does not surface this need. The bet's criterion-4 procurement-grade demonstration holds end-to-end with the two-strategy comparison surface at S40b's gold-set + S41's evidence-citation pipeline (verified by the all-zero CaveatAnnotation surface as procurement-grade-honest about graph_only's substrate state). Fusion implementation is Phase 2 retrieval-adapter extension work; D66 stands without rewrite; deferred-decisions entry holds without refresh.

### Entry 10: Gold-set aggregate-level audit emission

**Disposition.** Deferred-decisions entry refresh plus a new audit-finding annotation. The deferred-decisions entry framing committed activation "no later than the Phase 1 close audit at P12 close." The audit assesses: back-fill is procurement-grade-necessary for Phase 1's "every state change is audit-event-emitted" load-bearing claim under D26; however, the brief explicitly scopes code changes out of P12. The disposition is:

1. The deferred-decisions entry refreshes with the audit's explicit acknowledgement that procurement-grade-readiness at Phase 2 entry requires this back-fill.
2. A new entry at `charter/p12-phase-2-inputs.md` names gold-set audit-emission back-fill as a Phase 2-entry hygiene workitem with operational specificity (extend `contexts/retrieval_evaluation/application/` use cases for create_gold_set / append_entry_to_revision / finalize_revision / rename_gold_set to emit audit events; the rename surface needs an explicit `rename_gold_set` use case which today does not exist — S39b's rename was a direct SQL UPDATE, which is part of the audit-emission gap surfacing in the first place).

Phase 1 close substrate-readiness verdict: the bet's audit-evidence claim holds at the audit-event-chain level for tenant-authored content; the gold-set-aggregate-level gap is a known carryover with named Phase 2-entry remediation. The claim is honestly framed rather than overstated.

### Entry 11: S39b retroactive corpus version-control gap

**Disposition.** Methodology document entry as a Patterns-observed entry. The lesson is "future corpus content must land in the repo under `tests/fixtures/` or similar at ingestion time, not only as audit-trail-of-ingestion." Forward-relevance: any new corpus-dependent test or smoke artefact requires corpus content under version control.

The lesson generalises beyond corpus content to "any artefact a session depends on for reproducibility must be repo-resident at the session that ships it" — the S25-era synthetic sources were operator-deemed-substitutable at S39b without bit-identity to the original because the original did not land in the repo. The methodology document folds this into a single Patterns-observed entry: "Reproducibility artefacts land at the session that ships them; audit-trail-of-creation is necessary but not sufficient for reproducibility."

### Entry 12: CLI/API wiring-integration-test asymmetry

**Disposition.** Non-action at P12. Pre-P12 hygiene Finding 2 already settled the disposition as "defensible asymmetry; no backfill needed because CLI side has explicit cross-context adapter tests at `tests/integration/apps/cli/test_cross_context_adapters.py` and the API side exercises wiring through route integration tests at `tests/integration/api/test_*_routes.py` (eight test files post-S42) via FastAPI dependency injection." P12 audit confirms.

The two surfaces test wiring at different altitudes appropriate to each app's entry point. CLI-side tests verify adapter-construction correctness; API-side tests verify the same wiring through the full HTTP stack including dependency injection. Procurement-grade defensibility holds at the altitude each app exposes.

### Entry 13: Graph-extract pipeline reliability

**Disposition.** Non-action at P12; deferred-decisions entry holds. Pre-P12 hygiene Finding 1 landed the structural finding at `charter/deferred-decisions.md` with three structural pieces named (reclaim policy, worker-side asyncio timeout, optimistic-concurrency-control on reclaim) plus operational mitigation at Phase 1 (manual re-trigger via CLI).

P12 audit refreshes the activation trigger language to add explicit Phase 1-close framing: "production-grade graph retrieval reliability is the prerequisite for Phase 2 workflow agents that depend on graph evidence; the reclaim policy is non-negotiable at production-deployment context." The hygiene finding stands.

### Entry 14: Hygiene-session-as-shape observation

**Disposition.** Methodology document entry as part of the "Session shapes" sub-section landing alongside entry 4's bridge-session-pattern disposition. Hygiene sessions earn the methodology-document treatment because the shape is structurally distinct from substrate (architectural-surface ship) and bridge (mid-substrate verification) and transport (HTTP layer over existing substrate). Five session shapes total: substrate, bridge, transport, hygiene, audit.

Forward-relevance for Phase 2: hygiene sessions at phase boundaries plan by default rather than reactively. Phase 2 framing's session-sequence draft includes a planned hygiene-shaped session at the boundary between substrate work and consumer-UX work; the pre-P12 hygiene precedent's seven-item scope plus the methodology-candidate consolidation pattern carries forward as the template.

## Section 4: New entries audit-surfaced

Entries the P12 audit surfaces beyond the original 14. Each maps to a disposition shape per the audit-input convention.

### Entry 15 (audit-surfaced): D39 stale framing across charter files

**Observation.** Surfaced at Finding T2. Methodology.md is the active living-hypothesis surface; the "(pending operator authorship per D39)" language remains in five-plus charter sites despite the README rebrand at pre-P12 hygiene.

**Disposition.** Charter amendment via new D-entry confirming methodology.md as active living-hypothesis surface, superseding D39's pending-authorship framing without rewriting D39. Principles.md line 45 amends in place at the same audit-amendments commit. Other doc-content sites (CLAUDE.md, deferred-decisions.md preamble) update at hygiene moments rather than P12.

### Entry 16 (audit-surfaced): Twelve-bounded-context count merits documentation note for future audit conversations

**Observation.** Surfaced at Finding B1. The count exceeds rough P11-era estimates; the architecture surfaces both observability-as-context plus observability-as-platform-cross-cut, plus inference, plus tools, plus tenancy as the registry, plus six P5-through-P11 contexts. Each is charter-authorised; the count itself is the surprise. (The P12-era count was twelve; this entry originally froze that figure — see the corrected Disposition.)

**Disposition (corrected post-Ciborra-audit, 2026-05-28).** The original disposition froze the count at twelve "so future audit conversations inherit the documented count without rediscovery." The Ciborra phenomenological audit's Drift section found that artefact itself stale: seven D-authorised Phase-2-A contexts shipped since P12, so the frozen figure drifted to nineteen. An anti-rediscovery note that must itself be re-verified every audit defeats its own purpose. Corrected disposition: do not inherit a frozen count. Future audits derive the count live with `ls contexts/` at audit time. The count is **nineteen as of 2026-05-28** (the twelve P12 contexts plus `audit_conversation`, `daily_briefing`, `intake`, `intent_classification_evaluation`, `messaging`, `mirror_conversation`, `portfolio`) and grows as each new D-authorised bounded context ships. The structurally-honest split between bounded-context observability and platform-cross-cut observability per D16 still holds and is the durable observation worth inheriting; the number is not.

### Entry 17 (audit-surfaced): `TenantContext` and `ErrorResponse` shapes not formalised in schema.md

**Observation.** Surfaced at Finding B3. Both shapes are well-defined in code and narratively documented across D34/D50/D98; neither appears in `charter/schema.md`.

**Disposition.** Non-action at P12 with a documentation note for Phase 2 entry hygiene. The schema.md formalisation is hygiene work, not audit-disposition work; Phase 2 entry's brief drafts a schema-supplement workitem.

## Cross-reference index

Mapping from finding to resolution location.

| Finding | Resolution location |
|---|---|
| T1: D109 correction preserves audit trail | Non-action; methodology entry 1 absorbs pattern |
| T2: D39 stale framing | New D-entry at `charter/decisions.md` |
| T3: D66 vs as-built parallel_rrf | Already at D110 + deferred-decisions |
| T4: D14 "forbidden" supersession | D76 explicit supersession |
| T5: D89 control-plane tools | Non-action; deferral explicit at D89 |
| T6: D88→D90 streaming revision | Non-action; D90 explicit revision |
| T7: D107 session-log archival | Non-action; bootstrap shipped, per-package archival in flight at P12 close |
| T8: D111 vendor-flexibility operationalisation | Non-action; principle text in place at S41 |
| T9: D112 flat-module convention | Non-action; methodology candidate at entry 2 |
| B1: Twelve bounded contexts | Documentation note; audit-surfaced entry 16 |
| B2: Tenant audit test-event endpoint | Non-action |
| B3: TenantContext + ErrorResponse not in schema.md | Phase 2 entry hygiene; audit-surfaced entry 17 |
| B4: Enforcement count | Non-action; healthy trajectory |
| B5: Test harness conventions | Non-action |
| B6: Migration counts | Non-action |
| B7: No code-level drift | Non-action; bet's commitments ship |
| Entry 1: Pre-write reconciliation | Methodology document |
| Entry 2: Principle-versus-framing drift | Methodology document |
| Entry 3: Scope-check-at-substrate-application-boundary | Non-action; recurrence test continues |
| Entry 4: Bridge-session pattern | Methodology document (Session shapes sub-section) |
| Entry 5: Vendor-flexibility operationalisation | Non-action; principle text in place |
| Entry 6: Container-image-lag + ship-tooling-with-smoke-exercise | Methodology document |
| Entry 7: MRR threshold structural understanding | Methodology document |
| Entry 8: Cost-threshold tuning | Deferred-decisions refresh |
| Entry 9: parallel_rrf deferral | Deferred-decisions hold |
| Entry 10: Gold-set audit emission | Deferred-decisions refresh + Phase 2 entry hygiene workitem |
| Entry 11: S39b corpus version-control gap | Methodology document |
| Entry 12: CLI/API wiring parity | Non-action; defensible asymmetry |
| Entry 13: Graph-extract reliability | Deferred-decisions refresh |
| Entry 14: Hygiene-session-as-shape | Methodology document (Session shapes sub-section) |
| Entry 15 (audit-surfaced): D39 stale framing | New D-entry at `charter/decisions.md` |
| Entry 16 (audit-surfaced): Twelve-bounded-context count | Documentation note (this file) |
| Entry 17 (audit-surfaced): Schema.md formalisation gap | Phase 2 entry hygiene workitem |

## Audit verdict summary

The bet's load-bearing claims hold at Phase 1 close:

- A single tenant runs locally with the full stack (verified end-to-end via `make up` plus per-tenant database routing per D32).
- One agent can be configured, run, audited, and optimised through the platform's own tooling (verified at S30b for run, S37 for audit, S41 for optimise).
- The evaluation harness produces meaningful quality signals (S40 retrieval evaluation runner against the S40b clean gold-set produces recall@k differentials that distinguish retrieval-quality state).
- The trace capture layer surfaces optimisation recommendations, not just data (S41 optimization engine produces rule-derived recommendations with full evidence-citation traceability; procurement-grade demonstration holds; Phase 2 UX deliverable closes the bet's criterion 4 fully per D93).
- The operator can explain every architectural decision and why it was made (the audit reads against 112 D-entries each carrying Choice + Reasoning + Alternatives Considered + Kano; the decisions file is the demonstration artefact).
- The methodology document captures the architect-implementer pattern with enough specificity that another senior product leader could read it and adopt the discipline (the methodology document's substantive update at this audit's commit 8 lifts the document from v1 articulation to v2 with Phase 1's accumulated discipline-pattern data points integrated; the methodology is the proprietary insight the platform demonstrates).

Phase 1 closes with the substrate intact, the architectural discipline holding under measurement, and the methodology evidence ready for Phase 2 to consume as the substrate it builds against per D93.
