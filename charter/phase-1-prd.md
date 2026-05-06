# Phase 1 PRD

Living document per D43. Original draft preserved at every revision; as-built sections appended at phase audits. Phase 1 close produces the canonical phase PRD with full delta capture.

## Version 1 (P3 post-close strategic session) — initial draft, recorded retroactively as the Phase 1 baseline

### Problem statement

[OPERATOR REVIEW — case-study positioning] AI-assisted development has matured enough that the question for product organisations is no longer "can the model write code" but "what does this enable for the people directing the work." Senior product leaders, CPOs, and consultancies are watching for credible evidence about how the role changes when implementation is delegated to AI agents under the direction of a single person rather than a team. Phase 1 of the case study generates that evidence by running the experiment in the open: a senior product leader directs the implementation of an enterprise-grade agentic platform through Claude Code, with the platform built to procurement-realistic standards, and with every architectural decision, audit finding, and methodology observation recorded in public.

### Target user

[OPERATOR REVIEW — audience framing] Phase 1 has two readers, in priority order. The primary reader is the operator, who is the senior product leader running the experiment and using the case study as an evidence-generating exercise. The secondary reader is the prospective audience for the eventual case-study output: senior product leaders, CPOs, and consultancies investigating how AI-assisted development changes what product leadership can deliver directly. Phase 1 deliverables shape Phase 2 audience commitments; the platform's eventual users (enterprise teams who would adopt agentic systems built this way) are not Phase 1 readers but their concerns shape the architectural decisions the case study records.

### Scope

In scope for Phase 1:

- Twelve packages per `roadmap.md`, ordered for dependency and learning value.
- Single-tenant local stack with database-per-tenant architecture (D1) and per-tenant Postgres instances (D32).
- Bounded contexts on hexagonal layers (D16) with import-linter and AST enforcement.
- Identity, tenancy, LLM gateway, evaluation, source ingestion, agent CRUD, agent runtime, run history, audit viewer, optimization dashboard, active testing — the twelve packages as specified in `packages.md`.
- Cost capture and per-tenant cost attribution at P4 setup per D41.
- Charter discipline: living phase PRD, living roadmap, living PRFAQ, role-function audits, append-only D-entries with Kano categories from D41 forward, framework-driven option assessment per D42.
- Methodology document maturing across the phase, capturing the architect-implementer pattern with enough specificity that another senior product leader could read it and adopt the discipline.

Out of scope for Phase 1, deferred to Phase 2 or beyond:

- Production deployment, multi-region operation, customer onboarding (the platform is the demonstration, not the product).
- Cost ceilings, multi-tier model routing, progressive throttling (deferred per `deferred-decisions.md`; configuration columns land in P4 setup for forward compatibility, enforcement defers).
- Step-mode-shaped automation for narrow task types (deferred for review at Phase 1 close; the safe-task-type list is the close-audit deliverable).
- Brownfield ingestion patterns for additional contributors (deferred until contributor scaling is a real planning question).
- Sub-workspaces inside tenants (D2: deferred to V2 if needed).
- Runtime retrieval-strategy selection (D5: deferred to V2).
- Orchestrators beyond LangGraph until activation (deferred per `deferred-decisions.md`).

### Success criteria

By Phase 1 close:

- A single tenant runs locally with the full stack.
- One agent can be configured, run, audited, and optimised through the platform's own tooling.
- The evaluation harness produces meaningful quality signals.
- The trace capture layer surfaces optimization recommendations, with the cost dimension wired in (D41).
- The operator can explain every architectural decision and why it was made, in terms of the enterprise constraints that motivate it.
- The methodology document captures the architect-implementer pattern with enough specificity that another senior product leader could read it and adopt the discipline.
- The Phase 1 close audit produces no drift findings classified as severe.
- A Phase 1 PRD as-built section is appended to this document capturing the delta between this draft and what shipped.

The first four are platform artefacts that prove the proposition. The fifth and sixth are the methodology deliverables that the case study's audience would find load-bearing. The seventh and eighth are charter-discipline outputs that close the audit loop.

### Key bets

- **Architectural discipline at enterprise scale is the test condition, not the differentiator.** SOC 2 Type II, ISO 27001, database-per-tenant, hash-chained audit, jurisdiction-aware design, OTel-as-portability-boundary — the constraints are not aspirational, they are the level at which the proposition is being tested. A demonstration that AI-assisted development can produce a single-tenant prototype answers nothing useful to the target audience.
- **The methodology is the proprietary insight; the platform is what makes it credible.** The architect-implementer pattern, the role-function audit categories, the living-document discipline, and the append-only decision log together are the artefact that distinguishes this from standard AI-assisted-development demonstrations. Phase 1 produces the methodology by running it; the methodology document captures the pattern.
- **Mechanical enforcement scales with the codebase; operator attention does not.** Import-linter contracts (15+) and AST tests make architectural rules CI failures rather than review comments. Phase 1 trajectory is upward on both counts.
- **Observability is differentiator, not feature.** D7, D8, D9 commit the optimization layer to recommendation-shaped output with a bounded metric scope. D41 commits the cost dimension that completes it.
- **Two-surface model is conceptual, not UI-bound** (D47). Mode separation is maintained by operator discipline and artefact distinctness, not by tool separation.

### Open questions

- Will Phase 1 throughput hold through P11 and P12 within operator capacity? S9-era reflection raised the question; the Phase 1 close audit answers it.
- Will the optimization-recommendation surface produce signal worth acting on under single-tenant local conditions? P11 and P12 either confirm or surface as a Phase 2 redirection candidate.
- Will the methodology survive its own pivot at Phase 2 framing? The audit posture treats this as the load-bearing test of the methodology; surviving the pivot means the discipline transfers, not just the artefact.
- What does the Phase 2 framing of the case-study audience pivot toward, if anything? `prfaq.md` records candidate stories; the Phase 1 close audit picks one or surfaces a fourth.

### Acceptance shape

Phase 1 close audit produces:

- The canonical Phase 1 PRD with as-built section appended below.
- The Phase 1 close roadmap version (per D44) with reasoning category.
- The Phase 2 PRFAQ first draft as a transition artefact (per D45).
- Drift findings, role-function audit results across the five categories (per D46), Kano-distribution and RICE-defensibility checks (per D42), DORA and CORE4 metric review (per D40).
- The Phase 2 direction decision.

---

## v1 in-flight correction (carryover-cleanup strategic session, 2026-05-06)

D52 (this session) defers identity foundation (Keycloak realm, OIDC integration, SAML SP, SCIM 2.0 endpoint, federated session management) from Phase 1 to Phase 2 in explicit supersession of D3. The v1 Scope section's package enumeration in the In-scope bullet list reads "Identity, tenancy, LLM gateway, evaluation, source ingestion, agent CRUD, agent runtime, run history, audit viewer, optimization dashboard, active testing — the twelve packages as specified in `packages.md`." That enumeration is corrected as follows: P2 is "First LLM call" per `charter/packages.md` and `charter/roadmap.md` v3, not "Identity foundation"; the original identity foundation work activates at Phase 2 when production deployment context arrives (real IdP connections, SCIM provisioning from real HR systems, SAML against enterprise IdPs). Phase 1 retains auth-middleware-on-every-endpoint per D23 with the dev signed-token backend and the production-shaped Keycloak backend stubbed.

v1 body preserved verbatim per D43's append-only-at-version-level discipline; this correction is recorded as a separate section rather than as an in-place edit to v1. The carryover operator-review pass on the v1 Problem statement and Target user sections (carryover from the P3-post strategic session) will catch any further drift surfaced by this scope correction.

---

## As-built section (appended at Phase 1 close)

[Empty until Phase 1 close audit. The delta between this draft and the as-built reality is the audit deliverable.]
