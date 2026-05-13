# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P9 active — opening

P8 closed on 2026-05-13. Archive at [docs/archive/packages/p8.md](../docs/archive/packages/p8.md); measured outcomes appended to [log/packages.md](../log/packages.md). Seven sessions (S26a-1, S26a-2, S26b, S27b, S28b, S29b, S30b) shipped the agent runtime substrate per D86 (role-first model), D87 (override-mode space), D88 (agent runtime architecture), D89 (tool registry), and D90 (streaming runtime), plus D91 from the parallel brand-transplant strategic block. P8's contribution is the agent runtime substrate that makes the platform demonstrable in product form: roles as first-class primary aggregates composing into methodologies via `role_refs`; a streaming runtime exposing eleven domain-layer events through transport-neutral ports; an SSE transport at `apps/api/routers/agent.py` consumed end-to-end by the `padhanam agent run` CLI at S30b; production wiring of the runtime composition at `apps/api/_agent_runtime_wiring.py` including a per-tenant retrieval router. Two end-to-end demonstrations close P8 in product form: Flowstate-McKinsey ProblemFramer on tenant alpha producing a SMART problem statement (narrow artifact, 76s); Forgepath-LVT LVTGuide on tenant beta producing a full Lean Value Tree (broad artifact, 271s). Same substrate, two artifact scales — the bet's intelligence-layer commitment per D82 exercised in product form. Pattern reinforcements that solidified Phase 1 architectural norms during P8: the consumer-port-plus-wiring-adapter pattern reached four reinforcements across five sessions in a row with three-altitude generality (cross-context, intra-context wiring, transport) and a fourth observation (same-altitude cross-composition-root re-use at S30b); pre-write reconciliation as architectural discovery reached six-plus reinforcements with the new sub-observation that pre-session operator setup is itself a pre-write reconciliation moment. Both promotion candidates for the Phase 1 close audit window.

**P9 next.** Run history and replay infrastructure per [charter/packages.md](packages.md): a replay UI surface with citation linking back to source chunks and graph entities. P9 inherits from P8's substrate: the S29b nested OTel span hierarchy plus the eleven-event vocabulary plus the per-tenant audit chain together provide the substrate P9 builds the run-history surface against. P11's recommendation engine (further out in Phase 1) inherits from P9's run-history infrastructure. Framing strategic block opens at operator discretion.

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
- **PRFAQ phase-audit refresh.** Cadence per D45 (every phase
  audit). The v2 PRFAQ from the P4-post carryover-cleanup
  strategic session stands until the Phase 1 close audit. The
  Phase 1 close audit refresh additionally absorbs the dogfooding
  scenario acknowledgment per D77 and D78 (operator runs a private
  deployment for personal use as evidence of D14's customer-
  deployment scenario).
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
