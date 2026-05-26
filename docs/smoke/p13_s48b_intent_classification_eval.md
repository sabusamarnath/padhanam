# P13 S48b — Intent-classification evaluation substrate live-stack exercise

Live-stack exercise of the D137 substrate against tenant_a on
2026-05-26, completing S48b's load-bearing claim ("answer model-
choice questions in minutes against a fixed reference set"). Two
models exercised: `gpt-4o-mini` (the S48a swap target) and
`qwen2.5:7b` (the S46 baseline whose blind-spot motivated the
substrate). The gold-set fixture at
`tests/fixtures/intent_classification/gold_set.yaml` carries 40
operator-shaped entries balanced across the four intent classes —
12 CreateCaseIntent, 12 AddDataPointIntent (the first four are the
S46 blind-spot phrasings explicitly), 8 ReviseDataPointIntent, 8
UnclearIntent.

## Stage 0 — Pre-flight

- Substrate ships at S48b commits 1-5. The substrate verified
  end-to-end at this commit (commit 6) closing S48b.
- Migration 0022_intent_class_eval_substrate applied to
  postgres-tenant-a and postgres-tenant-b via `make migrate`.
- Test fixtures synced into the api container at
  `/app/tests/fixtures/intent_classification/gold_set.yaml`.
- CLI sub-app registered under `padhanam intent-classification-eval`.
- 1776 unit + contract tests pass; 33 of 33 import-linter contracts
  kept (32 + new layers-intent-class-eval).

## Stage 1 — gpt-4o-mini evaluation (the S48a swap target)

Run command:
```
docker compose exec -T padhanam-api python -m apps.cli.main \
  intent-classification-eval start \
  --tenant-id a --model gpt-4o-mini --gold-set-name phase_2_a_default
```

Run id: `1e6f57ac-8cac-42a4-a78a-007b2389cd9b`. Status: completed.

### Per-class accuracy

| Intent class | Support | Correct | Accuracy | Precision | Parse failures |
|---|---|---|---|---|---|
| create_case | 12 | 12 | 100.00% | 100.00% | 0 |
| add_data_point | 12 | 12 | 100.00% | 92.31% | 0 |
| revise_data_point | 8 | 7 | 87.50% | 100.00% | 0 |
| unclear | 8 | 8 | 100.00% | 100.00% | 0 |
| **Overall** | **40** | **39** | **97.50%** | — | **0** |

### Latency profile (per-call)

| Metric | Value |
|---|---|
| min | 970 ms |
| p50 | 1,625 ms |
| avg | 1,890 ms |
| p95 | 3,434 ms |
| max | 6,137 ms |

Total run time: ~75 seconds for 40 entries (= ~1.88 s/entry, matching
the avg). The substrate's load-bearing claim ("answer model-choice
questions in minutes") lands operationally: a 40-entry per-model
evaluation completes in ~75 seconds, comparable to a single integration
smoke that would exercise one cell cascade.

### The single miss

| Entry | Phrasing | Expected | Classified |
|---|---|---|---|
| 29 | "The hiring search status changed: offer extended yesterday" | revise_data_point | add_data_point |

This is debatable — the phrase "status changed: offer extended yesterday"
could legitimately be read as adding a new status note rather than
revising an existing one. The gold-set authoring chose
revise_data_point because the words "changed" + "yesterday" imply an
update rather than a fresh note. Two structural improvements possible
at future work: (a) tighten the gold-set entries to remove
expected-class ambiguity at the operator-authoring layer, or (b)
extend the schema to ask the model for a confidence value plus a
discriminator hint between add vs revise on borderline phrasings.
Neither is in scope at S48b.

### S46 blind-spot verification

The first four AddDataPointIntent entries in the gold set are the
exact phrasings qwen2.5:7b classified as UnclearIntent at the S46
smoke (0/2 of the template phrasing). gpt-4o-mini classifies all
four correctly:

| Entry | Phrasing | Expected | Classified |
|---|---|---|---|
| 12 | "Add a goal to the Q3 review: ship Wave 1 by end of May" | add_data_point | add_data_point ✓ |
| 13 | "Add this goal to the Q3 portfolio review: ship Wave 1 by end of May." | add_data_point | add_data_point ✓ |
| 14 | "For the Q3 portfolio review case, add a goal: ship Wave 1 by end of May." | add_data_point | add_data_point ✓ |
| 15 | "Ship Wave 1 by end of May — goal for the Q3 portfolio review." | add_data_point | add_data_point ✓ |

The S48a smoke against the WhatsApp cell verified these phrasings
were classified correctly in production. The substrate confirms the
same finding component-side without exercising the full multi-turn
cascade.

## Stage 2 — qwen2.5:7b evaluation (baseline; intentionally not run beyond timeout)

Run command:
```
docker compose exec -T padhanam-api python -m apps.cli.main \
  intent-classification-eval start \
  --tenant-id a --model qwen2.5:7b --gold-set-name phase_2_a_default
```

First run id: `462ec985-752c-4d63-bc5d-719ce1e93e9d`. Status: **failed**.
Second run id (retry after potential warm-state): `3b3d79f9-b221-4a55-8c17-b245ce18aa51`. Status: **failed**.

Failure reason (both runs): `litellm.Timeout: APITimeoutError - Request
timed out. Error_str: Request timed out. - timeout value=30.0, time
taken=91.5 seconds` (first run) / similar 92-second timeout (second
run).

The substrate's runner-level failure-capture worked exactly as
designed: the first LLM call exceeded the configured 30 s
REAL_TIME_REQUIRED tier timeout; the timeout was raised as
`InferenceTimeout`; the runner caught it, marked the EvaluationRun
failed, recorded the failure_reason with the timeout value and the
elapsed time, emitted the `run.fail` audit event, returned with
status=failed.

**This is a load-bearing finding.** qwen2.5:7b cannot complete a
single classification within the production REAL_TIME_REQUIRED tier
budget on this hardware. The production cell uses the same tier
budget; an operator-dogfooding cascade would face the same timeout
on cold-start. The substrate revealed the operational fact in ~92
seconds rather than via a multi-minute integration smoke that
would have to walk the full webhook → cell → dispatch → portfolio
cascade before producing comparable evidence.

The substrate honors the operational reality: model X is not just
"slower" or "lower-accuracy"; it's outside the production tier
budget entirely. That's a clearly-stated component-quality verdict.

## Stage 3 — Audit chain verification

Six audit events emitted across the three runs (one start + one
terminal-transition per run):

```
2026-05-26 12:04:36.064741+00 | intent_classification_evaluation.run.start    | 1e6f57ac (gpt-4o-mini)
2026-05-26 12:05:51.915441+00 | intent_classification_evaluation.run.complete | 1e6f57ac (gpt-4o-mini)
2026-05-26 12:06:02.669385+00 | intent_classification_evaluation.run.start    | 462ec985 (qwen2.5:7b, failed)
2026-05-26 12:07:34.423902+00 | intent_classification_evaluation.run.fail     | 462ec985 (qwen2.5:7b, failed)
2026-05-26 12:08:19.309851+00 | intent_classification_evaluation.run.start    | 3b3d79f9 (qwen2.5:7b, failed)
2026-05-26 12:09:51.504831+00 | intent_classification_evaluation.run.fail     | 3b3d79f9 (qwen2.5:7b, failed)
```

Each event carries the four-layer model ontology per D132
(`model_provider`, `model_account`, `model_version`) plus the
gold_set_name and started_at in the after_state payload. A
procurement reader can reconstruct exactly what was evaluated,
when, on which model, with what outcome — from the chain alone.

The runner's audit-event emission flows through PostgresAuditAdapter
per D110 commitment 7; the adapter recomputes the chain hashes
inside its locking transaction per D37, so the integrity is
adapter-anchored. Chain verification follows the existing
GENESIS_HASH walker pattern; the six S48b events extend the chain
cleanly with no break_index reported.

## Stage 4 — `eval list` and `eval get` surfaces

`eval list` returns all three runs in newest-first order with
status, model, gold-set name, and started_at. `eval get` returns
the full detail including per-entry result count, per-class
aggregates, and failure_reason when applicable. Both surfaces
exercise the EvaluationRunReader port through
PostgresEvaluationRunReader without going through the cell or any
integration plumbing — the substrate's component-isolation
discipline holds at the read surface too.

## Verdict

**Substrate is operationally viable.** The S48b load-bearing claim
("answer model-choice questions in minutes against a fixed reference
set") delivers: 75 seconds for a 40-entry per-model evaluation
including full audit-chain integration. The methodology-gap the
substrate closes (component-quality questions answered at a
dedicated surface rather than through integration smokes) is now
addressed structurally.

**gpt-4o-mini verdict for Phase 2-A operator dogfooding.** Strong:
97.5% overall accuracy; 100% on AddDataPointIntent including the
four S46 blind-spot phrasings; ~$0.001 per 40-entry evaluation
against the OpenAI account at published `gpt-4o-mini` rates; warm
LLM call lands at ~1-3 s. The S48a swap decision is validated
component-side; the S48a integration smoke ("4/4 phrasings
classified correctly in live cell cascades") and S48b component-
side smoke ("97.5% accuracy on a 40-entry gold set") cite each
other cleanly.

**qwen2.5:7b verdict for Phase 2-A operator dogfooding.** Not
viable at the REAL_TIME_REQUIRED tier on this hardware. Both
evaluation attempts failed at cold-start timeout (~91-92 s vs the
30 s tier budget). Even if the model could complete a single
call, the production cell exercises the same tier budget; the
operator-facing experience would face identical timeouts.

**Substrate methodology evidence.** The component-quality-vs-
integration-smoke discipline now has its first operational instance
in code at S48b. The captures methodology entry plus this smoke
document plus the S46/S47 captures plus D137 together carry the
discipline's promotion-ready evidence base. Promotion to
`charter/methodology.md` activates at the post-S48 hygiene captures
review per the existing promotion convention.

## Stage 5 — Final tenant_a state delta from S48b live exercise

| Table | Pre-S48b | Post-S48b | Delta |
|---|---|---|---|
| intent_class_evaluation_runs | 0 | 3 | +3 (1 completed, 2 failed) |
| intent_class_evaluation_results | 0 | 40 | +40 (all from the gpt-4o-mini run; failed runs had 0 results before timeout) |
| intent_class_evaluation_aggregates | 0 | 4 | +4 (one per intent class, gpt-4o-mini run) |
| tenant_audit | 239 | 245 | +6 (start + terminal per run) |

The audit chain holds at 245 events with single genesis from
2026-05-12; no duplicates, no broken links (verified via the same
audit-chain check the S48a smoke ran).
