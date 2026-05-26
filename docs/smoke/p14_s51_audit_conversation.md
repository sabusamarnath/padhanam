# P14 S51 — Audit-conversation cell + CitedResponse Protocol smoke

Live-stack smoke walking the S51 substrate end-to-end against tenant_a:
the CitedResponse Protocol at shared_kernel; the AuditConversationCell
consuming the existing AuditEventReader (S36) and the audit-classification
primitive at shared_kernel/intent_classification_audit.py; resolution-
ambiguity routing through D139 PendingClarification with the
heterogeneous-citations shape per Finding 4; the contract harness
extensions; and the audit-conversation gold-set evaluation against
the D137 substrate.

**Procedural** — the operator executes the stages below against the
freshly-rebuilt `padhanam-api` image. Per pre-write reconciliation
Finding 5 (S51 build, option c), the inbound webhook is **not** wired to
route to the audit-conversation cell at S51; the dispatch decision
defers to S52 framing. The smoke exercises the cell directly through a
helper script that constructs the cell with live ports and drives
``open`` / ``turn`` / ``close``. The Twilio webhook continues to dispatch
to manual_entry_cell unchanged; no regression to S47/S50.

## Prerequisites (executed at smoke-open)

- `padhanam-api` rebuilt via `make build-api`; new digest pin recorded
  in `compose.yaml` and the container force-recreated:
  `docker compose up -d --force-recreate padhanam-api`.
- No Alembic migration required at S51 — the audit-conversation cell
  consumes the existing AuditEventReader (S36) with no new tables.
- `gpt-4o-mini` pin still active at REAL_TIME_REQUIRED tier
  (`INFERENCE_REAL_TIME_REQUIRED_MODEL=gpt-4o-mini`, verified in
  `padhanam/config/inference.py`); `OPENAI_API_KEY` in the operator's
  `.env`.
- tenant_a's audit chain already carries 165+ events from S46/S47/S48a
  smokes plus a healthy mix of case and data-point references; S51
  exercises queries against that accumulated state.

## Stage 0 — Baseline state capture

Record the audit-chain row count and verify chain integrity before
running queries:

```bash
docker compose exec padhanam-api python -m padhanam.cli audit-event list \
  --tenant tenant_a --page-size 1
```

Confirm chain-integrity status is `"verified"`. Note the total row
count for end-of-smoke comparison.

## Stage 1 — Cell construction + ConversationFlow protocol conformance

Run the harness invocation that constructs the AuditConversationCell
with live ports (LiteLLM gateway, AuditEventReader Postgres adapter,
PortfolioCaseLookup adapter, ConfidenceCalculator, ThresholdResolver,
PendingClarificationReader+Repository, AuditPort):

```bash
docker compose exec padhanam-api python -m padhanam.cli audit-conversation \
  smoke-run --tenant tenant_a --input "show audit events for today"
```

Verify:
- `isinstance(cell, ConversationFlow)` returns True at construction.
- `open` returns a ConversationState with turn_count=0 and is_open=True.

## Stage 2 — FindByDateRange (high-confidence)

Send the input `"show audit events for today"`. Verify:

- Intent extracted: `FindByDateRange(range_keyword="today")`.
- Confidence band: `"high"`.
- AuditEventReader called with filters whose `timestamp_range` covers
  today 00:00 UTC → now.
- AuditConversationResponse returned with non-empty `cited_audit_events`
  (matching the audit events surfaced in the page).
- `cited_artefacts` carries heterogeneous citations (Case + DataPoint)
  per the symmetric-with-mirror shape per Finding 4.
- `isinstance(response, CitedResponse)` returns True.
- WhatsApp render at `render_for_whatsapp` produces Shape-1 citation
  line: `— audit XXXXXXXX · ref YYYYYYYY · HH:MM UTC`.

## Stage 3 — FindByActor (high-confidence)

Send the input `"what has operator done"`. Verify:

- Intent extracted: `FindByActor(actor="operator")`.
- AuditEventReader filters carry `actor="operator"`.
- Response cites every event surfaced; `cited_artefacts` heterogeneous
  per the resource_type discriminator on each event.

## Stage 4 — FindByEventType (high-confidence)

Send the input `"show me all case creations"`. Verify:

- Intent extracted: `FindByEventType(event_type="portfolio.case.create")`
  (or an equivalent action_verb the gpt-4o-mini classification yields).
- AuditEventReader filters carry `action_verbs=("portfolio.case.create",)`.

## Stage 5 — FindByCombination (high-confidence, multiple filters)

Send the input `"show alice's case creations from this week"`. Verify:

- Intent extracted: `FindByCombination(actor="alice", event_type="...",
  range_keyword="this_week")`.
- AuditEventReader filters carry the combined values.

## Stage 6 — Resolution-ambiguity routing (D139)

tenant_a carries multiple "Q3 portfolio review" cases from prior
smokes. Send the input `"show audit for the Q3 portfolio review"`.
Verify:

- Intent extracted: `FindByCase(case_reference="Q3 portfolio review")`.
- PortfolioCaseLookup returns multiple cases sharing the title.
- Cell routes through D139 PendingClarification:
  - PendingClarification persisted with `proposed_intent` carrying the
    classified intent fields plus `resolution_candidates` sidecar.
  - Confidence band: `"resolution_ambiguous"`.
  - Response text carries the numbered candidate list.
  - `cited_artefacts` carries one ArtefactCitation per candidate with
    `artefact_type="case"`.
  - WhatsApp render shows the numbered list plus the citation line.

## Stage 7 — Resolution-ambiguity positional selection

With the active PendingClarification from Stage 6, send the input `"1"`
(or another valid integer in range). Verify:

- Cell detects positional selection via the `resolution_candidates`
  sidecar.
- PendingClarification transitions PENDING → RESOLVED.
- The cell re-executes the audit query against the chosen case_id.
- Response cites the audit events for the resolved Case.

## Stage 8 — Medium-confidence path (PendingClarification creation)

Trigger a medium-confidence classification (the operator can craft a
deliberately-ambiguous phrasing like `"audit"`). Verify:

- Confidence band: `"medium"`.
- PendingClarification persisted with the medium-confidence proposed
  intent.
- Response text phrased as a question proposing the specific query.

## Stage 9 — Medium-confidence confirmation

Reply `"yes"` to the medium-confidence pending. Verify:

- PendingClarification transitions PENDING → RESOLVED.
- Cell re-executes the proposed query.
- Response carries citations for the executed query.

## Stage 10 — Audit-conversation gold-set evaluation (D137 substrate)

Run the gold-set evaluation against the audit-conversation fixture:

```bash
docker compose exec padhanam-api python -m padhanam.cli intent-classification-eval \
  start --tenant tenant_a \
  --gold-set audit_conversation_p14_s51 \
  --model gpt-4o-mini
```

Verify:

- The runner picks the audit-conversation `(prompt_builder, schema,
  result_key)` primitive per the S51 parameterisation.
- The 24-entry gold set evaluates against gpt-4o-mini.
- Per-class accuracy recorded; aggregate metrics persisted; audit
  events emitted for the run start + completion.
- Operator reviews the classification accuracy per intent class;
  ambiguity observations (entries where the model's classification
  diverges from the gold's expectation in a structurally-defensible
  way) noted at the session-log methodology line per the S48b
  reflection-2 recurrence test.

## Stage 11 — Audit-chain integrity post-smoke

Re-run the audit chain integrity check:

```bash
docker compose exec padhanam-api python -m padhanam.cli audit-event list \
  --tenant tenant_a --page-size 1
```

Verify:

- Total row count increased by the expected number of S51 events:
  - PendingClarification create + resolve + expire (per stage).
  - Evaluation run start + complete (Stage 10).
- Chain integrity status remains `"verified"`.
- No duplicate hashes; no broken links.

## Smoke close

At smoke close the operator records:

- Per-stage executed-evidence summary (each stage green / yellow with
  caveat / red with finding).
- Any structural-honesty findings surfaced during execution (the S48a
  smoke-driven captures cadence).
- Total audit-chain event delta from baseline.
- Gold-set evaluation summary (accuracy per intent class, parse
  failures, ambiguity observations).
- Forward dispositions: each finding routes to either a same-session
  fix, a captures entry, or a deferred-decisions entry per the
  Phase 2-A operator-dogfooding rhythm.

The procedural smoke is the load-bearing evidence at S51 close that the
substrate works against live state. The contract harness scenarios
(commit 5) verify structural conformance; the procedural smoke verifies
end-to-end behaviour against real LLM classification, real Postgres
queries, real audit-chain integrity, and real PendingClarification
lifecycle.
