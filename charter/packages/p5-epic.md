# P5 epic note (v1)

## Goal

Phase 1's evaluation harness scaffolded as a bounded context, with the data model that captures the architecture's posture on human oversight per D53. Reading C: humans are load-bearing in the scoring loop; the data model reflects that even though the UI for human review defers to a later package. At P5 close: tenant-authored scoring sheets exist as versioned, immutable, role-gated data in per-tenant DBs; deterministic and LLM-as-judge appliers run against agent outputs and produce scores against those sheets; cost-per-successful-task is computable from the trace cost data attached at P4; a CLI runner produces a regression report comparing two runs of a scoring sheet against an interaction set. Recommendation surfaces consuming the harness output (P11) and human-review UI are out of scope.

## Architectural commitments expected

P5 expects to ship at minimum three D-entries beyond D53:

- **Replay target seam.** Whether the replay engine calls `LiteLLMAdapter.complete()` directly or a `Replayable` port the agent runtime later implements. Likely committed at S17 when the replay engine lands. Kano: performance.
- **Cost-per-successful-task computation locus.** Computed in-harness from `gen_ai.cost.*` attributes captured at replay time, versus queried from Langfuse for cost rollup. Likely committed at S17 when the metric implementation lands. Kano: must-have (D8/D41 enforcement); the choice within "must-have" is between two implementation shapes.
- **Scoring-extensibility shape.** Strategy port from inception (option-preserving, performance Kano) versus hardcoded scorer list with port-retrofit later (must-have-only). Likely committed at S16 when the first deterministic applier lands. Kano: performance.

Additional D-entries possible if structural decisions surface during build. The session-close discipline catches them; build sessions do not pre-commit to D-entry counts.

## Out of scope

- **Human-review UI.** Data model carries `reviewed_by_user_id` and `confirmed_at` from inception per D53; the UI surfacing the human-review path defers to P10 (audit-log viewer) or P11 (optimization dashboard) territory.
- **Platform-baseline scoring sheet library.** Deferred per D53 to a later activation condition (real onboarding flow per D13, or a cross-tenant curated library with at least one real consumer beyond demoware).
- **Recommendation surface.** P11 territory; P5 produces the data the recommendation engine consumes.
- **Active testing scheduler.** P12 territory.
- **Eval-suite import from external tools** (Promptfoo, RAGAS, OpenAI Evals). PRFAQ pitch, not Phase 1 work; the canonical-interaction-set shape is the import boundary, but the importers themselves activate as customer demand surfaces.
- **Web UI for results.** P11 territory.
- **LLM-as-judge model selection beyond the dev default** (Qwen 2.5 7B per D15). Activates when calibration evidence surfaces.

## Forecast session split (v1 intent; revisable at build-session framing)

- **S16: Foundations.** Bounded context creation at `contexts/evaluation/`, scoring sheet domain model (sheet, revision, criterion, applier, rubric-application), per-tenant migration, first deterministic applier, end-to-end test through the new context. Charter touch-points: `charter/schema.md`, possibly D-entry on scoring-extensibility shape if structural decision surfaces.
- **S17: Replay engine and appliers.** Replay against the inference adapter (replay-seam decision committed at this session), additional deterministic appliers, LLM-as-judge applier, cost-per-successful-task computation locus committed.
- **S18: Regression report, CLI runner, P5 close.** Regression-report shape, CLI entry point, archive at `docs/archive/packages/p5.md`, measured-outcomes paragraph in `log/packages.md`, current-package transition to between-packages.

## Acceptance criteria for package close

1. New bounded context at `contexts/evaluation/` exists with hexagonal layers (`domain/`, `application/`, `ports/`, `adapters/inbound/`, `adapters/outbound/`) per D16.
2. Per-tenant Alembic migration adds tables for scoring sheets and revisions, criteria, applier records, and rubric-application records (the score-result shape). All seeded tenants migrate cleanly.
3. The scoring sheet domain model is versioned and immutable per version; updates create new revisions; rubric-application records reference the revision id, not the sheet id, so historical evaluations stay anchored to the version they were applied against.
4. The applier model treats deterministic primitives as code (a small bounded library inside `contexts/evaluation/`) and prompt appliers (LLM-as-judge) as data records, both subject to the same authorship and versioning model as the scoring sheet itself.
5. At least one deterministic applier and one LLM-as-judge applier run end-to-end against a stored scoring sheet.
6. The human applier mode is represented in the data model only: rubric-application records carry `reviewed_by_user_id`, `confirmed_at`, `automated_score`, and `human_score` from inception. P5 ships only the automated write path (deterministic and prompt appliers populate `automated_score`); the human-score write path and any UI for human review defer to P10 or P11 territory per D53.
7. Replay engine exercises an interaction (input → call → output) against the inference adapter and produces rubric-application records for every applier on the relevant scoring sheet.
8. Cost-per-successful-task is computable from rubric-application records joined with the trace store's `gen_ai.cost.*` attributes; the computation lives in `contexts/evaluation/` and does not query Langfuse directly per D27.
9. A CLI runner (`make eval-run` or equivalent) executes a scoring sheet against an interaction set and produces a regression report comparing the current run against a prior baseline.
10. `make lint` keeps all import-linter contracts; P5 adds at least one new contract for `contexts/evaluation/` boundaries; AST tests pass; `make scan` clean against the documented exceptions list.
11. End-to-end integration tests pass across tenant A and tenant B with no cross-tenant leakage of scoring sheets or rubric-application records.
12. `charter/schema.md` updated in the same commits as the migrations.
13. `docs/archive/packages/p5.md` exists with retrospective following the P3/P4 archive shape per D31.
14. `log/packages.md` gains a P5 entry containing a measured-outcomes paragraph per D40.
15. Archive at `docs/archive/packages/p5.md` reconciles against this v1 draft per D43, with the delta as the audit deliverable.
16. `charter/current-package.md` transitions to between-packages state pointing at the P5 archive.

## RICE

| Reach | Impact | Confidence | Effort | RICE |
|---|---|---|---|---|
| 5 | 5 | 2 | 1.4 | 35.7 |

- **Reach 5.** Exercises four of the bet's evidence-needs: architectural decisions (bounded context placement, scoring sheet primitive, applier-as-data shape), tenant isolation maintained for evaluation data, observability differentiator (cost-per-successful-task is the lead metric), optimization-recommendation foundation (rubric-application records are the substrate P11 consumes).
- **Impact 5.** Without the eval harness the optimization-recommendation differentiator has no calibrated data to consume; second highest-impact package after P4.
- **Confidence 2.** Substrate is in (P4 cost wiring, tenant context, inference adapter), but P5's design space is wider than P4's. Framing has narrowed the space; build sessions surface the residual choices.
- **Effort 1.4.** Three sessions: foundations and storage at S16, replay and appliers and cost wiring at S17, regression report and CLI and close at S18.

## Kano

Package-level: **must-have**. The eval harness is the substrate for D8 (cost-per-successful-task) and D9 (recommendation-shaped output); without it the optimization-recommendation differentiator has no data to consume.

Decision-level commitments set at framing per D53:

- **Storage location per-tenant only:** must-have. D1/D32 isolation discipline; no Phase-1 forcing function for control-plane storage.
- **Scoring sheet versioned and immutable per version:** must-have. Authored data with historical-stability requirement.
- **Appliers as data, except deterministic primitives in code:** performance. Change-velocity asymmetry between code-deploys and prompt-tweaks; preserves iterate-fast judge-prompt tuning inside the same versioning and authorization model as the sheet itself.
- **Reading-C posture (data model absorbs human review; UI defers):** performance. Preserves the case-study audit posture without pulling UI scope into a CLI-shaped package.
