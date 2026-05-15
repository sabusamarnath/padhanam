# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P11 framed; S39 next

P11 framed at the strategic-mode conversation between S38b close and S39 open on 2026-05-15. D108 commits the optimization-engine substrate as new bounded context at `contexts/optimization/` consuming four producer contexts (evaluation, retrieval_evaluation per D105, run_history, observability) through consumer-defined ports plus wiring adapters, with the `RunHistoryReader` from `contexts/run_history/ports/reader.py` reused per the S33 vintage and three new reader ports defined at S41. The recommendation aggregate carries five fields (category, subject, text, evidence_citations, status); numeric confidence scores stay out on D9 grounds. Four recommendation categories ship at P11 close: retrieval_strategy, model_choice, prompt_revision, cost_optimization. The allowlist closure folds into S39's front half (role-allowlist seed migrations gain the retrieval tool reference); per-invocation retrieval-constraint threading stays Phase 2. HTTP transports at S42 cover three router trees including the P5-deferred evaluation-HTTP carryover absorption. Active testing scheduler integration is P12 territory.

Four sessions firm (S39 allowlist plus `contexts/retrieval_evaluation/` substrate; S40 retrieval evaluation runner and metric computation; S41 `contexts/optimization/` substrate; S42 HTTP transports plus P11 close demo), S43 reserved for optional carryover hygiene. Epic note at [charter/packages/p11-epic.md](packages/p11-epic.md).

**Next Claude Code session.** S39 build session lands the allowlist closure as commit 1 (Alembic migration plus smoke verification adding the retrieval tool reference to seeded role allowlists per the existing migrations) followed by the `contexts/retrieval_evaluation/` substrate as subsequent commits. The S39 prompt drafts at the next Claude.ai conversation handoff.

D107 landed at S38b on 2026-05-15 committing the session-log per-package archival convention with the P0-through-P10 bootstrap; `log/sessions.md` cut from 1879 lines to 56 lines (header plus S38b entry). Forward from S42 close, package archives commit at package-close per D107.

**S39 in flight.** Substrate work for the retrieval evaluation context underway per D108's first commitment and D105's substrate commitments. D109 commits the gold-set domain shape and hash-chain reuse pattern at S39 charter commit. Allowlist closure as commit 2 (forward-only Alembic migration 0012 on the control plane UPDATEs eight seeded role-revision rows — LVTGuide plus seven McKinsey 7-Step roles — to add the retrieval tool reference and recomputes role-revision chain-self-contained hashes per the migration 0010 helper pattern). Audit-context refactor at commit 2.5 extracts `compute_chained_payload_hash` as a thin utility primitive inside `contexts/audit/domain/events.py`; `compute_event_hash` continues to own audit-event input-shaping and calls the helper internally; bit-identity preserved on tenant_a's existing audit chain. Retrieval evaluation context substrate as subsequent commits per D109's six commitments: domain aggregate root plus revision and entry value objects with `compute_revision_hash` wrapper consuming the extracted helper, application use cases for authoring, `GoldSetRepository` write-side port plus `GoldSetReader` consumer-defined read port, Postgres adapter, Alembic migration creating three new per-tenant tables, wiring at both composition roots, CLI surface for discovery-mode gold-set authoring, tenant-isolation contract scenarios, live-stack smoke against tenant_a including hash-chain integrity verification. D109's structural precedent for revision-with-hash-chain is `contexts/methodology/` (not `contexts/evaluation/`'s scoring-sheet, which is read-only at S16); the gold-set is the first Phase 1 context to ship the full create/append/finalize/list/get lifecycle with revision-granularity hash-chain at application-layer granularity. D105's "sibling-contexts-sharing-patterns" framing flagged for the P12 audit per the methodology line in the S39 session log entry; D105 not revised at S39.

**S39b in flight.** Verification-and-hygiene bridge between S39 substrate close and S40 runner work. tenant_a corpus re-ingest from substitute LVT-shaped markdown content (per S39 smoke carryover; S25's original synthetic sources never landed in the repo and are not recoverable), LVTGuide re-seed plus retrieval-allowlist application via new control-plane migration 0013_lvtguide_reseed lifting the LVT system prompt verbatim from briefs/p7/s25.md (per S30b fixture-leak carryover surfaced again at S39 smoke), real-corpus discovery-mode gold-set authoring with the same three queries as S39's synthetic gold-set to produce a structural-comparison artefact for the P12 audit (closes S39 AC 10 verification gap), migration name-length convention captured in log/captures.md as a project-tooling constraint. No new D-entries; this is execution work closing S39's verification gaps.

**S40 closed** at 2026-05-15 with the retrieval-evaluation runner substrate in place end-to-end against tenant_a. Eleven commits closed S40: charter touch-points landing D110 (9e062b7) plus the two new `charter/deferred-decisions.md` entries (parallel_rrf implementation, gold-set aggregate-level audit emission); domain layer with `EvaluationRun` aggregate root, `EvaluationResult` and `EvaluationAggregate` value objects, and metric primitives (a76919b); application use cases (`run_retrieval_evaluation`, `get_evaluation_run`, `list_evaluation_runs`) plus three consumer-defined ports plus 19 new unit tests covering strategy_keys projection, cursor codec round-trip, runner orchestration happy/failure paths, audit-event emission per write, cross-tenant isolation, and pagination (8a86265); Postgres adapters with bound-tenant defence-in-depth and the uuid<uuid cast fix from S33 (b4c44f3); Alembic migration 0014 with status CHECK + terminal-state pairing CHECK + three indices (d9cb409); wiring adapters #13 (`EvaluationRunRepositoryAdapter`) and #14 (`EvaluationRunReaderAdapter`) at the CLI composition root plus `build_evaluation_run_repository`/`build_evaluation_run_reader` factories at the API composition root (e7c02b0); CLI subcommands `evaluation-run start/get/list` with inline `_CliCompositeRetrievalClient` and `_CliRetrievalRunnerPort` wiring helpers, registered under the new `padhanam evaluation-run` typer sub-app (b20262a); twelve new tenant_isolation contract scenarios (8f179fd) extending the harness from 114 to 126; runtime fix at the audit-adapter construction site surfaced at smoke time (21acd36); live-stack smoke against tenant_a's S39b real-corpus gold-set producing run `ef58678a-...` with 6 per-query results plus 2 per-strategy aggregates plus 10 audit events with chain integrity intact (422d9c9). 1105 unit tests pass (+58 from S39b's 1047); 26 import-linter contracts kept. **S40-close verdict on the S39b gold-set's S41 usability: an S40b clean-gold-set bridge session is required before S41 ships.** The S39b gold-set's `expected_chunk_ids` were rank-1 selected from vector retrieval at authoring time and the runner uses the same vector retrieval at evaluation time, so MRR=1.0 is the artefact of two identical functions on the same corpus, not retrieval-quality measurement. Bridge-session-shape methodology candidate confirms at second instance (S39 → S39b verification-and-hygiene; S40 → S40b methodologically-clean-artefact authoring); one more instance at P11 close or P12 would promote.

**S40b closed** at 2026-05-15 with the clean gold-set authored end-to-end against tenant_a and the S41-evidence verdict landed. Five commits closed S40b: charter touch-points at `charter/current-package.md` plus the `.gitignore` rule for `docs/archive/snapshots/` closing the AC 17 cleanliness gap from S40 (ad9d729); corpus content at `tests/fixtures/corpus/p11_s40b/pacelane_recovery_first_case.md` describing a fictional fitness-wearable startup applying LVT — vocabulary divergence from the LVTGuide system prompt is on case-study-specific terms (Pacelane, recovery-first, HRV, Spearman correlation, subscription retention) per the operator's brief-strengthening insight that Query 2 vocabulary needs reframing alongside corpus content (db9cd2d); live-stack smoke against tenant_a (221ef1c) walking corpus refresh, the S39b rename ("P11 retrieval baseline (real corpus)" → "P11 retrieval baseline (rank-selected, S39b)" with hash byte-identical post-rename), clean gold-set authoring with content-fit selection (gold-set `3b001430-...`, finalized revision hash `8fec2553d9...`, three queries with explicit per-entry selection-vs-rank divergence including the borderline "What Pacelane learned" section operator-decided to include), verification re-run producing `c168c2ba-...` with vector_only recall@1 0.555 → 0.400 (−28% relative) / recall@3 1.0 → 0.800 (−20%) / recall@5 1.0 → 0.867 / MRR unchanged at 1.0; this commit landing the session log entry plus this close marker. **S40b-close verdict: contamination demonstrably broke at the recall@k surface; the S40b run can be cited as procurement-grade S41 evidence with the caveat that recall@k and precision@k are the load-bearing metric surfaces and MRR is structurally non-discriminating in this evaluation setup.** Four methodology candidates forwarded to P12 audit: pre-write reconciliation surfacing brief-vs-required-structure gaps (third P11 instance), metric-threshold expectations needing structural-understanding grounding rather than gut-intuition framing (MRR>0.9 threshold operator-owned as wrong implicit assumption), graph-extract pipeline reliability as future hygiene session candidate, and the bridge-session-shape pattern's second instance close. S41 framing brief should privilege recall@k differentials over MRR in evidence-citation specs explicitly.

## P10 — final history (preserved below for traceability)

**P10 framed** at strategic-mode conversation on 2026-05-14.
D102 commits the audit log read substrate as extension of the
existing `contexts/audit/` bounded context: consumer-defined
`AuditEventReader` port on the read side, two-destination model
(per-tenant `tenant_audit` and control-plane `tenant_audit`)
through a destination parameter on port methods, chain
integrity verified on read at page granularity reusing
`compute_event_hash` and `GENESIS_HASH` primitives from
`contexts/audit/domain/events.py` with new page-granularity
verifier logic on top (the existing `verify_chain` walker is
from-genesis-only and is NOT reused), HTTP transport exposing
both destinations on separately authorized routes (`/audit`
under principal-derived tenant context, `/platform/audit`
under a new platform-operator claim extending D23), HTTP API
for ingestion management absorbed at P10 from the P6
carryover. P10 epic at
[charter/packages/p10-epic.md](packages/p10-epic.md). Three-
to-four-session forecast (S36 read port + adapter + chain
integrity; S37 HTTP transport + platform-operator claim; S38
ingestion management HTTP API + P10 close demo; S39 carryover
hygiene if needed).

**Corrective note on misrouted P10 framing inputs.** The S35
close paragraph below carries the line "P10 is the evaluation
territory per the roadmap" and names two P10 framing inputs
(retrieval-not-exercised model-behaviour gap; trace-id
propagation gap). The P10 strategic-mode framing conversation
on 2026-05-14 surfaced that this characterisation contradicts
the canonical roadmap and D92, which scope P10 as the audit
log viewer (backend-only). The two named framing inputs are
correctly routed to the queued retrieval-evaluation design
session pre-P11, not to P10. The corrective is captured
append-only per the existing discipline; the original S35
text stands as written below and this note attaches at P10
open.

**S36 closed** at 2026-05-14 with the audit context's read
side now in place end-to-end. Eight commits closed S36:
charter touch-points landing D102 (audit log read substrate
framing); four domain value-object modules at
`contexts/audit/domain/` (`audit_event_record.py`,
`query_filters.py`, `chain_integrity.py`, `destination.py`);
`AuditEventReader` Protocol port at the new
`contexts/audit/ports/reader.py` (operator-selected option A
at the pre-write reconciliation finding 1 user-question:
keep write-side `AuditPort` at `domain/ports.py`, place new
reader at `ports/reader.py`; intra-context asymmetry
recorded as carryover); cursor codec at
`contexts/audit/application/cursor.py` mirroring run_history;
`.importlinter` layers-audit contract extended with
`contexts.audit.ports`; `PostgresAuditEventReader` adapter at
`contexts/audit/adapters/outbound/postgres/reader.py`
implementing the port against both destinations through
destination-parameter routing per D102 alternative (b);
chain integrity verifier reuses `compute_event_hash` and
`GENESIS_HASH` primitives (the existing `verify_chain`
walker is from-genesis-only and is NOT reused per D102
alternative (h)); wiring at both composition roots
(`AuditEventReaderAdapter` as the tenth consumer-port-plus-
wiring-adapter class on `apps/cli/_cross_context.py`;
`build_audit_event_reader` factory at
`apps/api/_agent_runtime_wiring.py`); seven tenant-isolation
contract scenarios at
`tests/contract/tenant_isolation/test_audit_reader_isolation.py`;
live-stack smoke at `docs/smoke/p10_s36_audit_reader.md`
walks five scenarios + two routing-guard pairs end-to-end
against tenant_a's chain (20 audit rows) and a seeded
control-plane probe event. Net new tests at S36 close: 92
audit unit tests (was 50 pre-S36; +42 new), 7 contract
harness scenarios, 6 wiring tests = 55 net new test cases.
25/25 import-linter contracts kept; AST enforcement passes.
Two new findings landed in `briefs/p10/s36.md` Appendix D
at write time: finding 8 (Pydantic v2 versus frozen
dataclass — frozen dataclass picked for sibling-symmetry)
and finding 9 (single `timestamp_range` versus the brief's
`started_at_range`/`ended_at_range` shape — the audit
schema has one timestamp column).

**S37 closed** at 2026-05-14 with the audit HTTP transport
and the platform-operator principal type now in place
end-to-end. Eight commits closed S37: D103 + charter
touch-points (commit 1) with alternative (b) revised at
pre-write reconciliation finding 1 user-question resolution
to acknowledge the existing `Principal.roles` + `OPERATOR_ROLE`
as production code rather than hypothetical Phase 2 future,
framing `principal_type` as structurally complementary
(discriminator anchors `tenant_id` conditional validity at
decode time, which role-list cannot do cleanly because
`verify_credential` requires `tenant_id` unconditionally
today); D23 backend extension at `padhanam/security/auth.py`
plus dependency surface at `apps/api/middleware.py` and
`apps/api/routers/inference.py` (commit 2); Pydantic DTOs +
query parser at `apps/api/routers/_audit_dto.py` and
`_audit_query.py` mirroring run-history precedent per finding
2 (commit 3); audit error response extension at
`apps/api/_errors.py` with five new error-code paths and the
parallel `register_audit_error_handlers` per finding 4 plus
the refactor of commit-2 dependencies to raise typed
`PrincipalTypeMismatchError` (commit 4); HTTP routes at
`apps/api/routers/audit.py` with two FastAPI routers under
`/audit/*` and `/platform/audit/*` plus composition wiring at
`apps/api/main.py` including `PostgresAuditAdapter`'s new
public `control_plane_sessionmaker` property (commit 5); six
tenant-isolation contract scenarios at
`tests/contract/tenant_isolation/test_audit_http_isolation.py`
(commit 6) extending the harness from 27 to 33 scenarios;
live-stack smoke at `docs/smoke/p10_s37_audit_http.md` plus
script at `scripts/smoke_p10_s37.py` walking all ten
verification paths end-to-end against tenant_a's 23-row chain
and a seeded control-plane probe event, with four security
events captured in `logs/security.jsonl` (commit 7); this
entry (commit 8). 1251 passed + 17 skipped + 31 deselected
(live_llm) at S37 close — net +51 from S36's 1200. 25/25
import-linter contracts kept; AST enforcement passes.

**S38 next**: HTTP API for ingestion management at
`apps/api/routers/ingestion.py` plus the P10 close
end-to-end demonstration absorbing both the audit HTTP
transport and the ingestion management surface. P6
carryover scope (list sources, get source by id, get source
ingestion status) lands here per D102. S38 anchors directly
from the P10 epic note at `charter/packages/p10-epic.md`
unless structural drift surfaces.

## P9 closed (preserved below)

**S35b closed** at 2026-05-14 with harness integrity restored across all six pre-existing carryover failures. Five commits closed S35b: commit 1 transitioned `charter/current-package.md` and preserved the brief; commit 2 fixed TRUNCATE-without-CASCADE on chunks-to-`run_chunk_citations` (two fixture sites — `test_concurrent_workers.py`, `test_create_from_methodology_flow.py` — extended their TRUNCATE table-list to include `run_chunk_citations` per D95's FK chain; production ORM-deletion semantics with `ON DELETE SET NULL` are unaffected because TRUNCATE bypasses FK-action triggers); commit 3 migrated `test_ingestion_isolation.py`'s S22/D65 retrieval-surface block from the failing padhanam-api psql shell-out to the in-tenant-container psql pattern already used at `test_concurrent_workers.py` and `test_create_from_methodology_flow.py`, with each tenant seeded a distinct marker chunk (placeholder unit-vector embedding, sources.state='indexed') so the test asserts own-marker-present AND other-marker-absent — pass-because-isolated; commit 4 folded in the streaming-isolation test-scaffolding fix (added `_NullRunHistoryWriter` to `_build_app` to satisfy S31's `run_history_writer` field on `AgentRuntimeComposition`); commit 5 (this commit) appends the session log entry and transitions `current-package.md` back to "P9 closed; P10 framing next." Pre-write reconciliation fired its fourteenth instance at session-open: one structural-drift finding (surface 2: methodology fixture pattern doesn't transfer to per-tenant DBs because per-D5 they have no host-port bindings; operator-resolved via user-question to in-tenant-container psql) plus four mechanical absorptions, plus a mid-commit-3 structural finding (deliberate-violation cycle exposed that D32's per-DB topology is the *primary* isolation mechanism, with the SQL predicate as defense-in-depth — meaningful methodology signal for the Phase 1 close audit). 1106 passed + 17 skipped + 31 deselected at S35b close (+6 from S35a's 1100). Zero failures, no regressions. 25/25 import-linter contracts kept; AST enforcement passes. No new D-entries at S35b; D24 already commits the principle the fixes restore. The S35a + S35b carryover-hygiene tail folds into the P9 archive at P10 strategic-mode framing per operator direction.

**S35a closed** at 2026-05-14 with the four P9 carryover hygiene workstreams landed. Six commits: D99 (two-tier integration test strategy: file-level `pytestmark = pytest.mark.live_llm` plus `addopts = "-q -m 'not live_llm'"` plus `make test-live-llm` Makefile target; 10 integration test files / 31 tests at the live tier); D100 (CLI settings flow through composition root via new `apps/cli/_composition.py` mirroring `apps/api`'s `AppCompositions` pattern; five `ControlPlaneSettings()` construction sites refactored; all 17 methodology + tool CLI integration tests now pass); D101 (tenant registry actor provenance via control-plane Alembic `0011_tenant_actor_provenance` adding `created_by_user_id text NOT NULL` with server-default backfill, adapter signature change, seed-script subject migration to `migration:ops/seed_tenants`, four-site wipe-fixture guard); D27 join-key first end-to-end exercise (trace_id propagation from active OTel span to runs row; new `_current_otel_trace_id_hex()` helper; smoke at `docs/smoke/p9_s35a_trace_id_propagation.md` verified row 486af46b carries `trace_id=b7e677a03e28afd51c5f691055545022`). One structural reconciliation finding at session-open (surface 9: tenant_registry's missing column; operator chose option (a) add via migration); one reconciliation-at-execution-time correction (alembic_version varchar(32) limit forced revision-id rename from 40 chars to 28 chars). 1100 passed + 17 skipped + 31 deselected (live_llm) at S35a close. Six pre-existing carryover failures unchanged (four already-named; two newly-named TRUNCATE-without-CASCADE failures from chunks ↔ run_chunk_citations FK surfaced now that the demo runs populated chunks). P9 retrospective and archive stand from S35; P10 framing is the next strategic-mode conversation.

### Canonical P9 close framing (from S35)


P8 closed on 2026-05-13. Archive at [docs/archive/packages/p8.md](../docs/archive/packages/p8.md); measured outcomes appended to [log/packages.md](../log/packages.md). Seven sessions (S26a-1, S26a-2, S26b, S27b, S28b, S29b, S30b) shipped the agent runtime substrate per D86 (role-first model), D87 (override-mode space), D88 (agent runtime architecture), D89 (tool registry), and D90 (streaming runtime), plus D91 from the parallel brand-transplant strategic block. P8's contribution is the agent runtime substrate that makes the platform demonstrable in product form: roles as first-class primary aggregates composing into methodologies via `role_refs`; a streaming runtime exposing eleven domain-layer events through transport-neutral ports; an SSE transport at `apps/api/routers/agent.py` consumed end-to-end by the `padhanam agent run` CLI at S30b; production wiring of the runtime composition at `apps/api/_agent_runtime_wiring.py` including a per-tenant retrieval router. Two end-to-end demonstrations close P8 in product form: Flowstate-McKinsey ProblemFramer on tenant alpha producing a SMART problem statement (narrow artifact, 76s); Forgepath-LVT LVTGuide on tenant beta producing a full Lean Value Tree (broad artifact, 271s). Same substrate, two artifact scales — the bet's intelligence-layer commitment per D82 exercised in product form. Pattern reinforcements that solidified Phase 1 architectural norms during P8: the consumer-port-plus-wiring-adapter pattern reached four reinforcements across five sessions in a row with three-altitude generality (cross-context, intra-context wiring, transport) and a fourth observation (same-altitude cross-composition-root re-use at S30b); pre-write reconciliation as architectural discovery reached six-plus reinforcements with the new sub-observation that pre-session operator setup is itself a pre-write reconciliation moment. Both promotion candidates for the Phase 1 close audit window.

**Phase 1 / Phase 2 boundary committed.** D92 confirms Phase 1 scope at P1 through P12 with P9-P12 reframed as backend-only substrate. D93 commits Phase 2 direction to methodology-as-product positioning with focus purely on UX/UI. The Phase 1 close audit lands at P12 close per `charter/methodology.md`'s audit posture; mid-phase audit work that would have captured methodology promotions and PRFAQ revoice defers to that audit. The new carryover entries below name the substrate-readiness items Phase 1 absorbs so Phase 2 UX work runs cleanly.

**P9 framed.** D94 commits the run-history substrate as Shape C: per-tenant Postgres `runs` table plus `run_chunk_citations` and `run_entity_citations` with rendering-grade snapshot columns alongside the technical references, single-transaction write at invocation completion, new bounded context at `contexts/run_history/` separate from `contexts/agent/`, single consumer-defined query port shaped to Phase 2 UX consumption at P9 with P11's aggregation-shaped port deferred to P11 framing. P9 epic at [charter/packages/p9-epic.md](packages/p9-epic.md). Four-to-five session forecast (S31 substrate-and-write-path, S32 citation-linking-and-completion-seam, S33 UX-query-port, S34 HTTP-ingestion-API-carryover, S35 P9 close if needed); session boundaries settle session-by-session per the established discipline. **S31 closed** at 2026-05-13 with the bounded-context substrate now in place: `contexts/run_history/` with the hexagonal-layer convention, three per-tenant tables (`runs`, `run_chunk_citations`, `run_entity_citations`) via Alembic revision `0011_create_run_history`, `RunHistoryWriter` consumer port at the agent context, `record_run` use case and `PostgresRunHistoryAdapter`, `RunHistoryWriterAdapter` wiring at both `apps/cli/` and `apps/api/` composition roots, `invoke_agent` extended with the run-record accumulator and post-terminal-yield write seam (D95 shape B), tenant-isolation contract harness extended with nine new scenarios. Live-stack smoke verified one runs row on `tenant_a` with audit hashes byte-for-byte matching the audit chain. Citation tables exist but no citation rows get written; citation linking with snapshot population and the single-transaction completion seam lands at **S32 next**. The two p9-epic open questions named at S31 charter update (citation snapshot semantics — chunk excerpt verbatim versus summary; whether `run_entity_citations` snapshots `source_chunk_ids` alongside the display label) carry forward to S32 framing. Reconciliation-time observations queued for the operator at session close: an automated rebuild-and-recreate target (the brief's missing `make build-api`) would absorb the manual `docker build` + `compose.yaml` digest pin + `force-recreate` cycle; the `.importlinter` location at the repo root (not a `[tool.importlinter]` block in `pyproject.toml`) is a brief-shape correction worth noting for future strategic-mode authoring.

**S32 closed** at 2026-05-13 with the citation surface now in place end-to-end from retrieval through to per-tenant Postgres rows. Eleven commits closed S32: charter updates landing D96 (`charter/decisions.md`, `charter/schema.md`, `charter/packages/p9-epic.md`, `charter/current-package.md`, brief preserved at `briefs/p9/s32.md` with Appendix D capturing pre-write reconciliation outcomes); citation candidate value objects at `contexts/agent/domain/citation_candidates.py` with discriminated union; `ToolCallCompleted` extension carrying `citation_candidates: tuple[CitationCandidate, ...] = ()`; `AgentRetrievalClient` port growing a `RetrievalResult` envelope so the wiring adapter produces both LLM-facing `RetrievedChunk` projections and citation candidates single-pass; ingestion-side `ChunkResult` extended with `chunk_index` and `source_snapshot` plus the pgvector SQL projecting the additional columns; `AgentLoopExecutor` populates `citation_candidates` on `ToolCallCompleted` events; `invoke_agent` accumulates with within-run deduplication first-seen-wins per `(chunk_id, run_id)` and `(entity_tenant_id, entity_name, entity_type, run_id)`; Alembic 0012_revise_citation_snapshots drops `source_citation text` for `source_snapshot jsonb` and drops `entity_display_label text` for `source_chunk_ids text[]` (applied directly to both tenants since the tenant-registry-driven `make migrate` path was non-operational due to a wiped registry); run-history-context `ChunkCitationRecord` and `EntityCitationRecord` mirror the agent candidates one-for-one per D54; `PostgresRunHistoryAdapter` writes all three tables within `async with session.begin()` with partial-failure rollback; tenant-isolation contract harness extended to 13 scenarios. Live-stack smoke verified one runs row + two chunk citation rows + one entity citation row on `tenant_a` with `source_snapshot` JSONB populated (Phase 1 keys `file_name`, `file_type`) and `source_chunk_ids` text[] carrying provenance. Pre-existing failures carried over from S30b/S31: methodology/tool CLI command tests (config shape drift); ingestion e2e tests (the same tenant-registry-wipe class). The HTTP API for ingestion management absorbed from the P6 deferred carryover is **S34 next** (or earlier if folded).

**S33 closed** at 2026-05-14 with the UX-shaped read surface now in place end-to-end. Seven commits closed S33: D97 at `charter/decisions.md` (RunHistoryReader port at run-history producer context; RunRecord-as-aggregate read DTO; four-filter RunListFilters vocabulary; cursor pagination on `(started_at, id)` with base64-of-JSON opaque cursor) plus charter touch-points; `RunHistoryReader` Protocol port at `contexts/run_history/ports/reader.py` with `get_run` returning `RunRecord | None` and `list_runs_with_filters` returning `RunListPage`; `RunListFilters` / `RunListCursor` / `MalformedCursorError` value objects at `contexts/run_history/domain/query_filters.py`; cursor codec at `contexts/run_history/application/cursor.py`; `PostgresRunHistoryReader` at `contexts/run_history/adapters/outbound/postgres/reader.py` implementing the port via three queries (avoids LEFT-JOIN cartesian product); `RunHistoryReaderAdapter` wiring at `apps/cli/_cross_context.py` (ninth wiring class on that file) and `build_run_history_reader` factory at `apps/api/_agent_runtime_wiring.py`; tenant-isolation contract harness extended to 16 scenarios; live-stack smoke against tenant_a exercises all four read scenarios end-to-end (get_run with citations populated, list with no filters, termination_reasons filter, cursor pagination across two pages). 831 unit tests pass at session close (+57 from S32's 774); 25/25 import-linter contracts kept. One real-Postgres finding surfaced at smoke time (tuple comparison `uuid < varchar` operator-resolution failure) and was fixed in the smoke commit with `sa.cast(..., pg.UUID)`; the class of finding is structurally invisible to the unit tests' fake session and worth recording for the live-stack-as-required-complement methodology promotion candidate. The read-DTO-symmetry call (RunRecord-as-aggregate rather than the brief's drafted `RunWithCitations` wrapper) was the session-open structural-honesty finding the user-question resolved.

**S34 next**: build evidence at S33 points more strongly toward S34 pivoting to HTTP routes surfacing the run-history reader than staying on the ingestion-management track. Three reasons: the reader substrate is now complete and one more session closes the end-to-end Phase 2 UX consumer story; the cursor codec is the substrate the HTTP layer's request/response boundary needs; the four-filter vocabulary is the natural input to a query-string parser. The ingestion-management API carryover from P6 can land at S35 or P9 close without prejudice; the strategic-mode conversation at S34 framing settles the call against operator priority.

**S34 in flight.** D98 commits the four HTTP shapes: response DTO as 1:1 mirror of `RunRecord` per the storage-versus-render discipline from D96; query parameter vocabulary mapping the four `RunListFilters` fields plus cursor and page_size; error response body shape with the eleven-path map and the cursor-and-filter-mismatch policy honouring both independently; principal-derived tenant context per S29b precedent at `apps/api/routers/agent.py`. S34 closes the end-to-end Phase 2 UX consumer story for the entire P9 substrate: the reader port from S33 is now callable from any web frontend, the cursor codec is exercised at its intended HTTP boundary, the four-filter vocabulary surfaces as a usable query-string parser. The strategic-mode S34 framing conversation settled the pivot from the ingestion-management API carryover to the run-history HTTP routes on Kano-must-have-for-Phase-2-UX grounds; ingestion-management lands at S35 or P9 close without prejudice.

**S34 closed** at 2026-05-14 with the run-history HTTP read surface now in place end-to-end. Eight commits closed S34: D98 plus charter touch-points; four Pydantic response DTOs mirroring the domain records 1:1; query-string parser mapping six query params to `RunListFilters` and `RunListCursor` via a sentinel-cursor mechanism on the initial page; two FastAPI routes (`GET /runs/{run_id}` returning the run-with-citations aggregate; `GET /runs` returning the paginated, filtered list); error response body shape at `apps/api/_errors.py` with eleven verification paths covered (`malformed_cursor`, `invalid_filter_range`, `run_not_found`, `validation_error`, `internal_error`) plus `CorrelationIdMiddleware`; tenant-isolation contract harness extended to 20 scenarios with four HTTP-layer scenarios; live-stack smoke against tenant_a verified all eleven verification paths plus two happy paths end-to-end including the `X-Correlation-Id` header round-trip. One pre-write reconciliation finding required a session-open user-question: brief scenario 20 ("tenant-not-in-registry returns 401") contradicted the existing `get_tenant_context` dependency's 404 behaviour; resolved to 404 per consistency-with-precedent, recorded in D98 alternative (k) and Appendix D of the preserved brief.

**S35 closed** at 2026-05-14 with P9 closed via end-to-end demonstration against tenant_a. Five commits closed S35: charter updates ahead of code carrying two new deferred-decisions entries (integration-test slowness from real-LLM inference; HTTP API for ingestion management absorbed from P6 and not landed within P9) plus the investigation note `docs/notes/integration-test-slowness-investigation.md`; carryover fix for `test_agent_sse_endpoint.py` `_runtime_with_script` helper missing the `run_history_writer` field at `AgentRuntimeComposition`; end-to-end demonstration trigger against tenant_a producing run id `5226925f-bd76-47c2-8c9b-fdb4b370e3ab` with audit-chain hashes linked byte-for-byte between the runs row and `tenant_audit`, recorded at `docs/smoke/p9_s35_e2e_demo.md`; P9 retrospective addendum to `charter/packages/p9-epic.md` and P9 entry at `log/packages.md` per the P8 precedent (5/5 clean-close, 0/5 CFR, +128 net new tests pushing total to 883), plus archive of the epic to `docs/archive/packages/p9.md`; session-log entry and this final transition. Five pre-write reconciliation surfaces absorbed mechanically at session-open; one mid-session structural finding surfaced at demo trigger time (methodology-lineage-pointing-to-wiped-row sub-class of the S30b fixture-wipe; resolved by authoring a fresh agent via `create-from-role`). Two Phase 1 substrate-completeness limitations recorded for the Phase 1 close audit at P12: retrieval-not-exercised model-behaviour gap (already a P8→P9 carryover); trace-id propagation gap from agent runtime to runs row (the `trace_id` column is NULL despite Langfuse-web healthy; structural finding; substrate complete at column + read-port level, capture path needs revisit). No new D-entries at S35; all P9 substrate decisions landed at D94 through D98.

P9 delivered the run-history backend substrate as the Phase 2 UX consumer surface plus the end-to-end demonstration as the bet-proof artefact for Phase 1 substrate-completeness per D92. Every consumer surface Phase 2 UX needs for run-history is in place and verifiable end-to-end through a single trigger command: write path (S31), citation surface (S32), consumer-defined read port (S33), HTTP transport (S34), demonstrated execution (S35). P10 is the evaluation territory per the roadmap; the strategic-mode P10 framing conversation follows P9 close. Two P10 framing inputs surfaced from P9 execution worth weighing at the strategic conversation: the retrieval-not-exercised gap is more impactful at P10 than P9 because the evaluation harness needs reliable tool invocation as its foundation; the trace-id propagation gap impacts P10's evaluation harness more than P9's run history because cross-store correlation with Langfuse is part of how the harness will deep-dive into per-run cost and latency. Both are inputs for the P10 conversation; the strategic conversation owns P10 scope decisions.

## Carryovers active across the P8→P9 boundary

- **Audit context port-location asymmetry.** Write-side
  `AuditPort` sits at `contexts/audit/domain/ports.py` (pre-
  P9 convention). Read-side `AuditEventReader` sits at
  `contexts/audit/ports/reader.py` (P9-era convention
  established at run_history). Activation trigger: the next
  port added to the audit context (likely at P10 S37 HTTP
  work or P11 recommendation-engine consumers). At that
  point, decide whether to symmetrize by moving `AuditPort`
  to `contexts/audit/ports/writer.py` versus accepting the
  intra-context asymmetry as the audit-context convention.
  Recorded at S36 pre-write reconciliation; deferred on
  scope-discipline grounds because Option B (move now) has
  unbounded touch surface and adds incidental scope at
  S36 build time.
- **Per-invocation retrieval-constraint threading at ToolInvoker.** The Phase 1 `ToolInvokerAdapter` constructor accepts retrieval constants at composition time; per-role retrieval constraints from the effective bundle do not thread through to the tool invoker on each invocation. Phase 2 substrate refinement queued at the `apps/api/_agent_runtime_wiring.py` module docstring.
- **Cross-app adapter location cleanup.** S30b's production wiring imports adapter classes from `apps/cli/_cross_context.py` because both `apps/cli/` and `apps/api/` need them. Phase 2 cleanup relocates to a shared `apps/`-level module; Phase 1 cross-app import is the pragmatic call documented in the wiring module's docstring.
- **`psql` missing in padhanam-api image.** Two tests at `tests/contract/tenant_isolation/test_ingestion_isolation.py` shell out to `psql` to truncate chunks + sources; the image does not include `psql`. Tests pass only when tenant DBs happen to be empty; S30b's demo runs surfaced the latent issue. Pre-existing failure; P9 candidate.
- **TRUNCATE-without-CASCADE on chunks blocked by `run_chunk_citations` FK.** Two tests (`tests/integration/contexts/ingestion/test_concurrent_workers.py::test_two_concurrent_workers_no_double_processing_full_pipeline`, `tests/e2e/agent/test_create_from_methodology_flow.py::test_full_role_aware_clone_and_edit_flow_against_live_stack`) shell out to `psql -c "TRUNCATE TABLE chunks, sources;"`. The TRUNCATE fails with `cannot truncate a table referenced in a foreign key constraint` because S32 introduced `run_chunk_citations.chunk_id REFERENCES chunks(id)`. Latent at S35 close when tenant_a's chunks were empty; load-bearing at S35a close because the trace_id-propagation live demo populated chunks via the retrieval tool call path. Fix shape: TRUNCATE CASCADE or include `run_chunk_citations` in the truncate set; not on S35a's path.
- **Tenant registry fixture leak.** During S30b's demo work, the tenant registry got wiped between the recovery seed and the demo runs by some contract-test fixture path not yet identified. Same shape as the methodology fixture leak S30b fixed; same fix shape (`created_by_user_id NOT LIKE 'migration:%'` filter or equivalent guard). Activation trigger is the next pre-session smoke run that surfaces an empty registry.
- **Hierarchical multi-agent topology design.** Closed at strategic-mode commit 6f66f71 (D80 through D85). Role-first refinement (D86) closed at this commit.
- **Layer A policy authoring.** Follow-on strategic block authoring
  the ten policy scaffolds at `charter/compliance/` per the
  compliance-as-shared-responsibility principle. Scheduled at
  operator discretion between P7 build sessions or after P7 close;
  does not block any P7 build session because the substrate (D-entries
  D69-D73, the principle, the scaffold structure) is in place. Authoring
  effort estimated at one strategic block session.
- **Product methodology selection-space.** P7 commits to LVT as
  the first methodology per D68; the LVT methodology template
  lands at S25. Other methodologies in
  [charter/product-methodology.md](product-methodology.md)
  activate as evidence pulls them in (operator authors as needed);
  per-domain methodology selection surfaces at the framing of each
  domain-bearing package.
- **Production CLI tenant resolution via the registry.** Phase 2
  shape; `apps/cli/_runtime.py`'s hardcoded test-set mapping is
  honest about its dev-only scope. Activates when production
  deployment context arrives.
- **Multi-baseline regression reports.** Deferred per D58;
  single-baseline at S18. Activates at P11's recommendation
  engine when run-history infrastructure exists from P9.
- **PRFAQ phase-audit refresh.** Cadence per D45 (every phase audit). The v2 PRFAQ from the P4-post carryover-cleanup strategic session stands until the Phase 1 close audit at P12 close. The Phase 1 close audit refresh absorbs the dogfooding scenario acknowledgment per D77 and D78 (operator runs a private deployment for personal use as evidence of D14's customer-deployment scenario), and supersedes D51's voice-and-audience choice per D93 (PRFAQ v3 voice realigns to methodology-as-product audience: senior product leaders, CPOs, consultancies per `bet.md` line 57).
- **Personal-use deployment of public Padhanam (Phase C).**
  Operator-controlled deployment of public Padhanam as a real
  instance of the customer-deployment scenario per D78, exercising
  D14's configuration + tools + bounded-extensions model. Phase C
  activates concretely after P8 close (when agent runtime exists);
  preparatory work (operator-authored tool services and methodology
  template authoring) can start after P7 close in parallel with P8
  build, subject to operator capacity per the all-or-nothing
  posture. PRFAQ acknowledgment lands at the next phase audit.
- **Calendar tool service as platform capability.** Deferred-
  decisions entry per the P7 mid-package strategic block on
  consumer-direction placement; activation when public Padhanam
  needs a calendar integration for any package work or when the
  personal-use deployment Phase C activates per D78, whichever
  comes first.
- **Email tool service as platform capability.** Deferred-decisions
  entry, same activation shape as the calendar tool entry.
- **Scheduled-runs primitive.** Deferred-decisions entry; activates
  when public Padhanam needs scheduled agent execution (likely P11
  or P12 territory) or when personal-use deployment Phase C needs
  daily-review-style triggers, whichever comes first. Two
  implementation candidates (platform primitive versus external
  trigger); choice settles when implementation begins.
- **HTTP API for ingestion management.** Was deferred per the P6 out-of-scope to "when a UI consumer arrives at P9 or P10." Under D93 the UI consumer is Phase 2 consumer UX. The API surface lands at P9 or earlier as Phase 1 substrate completion so Phase 2 UX consumes it directly.
- **HTTP API for evaluation management.** Same shape; was deferred until a UI consumer arrives at P10 or P11; under D93 lands as Phase 1 substrate completion at P10 or P11.
- **Browser-based authentication.** Cookies, CSRF, session management. D23's signed-token backend is operator-only; consumer UX needs proper session handling. Lands as Phase 1 close substrate-completion session.
- **Frontend stack decision.** React 19 / Vite 6 / React Router 7 are pinned at D10 as pre-S1 baseline; Phase 2 open confirms or revisits, plus chooses a UI library or commits to an in-house design system grounded in `charter/brand-guidelines.md` and `charter/brand/tokens.css`. Could land at Phase 1 close or at Phase 2 open; cheap either way.

## Deferred items remaining visible

- **Per-tenant Neo4j topology.** Activated at S21 per D63 with
  Phase 1 shared-instance + property-based scoping; the
  deferred-decisions entry remains as the production-deployment
  revisit marker with three named triggers (residency, blast
  radius, security-review).
- **Within-tenant segmentation primitive.** Held in the P6-open
  strategic-block conversation; activates at the consumer-driven
  session that demands it (likely P8 agent runtime). No schema
  commitment at P6 beyond tenant.
- **Classification field on TenantContext.** Deferred per S15
  framing decision option C; lands at the package that genuinely
  consumes it (P7 or P8 per the P4 epic note's out-of-scope
  section). TenantContext at P6 close still carries three fields,
  not four; adding the field later is a one-line edit on the
  value object plus a registry-row column.
- **Cost-ceiling forward-affordance columns.** Configuration
  columns landed at S14 alongside the cost-attribution column per
  D41. Reading and enforcing the columns defers to Phase 2 per
  [charter/deferred-decisions.md](deferred-decisions.md).
- **Pricing-table monthly review.** Cadence in
  `ops/scheduled_checks.yaml` per D41; first run scheduled
  2026-06-05.
- **Pricing-table format evolution.** S14 reflection forward-note;
  the format-(b) Pydantic + dict shape evolves to YAML/TOML under
  `ops/` when multi-region rates, time-zoned rates, or rate-card
  complexity arrives. Phase 2 framing.
- **PRFAQ operator-voice rewrite.** Follow-on strategic
  conversation, queued at operator discretion.
- **Phase 1 PRD operator-review** of the problem-statement and
  target-user sections. Operator discretion.
- **Production-shaped tenant onboarding workflow** (full D13
  implementation): awaits production deployment context.
- **Cross-replica cache invalidation for the routing layer**
  (D36): single-replica dev makes this a non-issue.
- **Hash chain caching as a performance optimisation** (D37):
  deferred until measurement justifies.
- **Methodology mechanical-enforcement upgrades.** Tracked in
  [charter/deferred-decisions.md](deferred-decisions.md). The
  framing-prompt-as-recommendation and pre-write reconciliation
  promotions at this commit move two items off the
  Patterns-observed candidate list onto the prescriptive
  principle surface; the user-driven course-correction Patterns-
  observed entry lands at the same commit.
- **Platform-baseline scoring sheet library** (deferred per D53;
  activates at real onboarding flow or a cross-tenant curated
  library with a real consumer).
- **Human-review UI for evaluation** (deferred per D53; lands at
  P10 or P11 territory).
- **Multi-currency cost reporting** (deferred per the strategic
  commit `24561c9` deferred-decisions entry; activates at the
  Phase 2 multi-region deployment context).
- **Per-criterion cost breakdowns in
  `CostPerSuccessfulTaskResult`** (P11 territory).
- **Calibration learning loops over `automated_score` vs
  `human_score`** (P11 territory; data substrate lives at
  rubric_applications per D55).
- **Trace_id-based recommendation queries beyond
  cost-per-successful-task** (P11 territory).
- **HTTP API for ingestion management** (deferred per the P6
  out-of-scope; CLI is the user surface at P6; HTTP API ships
  when a UI consumer arrives at P9 or P10).
- **HTTP API for evaluation management** (deferred; activates
  when a UI consumer arrives at P10 or P11).
- **Sheet/interaction-set management commands in the CLI**
  (deferred; activates when CRUD UI is needed).
- **Personalization as a runtime concern.** Deferred-decisions
  entry from P6 mid-package absorption (Ask David external
  reference); activates at P8 agent runtime or whichever
  predecessor orchestration session demands it.
