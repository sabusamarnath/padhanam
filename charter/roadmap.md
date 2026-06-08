# Roadmap

The living strategic-tree artefact, adopted in D44. Bet at the root, initiatives below (phases), epics below that (packages), stories below that (sessions). Versioned with reasoning attached to every change. Reviewed at every phase audit.

Reasoning category taxonomy for course changes:

- **Discovery** — work surfaced something that changes scope.
- **Capacity** — operator's available time changes the throughput calculation.
- **Signal** — data from earlier work changes the priority order.
- **Hedge** — uncertainty about a future event makes optionality worth more than commitment.

The distribution of reasoning categories at phase audits is itself signal per D44. Too many capacity-driven changes mean the bet was overscoped; too many signal-driven changes mean the bet was poorly grounded; too many hedge entries mean the operator is avoiding commitment.

---

## Bet

A public demonstration that a senior product leader can direct the end-to-end implementation of an enterprise-grade agentic platform through AI-assisted development without writing code, with the architectural discipline holding at the level of complexity that real enterprise software requires. The platform is the artefact; the methodology that emerges is the proprietary insight. See [bet.md](bet.md) for the strategic articulation; [prfaq.md](prfaq.md) for the external articulation.

## Initiative 1: Phase 1 (in progress)

By Phase 1 close: a single tenant runs locally with the full stack; one agent can be configured, run, audited, and optimised through the platform's own tooling; the trace capture layer surfaces optimization recommendations, not just data; the methodology document captures the architect-implementer pattern with enough specificity that another senior product leader could read it and adopt the discipline. Phase 2 direction decided at the Phase 1 close audit. See [phase-1-prd.md](phase-1-prd.md) for the living phase-level PRD.

### Packages, with RICE scoring

Scoring criteria fitted to the case-study framing:

- **Reach (1–5)**: how many of the bet's evidence-needs (enterprise architectural decisions, identity federation, tenant isolation, observability differentiator, evaluation, optimization recommendations) does this package exercise.
- **Impact (1–5)**: how strongly does this package demonstrate the proposition that a senior product leader can direct enterprise-grade implementation.
- **Confidence (1–3)**: forecast confidence at the time the package was framed.
- **Effort (operator-weeks)**: estimated calendar weeks of operator time.

RICE = (R × I × C) / E. Scores are operator-judged, recorded at this strategic session as the canonical baseline; P1, P2, and P3 scores are applied retroactively. Phase 1 close audit reviews scores against actual delivery and against signal that would have changed them.

| Package | Title | R | I | C | E | RICE |
|---|---|---|---|---|---|---|
| P1 | Scaffold | 1 | 1 | 3 | 0.6 | 5.0 |
| P2 | First LLM call | 2 | 1 | 3 | 1.6 | 3.75 |
| P3 | Tenancy primitives | 4 | 4 | 2 | 2.0 | 16.0 |
| P4 | LLM gateway | 5 | 5 | 3 | 0.8 | 93.75 |
| P5 | Evaluation harness | 5 | 5 | 2 | 1.4 | 35.7 |
| P6 | Source ingestion | 4 | 3 | 2 | 1.6 | 15.0 |
| P7 | Agent CRUD | 4 | 4 | 3 | 1.0 | 48.0 |
| P8 | Agent runtime | 5 | 5 | 2 | 1.6 | 31.25 |
| P9 | Run history | 3 | 4 | 2 | 1.0 | 24.0 |
| P10 | Audit log viewer | 2 | 2 | 3 | 0.8 | 15.0 |
| P11 | Optimization dashboard | 5 | 5 | 1 | 2.4 | 10.4 |
| P12 | Active testing scheduler | 5 | 5 | 1 | 2.0 | 12.5 |

The RICE column would suggest P4 first by raw score. Actual ordering preserves dependency: P3 (tenancy) precedes P4 (gateway) because per-tenant cost attribution per D41 needs the tenant-registry surface, and tenant context is required throughout the inference path. Dependency overrides RICE; RICE is honest about how strongly a package contributes evidence, not about whether it can run in isolation.

## Initiative 2: Phase 2 (committed; the daily driver)

Methodology-as-product UX on Phase 1's substrate per D93, concretised at D156 as a whole-life
causal daily driver for the first-instance senior-leader ICP: a prioritised today surface and a
causal decision map (a Causal Decision Diagram per Decision Intelligence), two views of one
graph, holding the ICP's professional and personal day without a boundary between them, because
the causation runs across it. Active, not passive: the system watches tracked state, surfaces
what is due or slipping, and traces the causal ripple to outcomes as recommendation-shaped output
per D9. The bet, the ICP, and the methodology-as-proprietary-insight are unchanged. Stages and
packages at `charter/packages.md` Phase 2 section; user segment at
`charter/phase-2-user-segment.md`; the design arc at `charter/phase-2-design-7step.md`.

**Phase 2-A is one stage in two waves (v8).** Wave 1 (P13–P16) shipped the thin slice; the Phase
2-A dogfood gate revealed the usable threshold sits above it. Wave 2 (P17–P20) is the plan-side
build that reaches the gate — Padhanam as the assessment layer over the work tools the user already
keeps (the assess-not-replace principle in `principles.md`; the plan-side work-unit model at D166).
The Phase 2-A close gate (dogfooding plus the senior-leader-ICP read) sits at the end of Wave 2.
Phase 2-B (the B-stream) renumbers to P21–P24; the v8 old→new mapping in the version log below is
the single source of truth for the renumber.

### Phase 2-A Wave 2 packages (the plan-side build), with RICE scoring

The dogfoodable daily driver, four packages. The six real goals are seeded by script (the
German/get-a-job precedent), so the assessment reads against them identically whether typed or
seeded — a goal-capture UI is **not** on the critical path and drops to Phase 2-B, shaped by use.
RICE is illustrative; effort confirms against the codebase at each package open; the order matters
more than the decimals.

| Package | Reach | Impact | Confidence | Effort | RICE |
|---|---|---|---|---|---|
| P17 Task ingestion (Google Tasks) | 4 | 1.5 | 0.9 | 1 | 5.4 |
| P19 Goal-aligned assessment (the moat) | 3 | 3 | 0.8 | 2 | 3.6 |
| P18 Unit-of-work correlation | 5 | 2 | 0.7 | 2.5 | 2.8 |
| P20 Missing-facet suggestions | 5 | 1 | 0.6 | 2 | 1.5 |

The pass earns its keep by burying the rebuilt-Wingtip Scheduling trap as a scoring artifact. Suggestions (P20)
carry joint-highest Reach (the nudges seen every day) yet land last, because Impact is parity (the
time-blockers already ship them) and Confidence is low (the credulity risk the S62 smoke showed).
The assessment (P19), the actual moat, carries the lowest Reach (it touches only structured work)
and is rescued by Impact — the D166 Kano delighter. Reach misleads in both directions; Impact and
Confidence are the correction.

**Build sequence** (dependencies constrain it and agree with the scores where it counts): P17 task
ingestion (cheapest, foundational, unblocks P18) → P18 correlation (the substrate gate; nothing
downstream exists without it) → P19 assessment (the moat, before suggestions — the D166 Kano
discipline enforced in the sequence) → P20 suggestions (last; lowest RICE, highest credulity risk,
parity value). **The dogfoodable threshold sits after P19**: goals seeded, tasks ingested, units
correlated, the goal-aligned assessment live — the operator runs a real day through it. P20
enriches the day and lands just after the threshold rather than gating it.

**Precondition (outside the RICE pass): S64 test-integrity.** Runs first or alongside, not competing
for priority — it is the condition that the green wall is trustworthy before four packages of
surface area land on it: the four-session-red clock-seam test and the fifth-recurrence
mock-blindness that shipped a real bug caught only by luck.

**Held for Phase 2-B, shaped by the dogfood** (none scored now; the dogfood verdict prioritises
them): the five D166 constraint dimensions (dependency, deadline, capacity, recurrence,
waiting-on-others); the goal-capture UI (deferred by seed-first); Trello ingestion (the second task
adapter, the hardest assess-not-replace proof); personal-chat ingestion (connector-blocked for
iMessage / personal WhatsApp); write-back (a fresh decision against the read-only posture if ever
wanted); and the v6 B-stream, slid to P21–P24.

---

## Version log

- **v1** (P1 framing, retroactively recorded). Initial framing per `bet.md`. Twelve packages, dependency-ordered, twelve sessions estimated total. RICE column not present at framing.
- **v2** (P3 post-close strategic session, post-D41-D48 landing). Reasoning category: **discovery**. The strategic-tree artefact is promoted to a literal living document in this version per D44, with the existing implicit structure made explicit. RICE columns added per D42, with scores judged at this session and applied retroactively for P1–P3. No package added or removed; sequencing unchanged. Phase 2 framing is delegated to the Phase 1 close audit.
- **v3** (P4-post carryover-cleanup strategic session, 2026-05-06). Reasoning category: **discovery** (drift-correction shape). The 2026-05-06 status-snapshot pass surfaced that the P2 row's title "Identity foundation" did not match the as-built P2 archive at `docs/archive/packages/p2.md` ("First LLM call"). The mismatch carried forward from S4 through P4 close without a recorded D-entry; D52 (this session) defers identity foundation to Phase 2 in supersession of D3, and this version updates the P2 row title to "First LLM call" so the table reflects what shipped. RICE scores unchanged at 2/1/3/1.6 = 3.75 — the v2 retroactive scoring was applied against the actual P2 work, not against the original Identity-foundation framing, and the title correction in this version brings the row's display name into line with that. Drift-correction is a form of discovery (discovery of error in the artefact relative to as-built reality), not a fifth category in the four-category D44 taxonomy. The drift is recorded as the first entry in `charter/methodology.md`'s Failure modes section; the discipline addition (charter-vs-archive consistency check at every package close) is named there as a promotion candidate for the methodology mechanical-enforcement upgrades section. No package added or removed; sequencing unchanged. Phase 2 absorbs the deferred identity foundation in addition to the deferred-decisions cluster (cost ceilings, multi-tier routing, throttling, full DORA/CORE4 instrumentation, production-shaped onboarding, step-mode tooling, pricing-table format evolution) — Phase 2 framing at the Phase 1 close audit accounts for the additional scope.
- **v4** (P7→P8 topology design strategic block, 2026-05-11). Reasoning category: **discovery**. Workflow primitive surfaced from 2026-05-11 captures entry post-P7 close. P8 text revised to remove LangGraph and name AgentLoopExecutor per D84. Workflow context architecture committed for Phase 2 implementation per D83. Six new D-entries (D80 four-layer constraint stack; D81 methodology aggregate v2 with multi-role refinement and per-field binding mode; D82 platform invariants and Padhanam-as-intelligence-layer with five danger-targeted invariants; D83 workflow as architectural primitive with Phase 2 implementation; D84 P8 agent runtime adapter shape and LangGraph deferral; D85 McKinsey 7-Step methodology authoring placement) land in the topology design session strategic commit, alongside the new workflow context charter file at `charter/contexts/workflow.md`, the revised P8 epic note at `charter/packages/p8-epic.md`, the new User safety section in `charter/principles.md` with the refined methodology-embedded principle, the P8 line revision in `charter/packages.md`, three new deferred-decisions entries (cascading-harm invariant shape; retrieval-bound hard-constraint shape; per-role binding-mode override), the captures triage resolution for the 2026-05-11 P7 strategic block synthesis entry, and the `current-package.md` between-packages transition reflecting topology design landed. No package added or removed; P8's scope shifts inside its existing slot (agent runtime ships with hand-rolled AgentLoopExecutor per D84; workflow context architecture committed for Phase 2 per D83). RICE scores for P8 unchanged at 5/5/2/1.6 = 31.25; the scope reframing preserves the bet's success criterion 2 (one agent running at Phase 1 close) without expanding P8 effort. Phase 2 absorbs workflow context implementation, LangGraph adapter, consumer-grade UX surface, and gallery pre-population content alongside the existing Phase 2 deferral cluster.
- **v5** (Phase 1 / Phase 2 boundary strategic block, 2026-05-13). Reasoning category: **discovery + signal**. D92 confirms Phase 1 scope at P1 through P12 with P9-P12 reframed as backend-only substrate; D93 commits Phase 2 direction to methodology-as-product positioning with focus purely on UX/UI. The discovery dimension: the audit conversation surfaced that P9-P12 in their originally-planned form contained UI elements that under D93's UX-purity commitment naturally belong in Phase 2; the reframing makes the UI-versus-backend boundary explicit. The signal dimension: the bet's load-bearing differentiator (consumer-expectance-with-enterprise-guardrails) and the three PRFAQ candidate framings were tested against each other in the audit conversation; methodology-as-product emerged as the only candidate satisfying both dimensions of the differentiator without bet revision. RICE table scores stand at v4 values; effort estimates for P9-P12 revise at each package open as backend-only scope sharpens (the UI elements removing from P9 through P11 reduces effort relative to the originally-scored values, but specific updates are operator-judged at package open). No package added or removed; sequencing unchanged.
- **v6** (Phase 2 packaging commitment, 2026-05-21). Reasoning category: **discovery**. Phase 2 commits as Initiative 2 of the bet, scoped through the Phase 2 design 7-Step arc per D93 (methodology-as-product positioning). The arc converged on eight packages across two stages. **Phase 2-A: Operator-validated find-rhythm-and-settle-in instance.** Four packages P13 through P16. Wave structure: P13 foundational substrate (Wave 1); P14 core domain entities and trust substrate (Wave 2); P15 messaging substrate and user-facing surfaces (Wave 3); P16 late user-facing surfaces (Wave 4). **Phase 2-B: Scale to broader senior-leader-ICP.** Four packages P17 through P20. Wave structure: P17 B9 elevated plus foundational substrates (Wave 1); P18 operational delivery plus agent-runtime exercise (Wave 2); P19 accumulated-history wave (Wave 3); P20 Phase 2-B late or Phase 3 boundary (Wave 4). **Phase 2-A close gate condition.** Operational thresholds plus dogfooding-evidence thresholds per Step 5 substrate-completion criteria. Specifically: operator dogfooding across at least one week of real use; senior-leader-ICP test condition validation against operator-as-first-instance; substrate-completion verification across the four Phase 2-A waves. **Cross-references.** `charter/phase-2-design-7step.md` Step 7 close for the discovery source; `charter/packages.md` Phase 2 section for the canonical commitment surface; `charter/architecture.md` Phase 2 architectural primitives section for the six committed primitives; `charter/phase-2-user-segment.md` for the senior-leader-ICP commitment.
- **v7** (Post-P15 strategic block, 2026-06-04). Reasoning category: **discovery**. The post-P15 strategic block surfaced that D93's committed-but-abstract "methodology-as-product UX" resolves into a concrete shape: a whole-life causal daily driver for the first-instance senior-leader ICP, recorded at D156. Two discoveries drove it. The operator could not dogfood through technical testing, and the Phase 2-A close gate produces no evidence without a daily-use surface; the operator's abandoned standalone tracker evidences that a passive tool goes quiet when life moves, and active surfacing is the antidote, the observability differentiator pointed at a life. And a causal model of how actions reach outcomes necessarily spans personal and professional, because the causation does, so the personal-professional split is not a viable scope boundary. The bet is unchanged (platform-as-demonstration, methodology-as-proprietary-insight, observability-as-differentiator); the ICP is unchanged (senior product leaders, now seen whole). This extends D93 and the v6 packaging; it does not supersede them. Package impact: P16 reframes as the first daily-driver surface from its committed surfacing-mechanics and user-authored-items scope; Phase 2-B (P17 to P20) absorbs three daily-driver epics (cadence-with-staleness, scheduled-with-lead-time, the causal-decision-graph context) plus the substrate-shape exercise (CDA-beyond-portfolio) and the Day concept, into the existing B-stream. No new initiative; the daily driver is the integrating shape of Initiative 2. RICE re-scores the affected Phase 2-B packages at sequencing. Cross-references: D156; `charter/packages.md` Phase 2 section; `charter/phase-2-user-segment.md` whole-life clause; `charter/deferred-decisions.md` two new entries; `charter/product-methodology.md` DI and CDD addition.
- **v8** (Plan-side build scoping strategic block, 2026-06-08). Reasoning category: **discovery** (gate-driven correction shape). The Phase 2-A dogfood gate revealed its own threshold: the Wave 1 thin slice (P13–P16) sits below the usable line a daily driver must clear, so Phase 2-A extends from four packages to eight. This is a **gate-driven correction** — the gate told us the threshold is higher than first scoped — **not silent scope-creep**; recording it as such is the honest reading and keeps the next audit from flagging it. **Phase 2-A is now one stage in two waves:** Wave 1 (P13–P16, the thin slice) and Wave 2 (P17–P20, the plan-side build that reaches the gate). The Phase 2-A close gate (dogfooding plus the senior-leader-ICP read) sits at the end of Wave 2; it is the same gate reached later than first scoped, not a new stage, so it is not split out into its own stage or initiative. **Wave 2, four packages** — Padhanam as the assessment layer over the work tools the user already keeps (the assess-not-replace principle; the plan-side work-unit model at D166): **P17** task ingestion (Google Tasks, TASKS_READ behind the D148/D155 read-only seam, reusing the connected Google provider as an added scope); **P18** unit-of-work correlation (the D166 Padhanam-native edge, inferred by title/time, high-precision, never written back); **P19** goal-aligned assessment (orphan work + the neglected goal — the D166 Kano delighter, the moat); **P20** missing-facet suggestions (the parity layer, carrying the credulity discipline). **Seed-first reframe:** the six real goals are seeded by script (the German/get-a-job precedent), so the assessment reads against them identically whether typed or seeded — the goal-capture UI drops off the critical path and becomes a Phase 2-B concern real use will shape, removing a package from the path to the gate. The RICE pass and build sequence are at the Initiative 2 Wave 2 subsection above; the pass buries the rebuilt-Wingtip Scheduling trap (Reach alone would build the commodity suggestions first; Impact and Confidence correct it). Dogfoodable threshold after P19; P20 lands just after. **S64 test-integrity** is the precondition, outside the RICE pass. **Phase 2-B renumber — old→new mapping (this clause is the single source of truth):** the v6 B-stream packages slide by four — **P17→P21** (B9 elevated + foundational substrates), **P18→P22** (operational delivery + agent-runtime exercise), **P19→P23** (accumulated-history wave), **P20→P24** (Phase 2-B late / Phase 3 boundary). This **resolves a deferral, not a commitment**: v7 left Phase 2-B's package assignment and RICE ordering explicitly unsettled until Phase 2-B framing, and `charter/packages.md` says the same, so claiming P17–P20 for Phase 2-A Wave 2 is legitimate rather than a renumber of locked slots. **Three drift-safety rules (the v3 cure, applied):** (1) renumber **only the two live surfaces**, `charter/roadmap.md` and `charter/packages.md`; (2) **leave every historical reference verbatim** — D-entries (D120's "P17 Wave 1 Cluster B9" and the rest), `charter/phase-2-design-7step.md` (59 mentions), `charter/phase-2-audit-inputs.md`, `charter/architecture.md` — because editing history to chase the numbers is the exact move that birthed the v3 charter-vs-archive drift; (3) **this v8 old→new mapping is the single source of truth** for the renumber, pointed to from both live surfaces, so anyone touching a B-stream number meets it. The dangling historical refs are not the danger; the temptation to chase and edit them is. **Held for Phase 2-B (shaped by the dogfood):** the five D166 constraint dimensions (dependency, deadline, capacity, recurrence, waiting-on-others); the goal-capture UI; Trello ingestion (the second task adapter, the hardest assess-not-replace proof); personal-chat ingestion (connector-blocked); and write-back. No new initiative; this is Initiative 2 / Phase 2-A finally satisfying its own close criterion. RICE for the renumbered B-stream (P21–P24) still settles at Phase 2-B framing per v7. Cross-references: D166 (the plan-side work-unit model); D156 (the daily driver as Initiative 2's integrating shape); D148/D151/D155 (read-only external-cache ingestion); D17 (cross-context read seam); D161 (the connected Google provider P17 reuses); the assess-not-replace principle in `charter/principles.md`; the task-tool ingestion entry in `charter/deferred-decisions.md`; and `charter/packages.md` Phase 2 section (the canonical package surface, renumbered in this commit).
