# P12 audit inputs

This file consolidates methodology candidates and architectural-honesty observations forwarded from P11 sessions for the P12 audit. Each entry frames the observation, the supporting evidence, and the decision shape the candidate implies for P12 to resolve.

This file is input material for P12 audit, not P12 audit output. P12 audit acts on these entries with charter-track dispositions (D-entry amendments, principle additions, deferred-decision entries, or explicit non-action). Entries are append-only between audit boundaries; P12 audit may move resolved entries to a "P12 resolved" archive section at audit close.

Sourced from: S39 / S39b / S40 / S40b / S41 / S42 session log entries (`log/sessions.md`); `log/captures.md` cumulative captures; pre-P12 hygiene session investigation outcomes.

---

## 1. Pre-write reconciliation as architectural discovery (beyond promotion threshold)

**Observation.** At session-open, Claude Code reads the files the brief names before writing code; surfaces inconsistencies between the brief's assumptions and the as-built codebase reality; raises user-questions; operator resolves with explicit dispositions (often new or amended D-entries). The discipline catches drift between brief-time and write-time that prose review at brief-drafting alone cannot catch.

**Evidence.** Five P11 instances. S39 D109 sibling-precedent finding (`contexts/methodology/` vs `contexts/evaluation/`); S40 D66 framing-vs-as-built strategy enumeration (`parallel_rrf` deferred at adapter layer); S40b graph-extract pipeline reliability deviation surfacing graph_only all-zero aggregates; S41 D111 framing scope (β → δ push-back to commit OptimizationRun as a coupled aggregate); S42 Finding 5 DTO placement deviation (per-context-subdirectory framing vs five-of-five flat-module precedent). Recurrence count is well beyond the methodology-document promotion threshold; multiple prior session log entries name the pattern as a promotion candidate.

**Decision shape implied.** Formal promotion to `charter/methodology.md` (pending operator authorship per D39) as a Patterns-observed entry. The pattern's load-bearing mechanism plus the recurrence trail belong in the methodology document as a constraint on session opening, not in session-log entries that decay into archive after package close.

## 2. Principle-versus-framing drift as distinct methodology candidate

**Observation.** Distinct from pre-write reconciliation's "brief vs as-built codebase" drift; this is "brief vs principles file" drift. The brief frames against no specific codebase reality but contradicts an architectural principle the codebase commits to. Pre-write reconciliation can't catch it because there's no codebase reference to reconcile against; only writing the code and watching the import pattern surfaces the principle violation.

**Evidence.** Two S41 instances: commit 4 rules placement (`contexts/optimization/domain/rules/` framed; `contexts/optimization/application/rules/` structurally honest because rules consume the application-layer EvidenceContext); commit 8 import-linter TYPE_CHECKING edge (broke layers-optimization contract because import-linter parses TYPE_CHECKING blocks as real imports). One S42 instance: Finding 5 DTO placement (per-context-subdirectory framing vs flat-module convention precedent — arguably a hybrid of pre-write reconciliation and principle drift; the deviation is from the established convention which is principle-like).

**Decision shape implied.** Distinct entry in the methodology document. Mitigation surface different from as-built drift: brief-vs-principles check at strategic-mode close (before the build prompt drafts) catches this class. Recurrence test continues at the next session; if instance count grows in P12-and-beyond, the mitigation discipline tightens.

## 3. Scope-check-at-substrate-application-boundary as candidate substrate-session default

**Observation.** Substrate sessions ship domain + application + adapters + tests + smoke; scope is large; operator pause at the natural domain-application transition catches scope expansion that would otherwise surface at smoke time. S41 fired this pattern: the (δ) push-back at pre-write reconciliation expanded scope ~15-20%; mid-execution operator pause at the substrate-application boundary caught the expansion and resumed cleanly.

**Evidence.** One explicit instance at S41 (single P11 occurrence). The pattern is the planned-scope-check moment at the boundary, not the pause itself. The S40 / S40b / S39 sessions did not fire this pattern because they didn't have substrate expansion at execution time.

**Decision shape implied.** Recurrence test pending. P12 input: should substrate sessions plan a scope-check at the domain-application boundary by default, or remain reactive to operator pause? If the candidate is treated as a default, the brief format needs a "scope-check point" section. If reactive, the pattern remains operator-driven without formal codification.

## 4. Bridge-session pattern (two confirmed instances)

**Observation.** Bridge sessions sit between substrate sessions and address verification-and-hygiene work that the substrate session cannot ship cleanly. The pattern distinguishes from substrate sessions (which ship architectural surface) and from hygiene sessions (which consolidate end-of-package debt).

**Evidence.** Two P11 instances. S39b sits between S39 (substrate) and S40 (runner) addressing corpus re-ingest, LVTGuide re-seed, and discovery-mode-gold-set rebuild; the substrate work needed verification surface the prior session lacked. S40b sits between S40 (runner) and S41 (optimization) addressing methodologically-clean-gold-set authoring after S39b's gold-set surfaced as contaminated for S41 evidence use. Both bridges produce charter-grade artefacts that downstream sessions cite.

**Decision shape implied.** Two-instance recurrence at P11 close; pattern is methodology-document candidate but not yet beyond promotion threshold. P12 audit assesses whether a third instance lands or whether the pattern stays at two-instance signal level. Forward-relevance: should Phase 2 plan bridge sessions in advance when substrate scope creates verification debt, or remain reactive to substrate-close findings?

## 5. Vendor-flexibility principle operationalisation verdict

**Observation.** S41 is the first session to operationalise the vendor-flexibility principle beyond vendor ports via pluggable domain-layer abstractions (`MetricCalculator` Protocol; `RecommendationRule` Protocol). The verdict at session close: the abstractions feel structurally honest, not over-engineered. The two-method `MetricCalculator` shape was an explicit Finding 1 expansion away from the original single-method draft because the runner consumes both surfaces.

**Evidence.** S41 commit 2 (MetricCalculator extraction with bit-identity preserved across 80 retrieval_evaluation tests); S41 commit 4 (RecommendationRule Protocol plus four default rules); the vendor-flexibility principle text at `charter/principles.md`. Phase 2 graded-relevance implementations (nDCG, MAP) and richer rule-trigger languages have clean swap surfaces without runner change.

**Decision shape implied.** Charter-positive: the principle is operationalisable at consumption-pattern granularity, not just at vendor-port granularity. P12 audit may add an explicit principle paragraph naming "pluggable domain-layer abstractions" as the operationalisation pattern, or may leave the principle as currently framed and rely on session-log evidence for the operationalisation pattern.

## 6. Container-image-lag at smoke surfaces — pattern resolved at S41 close but lesson generalises

**Observation.** Pre-S41, three smoke runs (S39, S40, S41) each independently surfaced the container-image-lag pattern (source changes don't reach the running container without rebuild + digest pin update). The fix landed at S41 close as the `make build-api` Makefile target. S42 smoke surfaced a docker-compose-build-rejects-digest-tag bug in the new target; fixed inline at S42 smoke. Pre-P12 hygiene verifies the fix holds.

**Evidence.** Three S39-S41 instances of the underlying friction; one S42 instance of the fix's own bug. The dev-friction is proportional to rebuild frequency; production-shaped deployment with upstream-image digest pins eliminates the friction surface entirely.

**Decision shape implied.** Resolved at session-close for the dev-rig fast-path concern. The transferable methodology candidate is "smoke-time verification of dev-workflow tooling at the same session that ships it" — the S41 close commit shipping `make build-api` did not exercise the target against the production-shape flow (the commit's own validation used direct `docker build`, the established pattern); first production use at S42 surfaced the bug. Recurrence test continues at the next dev-workflow tooling addition. P12 audit may codify "ship-tooling-with-smoke-exercise" as discipline expectation.

## 7. MRR threshold structural understanding (metric-threshold expectations need grounding)

**Observation.** S40b surfaced that the operator's implicit MRR>0.9 threshold assumption was wrong because MRR was structurally non-discriminating in the S40-era evaluation setup (rank-1 expected chunks against rank-1 retrieval results produce MRR=1.0 across any vector retrieval surface). The structurally-load-bearing surfaces are recall@k and precision@k differentials at @3.

**Evidence.** S40b smoke produced verification re-run c168c2ba with vector_only recall@1 0.555 → 0.400 (−28% relative), recall@3 1.0 → 0.800 (−20%), MRR unchanged at 1.0. The contamination demonstrably broke at the recall@k surface but not at MRR. The S40b-close verdict and the S41 framing brief both privilege recall@k differentials over MRR explicitly forward.

**Decision shape implied.** P12 audit captures the lesson: metric-threshold expectations need structural-understanding grounding rather than gut-intuition framing. The candidate is a methodology-document Patterns-observed entry; the specific MRR-non-discriminating instance is a one-time finding that doesn't repeat structurally because the evaluation setup is fixed. Forward-relevance: when adding a new metric or threshold, ground the expectation in the structural shape of the comparison surface.

## 8. Cost-threshold tuning under production LLM regime (deferred pending consumer evidence)

**Observation.** D111 commitment 5 ships `cost_optimization_rule` with starter threshold $0.10 cost-per-successful-task. The threshold is tuned for the development regime (local Ollama models with effectively zero per-token cost); production LLM regimes (vendor APIs, hosted models) shift the threshold by orders of magnitude. S41 smoke produced substrate-honest zero emission against $0.000246 mean (well below threshold).

**Evidence.** D111 commitment 5 names the threshold as "starter; tuning is Phase 2 evolution as consumer evidence accumulates". S41 smoke at local Ollama regime never triggers the rule; threshold-vs-actual gap is roughly 400x.

**Decision shape implied.** Parked pending consumer evidence (Phase 2 swap-via-UI / consumer-evidence-driven tuning). P12 audit confirms the parked state holds or names a specific scenario where tuning needs to happen earlier. No charter action required at P12 unless the threshold posture has changed.

## 9. `parallel_rrf` retrieval-strategy implementation deferral

**Observation.** D66 catalogues three retrieval strategies (`vector_only`, `graph_only`, `parallel_rrf`); S40 ships the runner against the two executing strategies projected to canonical identifiers `vector_only` and `graph_only`; `parallel_rrf` deferred per `charter/deferred-decisions.md` until activation trigger fires.

**Evidence.** Deferred-decisions entry at `charter/deferred-decisions.md` (added at S40); D110 alternative (i) records the rejection of rewriting D66 to match the as-built two-strategy surface. Pre-write reconciliation Finding 2 at S40 caught the framing-vs-as-built gap.

**Decision shape implied.** P12 audit assesses whether the activation trigger (procurement-grade need for three-strategy comparison) has fired. If yes, schedule the Phase 2 retrieval-adapter extension session; if no, the deferral holds with refreshed trigger language.

## 10. Gold-set aggregate-level audit emission

**Observation.** Gold-set substrate at `contexts/retrieval_evaluation/` ships at S39 without audit-event emission on aggregate-level mutations (creation, append-entry, finalize-revision, name update). Revision content carries hash-chain self-containment per D109; aggregate-level mutations rely on per-tenant DB integrity, which is not procurement-grade tamper-evidence. S39b rename of the synthetic gold-set illustrated the gap concretely.

**Evidence.** Deferred-decisions entry at `charter/deferred-decisions.md` (added at S40); S40 pre-write reconciliation Finding 6 captured the within-context regime distinction across the two existing audit surfaces (revision content vs aggregate mutations).

**Decision shape implied.** Activation no later than Phase 1 close per the deferred-decisions entry's framing. P12 audit confirms back-fill schedule (immediate at a P12 hygiene window, post-P12, or Phase 1 close session itself).

## 11. S39b retroactive corpus version-control gap

**Observation.** S25's synthetic LVT-shaped sources never landed in the repo and are not recoverable; S39b authored substitute LVT-shaped markdown content for the corpus. The retroactive content-version-control gap means tenant_a's S25-era corpus is not bit-identical to any reproducible artefact in the repo.

**Evidence.** S39b session log entry frames the substitute-content reconstruction as bridge-session-shape work; S40b corpus content at `tests/fixtures/corpus/p11_s40b/pacelane_recovery_first_case.md` is the first reproducible-from-repo corpus content.

**Decision shape implied.** P12 audit captures the lesson: future corpus content must land in the repo under `tests/fixtures/` or similar at ingestion time, not only as audit-trail-of-ingestion. Forward-relevance: any new corpus-dependent test or smoke artefact requires corpus content under version control.

## 12. CLI/API wiring-integration-test asymmetry (defensible at pre-P12 hygiene)

**Observation.** Eighteen wiring class pairs ship across CLI and API composition roots through S42; the test surface coverage differs by entry point. CLI side has explicit cross-context adapter tests at `tests/integration/apps/cli/test_cross_context_adapters.py` and `test_cross_context_tool_adapters.py` plus dedicated reader-adapter tests for run_history and audit. API side has route-level integration tests that exercise the wiring through TestClient + FastAPI dependency_overrides at `tests/integration/api/test_*_routes.py` (eight test files post-S42).

**Evidence.** Pre-P12 hygiene Finding 2 investigation surface listed at the session entry. The two surfaces test wiring at different altitudes: CLI-side tests verify adapter-construction correctness at the consumer-port-plus-wiring-adapter boundary; API-side tests verify the same wiring through the full HTTP stack including dependency injection.

**Decision shape implied.** Defensible asymmetry: no backfill needed at this hygiene session. The wiring is exercised at both surfaces at adequate granularity for procurement-grade defensibility. P12 audit confirms or revises the assessment; if revised, the candidate work is API-side explicit wiring tests mirroring the CLI-side construction-correctness pattern.

## 13. Graph-extract pipeline reliability (structural finding at pre-P12 hygiene)

**Observation.** S40b smoke surfaced graph_only retrieval consistently returning all-zero aggregates because the graph-extract pipeline did not reliably extract entities from the S25/S39b corpus. Pre-P12 hygiene investigation surfaces the structural gap: the `EXTRACTING` state in `contexts/ingestion/domain/state.py` has no reclaim-after-timeout policy. A worker dying mid-extraction (LLM-call hang, container kill, transaction-rollback edge case) leaves the source stuck in `EXTRACTING` indefinitely; no other worker picks it up; the source never reaches `INDEXED` or `EXTRACTION_FAILED`.

**Evidence.** S40b methodology candidate ("graph-extract pipeline reliability as future hygiene session candidate"); `contexts/ingestion/application/extract_source.py` plus `contexts/ingestion/adapters/outbound/postgres/source_repository.py` inspected at pre-P12 hygiene Finding 1 investigation; no reclaim-after-timeout transition implemented; LLM extraction calls have no timeout enforcement at the worker boundary.

**Decision shape implied.** Structural — requires reclaim-after-timeout policy plus transaction semantics that survive worker death. Landed at `charter/deferred-decisions.md` per pre-P12 hygiene Finding 1 disposition. Activation trigger: any Phase 1 close or Phase 2 work that depends on graph retrieval producing entities reliably (workflow agents that depend on graph evidence; recommendation rules that cite graph state). Operational mitigation at Phase 1: manual re-trigger via CLI for sources stuck in EXTRACTING.

## 14. Hygiene-session-as-shape observation (this session)

**Observation.** Pre-P12 hygiene is the first explicit hygiene-shaped session in P11. Distinct from substrate sessions (ship architectural surface), bridge sessions (verification-and-hygiene between substrate sessions), and transport sessions (HTTP layer atop existing substrate). Hygiene sessions consolidate end-of-package debt: documentation expansion, methodology-candidate consolidation, dev-tooling hardening, structural-finding documentation, stray-artefact cleanup.

**Evidence.** This session's seven-item scope: README expansion, p12-audit-inputs consolidation, make build-api verification, graph-extract investigation, CLI/API wiring parity verification, validator loosening, stray directory cleanup. No new D-entries (per the brief's commitment); no new architectural decisions; outputs are documentation + small fixes + structural findings forwarded to P12.

**Decision shape implied.** P12 audit assesses whether hygiene-shaped sessions warrant methodology-line treatment as a distinct session shape. Recurrence test pending: does Phase 2 plan a hygiene session at each phase boundary by default? If yes, codify the shape with brief-format expectations (smaller scope, mixed commit prefixes, no new D-entries, structural findings forwarded to next audit). If no, the pattern stays as one-instance observation.

---

## How P12 audit acts on this file

For each entry above, P12 audit produces one of four disposition types:

1. **Charter amendment.** D-entry edit, principle addition, or roadmap version update. Captures the resolution permanently in the binding-specification surface.
2. **Methodology-document entry.** Promotion of a P11 pattern to `charter/methodology.md` (pending operator authorship per D39) with the operationalisation and recurrence trail.
3. **Deferred-decisions entry.** New or updated entry at `charter/deferred-decisions.md` with refreshed activation trigger language.
4. **Explicit non-action.** Entry remains in this file with the audit's "non-action" disposition recorded; recurrence test continues until next phase audit.

P12 audit may also add new entries that surface during the audit conversation itself. The audit's output artefact updates this file with disposition annotations per entry plus any new audit-surfaced entries.
