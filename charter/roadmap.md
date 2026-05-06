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

## Initiative 2: Phase 2 (direction TBD)

Decided at the Phase 1 close audit. Candidate shapes are documented in `prfaq.md` as alternative version-1 stories; the audit picks one (or surfaces a fourth) and the v2 PRFAQ press release narrows accordingly.

---

## Version log

- **v1** (P1 framing, retroactively recorded). Initial framing per `bet.md`. Twelve packages, dependency-ordered, twelve sessions estimated total. RICE column not present at framing.
- **v2** (P3 post-close strategic session, post-D41-D48 landing). Reasoning category: **discovery**. The strategic-tree artefact is promoted to a literal living document in this version per D44, with the existing implicit structure made explicit. RICE columns added per D42, with scores judged at this session and applied retroactively for P1–P3. No package added or removed; sequencing unchanged. Phase 2 framing is delegated to the Phase 1 close audit.
- **v3** (P4-post carryover-cleanup strategic session, 2026-05-06). Reasoning category: **discovery** (drift-correction shape). The 2026-05-06 status-snapshot pass surfaced that the P2 row's title "Identity foundation" did not match the as-built P2 archive at `docs/archive/packages/p2.md` ("First LLM call"). The mismatch carried forward from S4 through P4 close without a recorded D-entry; D52 (this session) defers identity foundation to Phase 2 in supersession of D3, and this version updates the P2 row title to "First LLM call" so the table reflects what shipped. RICE scores unchanged at 2/1/3/1.6 = 3.75 — the v2 retroactive scoring was applied against the actual P2 work, not against the original Identity-foundation framing, and the title correction in this version brings the row's display name into line with that. Drift-correction is a form of discovery (discovery of error in the artefact relative to as-built reality), not a fifth category in the four-category D44 taxonomy. The drift is recorded as the first entry in `charter/methodology.md`'s Failure modes section; the discipline addition (charter-vs-archive consistency check at every package close) is named there as a promotion candidate for the methodology mechanical-enforcement upgrades section. No package added or removed; sequencing unchanged. Phase 2 absorbs the deferred identity foundation in addition to the deferred-decisions cluster (cost ceilings, multi-tier routing, throttling, full DORA/CORE4 instrumentation, production-shaped onboarding, step-mode tooling, pricing-table format evolution) — Phase 2 framing at the Phase 1 close audit accounts for the additional scope.
