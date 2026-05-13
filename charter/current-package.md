# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P9 active — S31 closed; S32 next

P8 closed on 2026-05-13. Archive at [docs/archive/packages/p8.md](../docs/archive/packages/p8.md); measured outcomes appended to [log/packages.md](../log/packages.md). Seven sessions (S26a-1, S26a-2, S26b, S27b, S28b, S29b, S30b) shipped the agent runtime substrate per D86 (role-first model), D87 (override-mode space), D88 (agent runtime architecture), D89 (tool registry), and D90 (streaming runtime), plus D91 from the parallel brand-transplant strategic block. P8's contribution is the agent runtime substrate that makes the platform demonstrable in product form: roles as first-class primary aggregates composing into methodologies via `role_refs`; a streaming runtime exposing eleven domain-layer events through transport-neutral ports; an SSE transport at `apps/api/routers/agent.py` consumed end-to-end by the `padhanam agent run` CLI at S30b; production wiring of the runtime composition at `apps/api/_agent_runtime_wiring.py` including a per-tenant retrieval router. Two end-to-end demonstrations close P8 in product form: Flowstate-McKinsey ProblemFramer on tenant alpha producing a SMART problem statement (narrow artifact, 76s); Forgepath-LVT LVTGuide on tenant beta producing a full Lean Value Tree (broad artifact, 271s). Same substrate, two artifact scales — the bet's intelligence-layer commitment per D82 exercised in product form. Pattern reinforcements that solidified Phase 1 architectural norms during P8: the consumer-port-plus-wiring-adapter pattern reached four reinforcements across five sessions in a row with three-altitude generality (cross-context, intra-context wiring, transport) and a fourth observation (same-altitude cross-composition-root re-use at S30b); pre-write reconciliation as architectural discovery reached six-plus reinforcements with the new sub-observation that pre-session operator setup is itself a pre-write reconciliation moment. Both promotion candidates for the Phase 1 close audit window.

**Phase 1 / Phase 2 boundary committed.** D92 confirms Phase 1 scope at P1 through P12 with P9-P12 reframed as backend-only substrate. D93 commits Phase 2 direction to methodology-as-product positioning with focus purely on UX/UI. The Phase 1 close audit lands at P12 close per `charter/methodology.md`'s audit posture; mid-phase audit work that would have captured methodology promotions and PRFAQ revoice defers to that audit. The new carryover entries below name the substrate-readiness items Phase 1 absorbs so Phase 2 UX work runs cleanly.

**P9 framed.** D94 commits the run-history substrate as Shape C: per-tenant Postgres `runs` table plus `run_chunk_citations` and `run_entity_citations` with rendering-grade snapshot columns alongside the technical references, single-transaction write at invocation completion, new bounded context at `contexts/run_history/` separate from `contexts/agent/`, single consumer-defined query port shaped to Phase 2 UX consumption at P9 with P11's aggregation-shaped port deferred to P11 framing. P9 epic at [charter/packages/p9-epic.md](packages/p9-epic.md). Four-to-five session forecast (S31 substrate-and-write-path, S32 citation-linking-and-completion-seam, S33 UX-query-port, S34 HTTP-ingestion-API-carryover, S35 P9 close if needed); session boundaries settle session-by-session per the established discipline. **S31 closed** at 2026-05-13 with the bounded-context substrate now in place: `contexts/run_history/` with the hexagonal-layer convention, three per-tenant tables (`runs`, `run_chunk_citations`, `run_entity_citations`) via Alembic revision `0011_create_run_history`, `RunHistoryWriter` consumer port at the agent context, `record_run` use case and `PostgresRunHistoryAdapter`, `RunHistoryWriterAdapter` wiring at both `apps/cli/` and `apps/api/` composition roots, `invoke_agent` extended with the run-record accumulator and post-terminal-yield write seam (D95 shape B), tenant-isolation contract harness extended with nine new scenarios. Live-stack smoke verified one runs row on `tenant_a` with audit hashes byte-for-byte matching the audit chain. Citation tables exist but no citation rows get written; citation linking with snapshot population and the single-transaction completion seam lands at **S32 next**. The two p9-epic open questions named at S31 charter update (citation snapshot semantics — chunk excerpt verbatim versus summary; whether `run_entity_citations` snapshots `source_chunk_ids` alongside the display label) carry forward to S32 framing. Reconciliation-time observations queued for the operator at session close: an automated rebuild-and-recreate target (the brief's missing `make build-api`) would absorb the manual `docker build` + `compose.yaml` digest pin + `force-recreate` cycle; the `.importlinter` location at the repo root (not a `[tool.importlinter]` block in `pyproject.toml`) is a brief-shape correction worth noting for future strategic-mode authoring.

## Carryovers active across the P8→P9 boundary

- **Retrieval-aware role allowlists.** P8's two demos showed the substrate end-to-end but without retrieval grounding because all migration-seeded roles ship with empty `tool_allowlist`. Per-invocation allowlist override OR role-allowlist tightening (adding the retrieval tool reference) at Phase 2 makes source-grounded artifacts the default. Activates at the first authoring evidence demanding it.
- **Per-invocation retrieval-constraint threading at ToolInvoker.** The Phase 1 `ToolInvokerAdapter` constructor accepts retrieval constants at composition time; per-role retrieval constraints from the effective bundle do not thread through to the tool invoker on each invocation. Phase 2 substrate refinement queued at the `apps/api/_agent_runtime_wiring.py` module docstring.
- **Cross-app adapter location cleanup.** S30b's production wiring imports adapter classes from `apps/cli/_cross_context.py` because both `apps/cli/` and `apps/api/` need them. Phase 2 cleanup relocates to a shared `apps/`-level module; Phase 1 cross-app import is the pragmatic call documented in the wiring module's docstring.
- **`psql` missing in padhanam-api image.** Two tests at `tests/contract/tenant_isolation/test_ingestion_isolation.py` shell out to `psql` to truncate chunks + sources; the image does not include `psql`. Tests pass only when tenant DBs happen to be empty; S30b's demo runs surfaced the latent issue. Pre-existing failure; P9 candidate.
- **Tenant registry fixture leak.** During S30b's demo work, the tenant registry got wiped between the recovery seed and the demo runs by some contract-test fixture path not yet identified. Same shape as the methodology fixture leak S30b fixed; same fix shape (`created_by_user_id NOT LIKE 'migration:%'` filter or equivalent guard). Activation trigger is the next pre-session smoke run that surfaces an empty registry.
- **Hierarchical multi-agent topology design.** Closed at strategic-mode commit 6f66f71 (D80 through D85). Role-first refinement (D86) closed at this commit.
- **Layer A policy authoring.** Follow-on strategic block authoring
  the ten policy scaffolds at `charter/compliance/` per the
  compliance-as-shared-responsibility principle. Scheduled at
  operator discretion between P7 build sessions or after P7 close;
  does not block any P7 build session because the substrate (D-entries
  D69-D73, the principle, the scaffold structure) is in place. Authoring
  effort estimated at one strategic block session.
- **Retrieval-evaluation design session.** Queued strategic-mode
  conversation ahead of P11 (recommendation engine). The audience
  is the existing eval harness from P5 and the optimisation layer
  at P11; the design space (gold-set construction, offline versus
  online relevance signals, recall@k versus precision@k tradeoffs,
  test corpus shape) warrants its own focused session at the
  audience-relevant moment. Must-have for the bet's optimisation
  claim because the optimisation layer has to distinguish retrieval
  failures from reasoning failures; deferred at the data-retrieval
  design session on Kano-versus-RICE asymmetry grounds (must-have
  on Kano, high effort on RICE relative to its on-runtime impact).
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
