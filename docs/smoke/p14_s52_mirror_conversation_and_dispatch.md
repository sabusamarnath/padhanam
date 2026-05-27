# P14 S52 — Three-cell dispatch + mirror-conversation end-to-end smoke

Live-stack smoke walking the S52 substrate end-to-end against tenant_a:

- The MetaClassifier dispatch substrate (D140) at the messaging
  context with the LiteLLM-backed adapter classifying inbounds into
  the three real cells plus the DISPATCH_CLARIFICATION sentinel.
- The `dispatch_inbound` use case orchestrating the five-step flow
  (active-pending check → meta-classification → high-confidence
  dispatch → low-confidence routing to dispatch_clarification).
- PendingClarification's `target_cell` extension (Alembic 0023)
  populated by every cell that creates a pending and consulted at
  active-pending routing.
- The MirrorConversationCell composing the portfolio read-side
  substrate (via the MirrorPortfolioReader consumer port) with
  the intent-classification primitive and the D131/D135/D138
  response composition pattern.
- Message `cell_payload` extension (Alembic 0024) persisting the
  mirror-conversation cell's `current_focus_artefact` for drill-down
  anchor extraction on the next turn per D141.
- Resolution-ambiguity routing for title-ambiguous artefact references
  per D139.
- The WhatsApp render extension for MirrorConversationResponse with
  breadcrumb context for relative intents.
- The mirror-conversation gold set running against the parameterised
  D137 substrate as fourth instance.

**Procedural** — the operator executes the stages below against the
freshly-rebuilt `padhanam-api` image. The build environment cannot
reach docker or the Twilio Sandbox; this document records the
expected outcomes for each stage so the operator can confirm at live
execution.

## Prerequisites (executed at smoke-open)

- `padhanam-api` rebuilt via `make build-api`; new digest pin
  recorded in `compose.yaml` and the container force-recreated:
  `docker compose up -d --force-recreate padhanam-api`.
- Alembic migrations 0023 (`pending_clar_target_cell`) and 0024
  (`message_cell_payload`) applied to both tenant synthetic DBs:
  `docker compose exec padhanam-api alembic -n tenant upgrade head`
  on each tenant container.
- `gpt-4o-mini` pin still active at `REAL_TIME_REQUIRED` tier;
  `OPENAI_API_KEY` in the operator's `.env`. The meta-classifier
  consumes the same StructuredOutputPort per D130 so the same model
  pin governs both meta-classification and cell-internal intent
  extraction.
- tenant_a's audit chain carries accumulated state from S46/S47/S48a
  and the S51 audit-conversation smokes; tenant_a's portfolio
  carries the cases created during those exercises.

## Stage 0 — Baseline state capture

Record the row counts plus chain integrity before the smoke runs:

```bash
docker compose exec padhanam-api python -m padhanam.cli audit-event list \
  --tenant tenant_a --page-size 1
docker compose exec padhanam-api python -m padhanam.cli portfolio list \
  --tenant tenant_a
docker compose exec padhanam-api python -m padhanam.cli messages list \
  --tenant tenant_a --page-size 1
```

Note: intakes count, cases count, data_points count, messages count,
tenant_audit count, and audit chain integrity status. Compare against
end-of-smoke counts.

## Stage 1 — Manual-entry routing (high-confidence dispatch to manual_entry)

Send WhatsApp message shaped for manual_entry:

```
add a goal for the Q3 portfolio review: ship Wave 1 by Friday
```

Expected: the MetaClassifier routes to `manual_entry` at high
confidence (≥0.8). The manual_entry cell runs, creates the data
point against the Q3 review case, and replies with the cited
confirmation. Verify the outbound carries D131 Shape-1 citation
(`ref XXXXXXXX · intake XXXXXXXX · HH:MM UTC`). Verify the message's
`cell_payload` column is NULL (manual_entry does not populate per
D141).

## Stage 2 — Audit-conversation routing (high-confidence dispatch to audit_conversation)

Send WhatsApp message shaped for audit_conversation:

```
show me the audit history for the Q3 portfolio review case
```

Expected: the MetaClassifier routes to `audit_conversation` at high
confidence. The audit-conversation cell runs, classifies the intent
as FindByCase, resolves the case reference, queries the audit chain
via the existing AuditEventReader, and replies with the cited
list of audit events. The outbound carries the audit-conversation
render shape (event list followed by `audit XXXXXXXX · ref XXXXXXXX
· HH:MM UTC` citation line). Verify the message's `cell_payload`
column is NULL.

## Stage 3 — Mirror-conversation routing + cell_payload persistence

Send WhatsApp message shaped for mirror_conversation:

```
show me the Q3 portfolio review
```

Expected: the MetaClassifier routes to `mirror_conversation` at high
confidence. The mirror cell loads the Q3 review case detail and
replies with the case summary plus its data points. The outbound
carries the mirror render shape (case title + data point list +
Shape-1 citation line + `↳ context: case XXXXXXXX` breadcrumb).
Verify the message's `cell_payload` column is non-null and parses
to `{"current_focus_artefact": {"artefact_id": "<case_uuid>",
"artefact_type": "case"}}` — this is D141's first operational
exercise.

## Stage 4 — Drill-down with cell_payload extraction

Send relative-intent follow-up:

```
tell me about ship Wave 1
```

Expected: the MetaClassifier routes to `mirror_conversation` (the
relative-intent heuristic at the rule-based adapter or the LLM-
backed routing using conversation history). The mirror cell loads
the prior outbound's cell_payload, extracts `current_focus_artefact`
as the Q3 review case, classifies the intent as DrillDownToChild,
resolves "ship Wave 1" against the case's data points, and replies
with the matched data point's detail. The outbound's breadcrumb
updates to `↳ context: data point XXXXXXXX`. cell_payload persists
the updated focus on the new outbound.

## Stage 5 — Low-confidence dispatch → dispatch_clarification PendingClarification

Send dispatch-ambiguous inbound:

```
Q3 results
```

Expected: the MetaClassifier returns a low-confidence classification
(below 0.8). The `dispatch_inbound` use case creates a
PendingClarification with `target_cell='dispatch_clarification'`
carrying the original inbound text in `proposed_intent`. The
outbound is the routing prompt:

```
I'm not sure which surface to route this to. Could you say which
you'd like?
  1. Record new portfolio state (manual entry).
  2. Ask about audit history.
  3. View current portfolio state.
(reply with the number, or 'manual', 'audit', or 'mirror').
```

Verify the pending row in `pending_clarifications` carries the
expected `target_cell` value.

## Stage 6 — dispatch_clarification resolution

Reply to the routing prompt:

```
mirror
```

Expected: the `dispatch_inbound` use case finds the active
dispatch_clarification pending, recognises the reply, expires the
pending, and re-runs dispatch with `target_cell=mirror_conversation`
against the *original* inbound text ("Q3 results"). The mirror cell
runs, classifies as ShowCase with `case_reference="Q3"` (probably
falling through to UnclearMirrorIntent if no clean match; verify
the actual classification at live execution), and replies
appropriately. Verify the prior dispatch_clarification pending
status is now EXPIRED in the database.

## Stage 7 — Relative intent with no prior mirror focus

After a cross-cell interlude (Stage 8 below resets context with an
audit query), send a relative-intent inbound with no recent mirror
outbound to anchor against:

```
show the parent of this
```

Expected: the mirror cell loads conversation history, finds no
prior mirror outbound (or finds an audit outbound that doesn't
populate cell_payload with the mirror shape), and the
`extract_focus_from_cell_payload` helper returns None per D141's
implementer-side validation. The cell routes through D139 with a
no-prior-focus clarification:

```
I don't have a child artefact in context — there's no parent to
show. Try showing a data point first.
```

## Stage 8 — Title-ambiguous resolution (D139 routing)

If tenant_a's portfolio carries multiple cases sharing a title
(e.g., the three "Q3 portfolio review" cases accumulated from
S46/S47/S48a), send:

```
show me the Q3 portfolio review
```

Expected: the mirror cell's resolver finds multiple title matches,
creates a PendingClarification (target_cell='mirror_conversation')
with `resolution_candidates` sidecar carrying each candidate's id +
label. The outbound is the numbered candidate list. Verify the
pending row in `pending_clarifications` carries
`target_cell='mirror_conversation'` and the `proposed_intent` carries
the `resolution_candidates` key.

## Stage 9 — Resolution-ambiguity positional reply

Reply with the position:

```
2
```

Expected: the mirror cell finds the active pending, parses the
positional reply, resolves the chosen case id, expires the pending,
and dispatches the original ShowCase against the chosen case. The
outbound is the case detail with breadcrumb context for that
specific case.

## Stage 10 — Cross-cell cell_payload isolation

Send an audit-conversation query that the meta-classifier routes to
`audit_conversation`:

```
audit log for last week
```

Expected: audit-conversation runs. Its outbound has `cell_payload`
NULL (audit-conversation does not populate the column per S52
discipline). Now send another mirror inbound:

```
show me the partnership case
```

Expected: the mirror cell loads conversation history. The most
recent outbound is the audit-conversation reply with cell_payload
NULL; the next-most-recent is the Stage 9 outbound which is a
mirror-conversation case detail with cell_payload populated. The
mirror cell's `_load_prior_mirror_focus` walks back through history
and extracts the focus from the Stage 9 outbound (the audit
outbound's NULL payload is gracefully ignored per D141's
implementer-side validation).

## Stage 11 — Meta-classifier gold-set evaluation

Run the meta-classifier evaluation against the gold set landed at
S52 commit 5:

```bash
docker compose exec padhanam-api python -m padhanam.cli intent-classification-eval \
  eval start --gold-set meta_classifier_p14_s52 --model gpt-4o-mini \
  --tenant tenant_a
```

Expected: the runner classifies each of the 24 entries against the
configured model and records the per-class accuracy. The 20 entries
shaped for a specific cell should classify correctly at >85%; the 4
ambiguous entries should return low confidence (the gold set
captures expected_intent_class as best-guess; the load-bearing
signal is the confidence float, which a future runner-side
threshold check could surface explicitly).

## Stage 12 — Mirror-conversation gold-set evaluation

Run the mirror-conversation evaluation against the gold set landed at
S52 commit 9:

```bash
docker compose exec padhanam-api python -m padhanam.cli intent-classification-eval \
  eval start --gold-set mirror_conversation_p14_s52 --model gpt-4o-mini \
  --tenant tenant_a
```

Expected: the runner classifies each of the 30 entries; absolute
intents should classify at >90% accuracy. Relative-intent entries
(drill_down_to_child, show_parent, show_siblings) carry
`prior_turns` metadata that the current runner does not yet consume
(the substrate measures the classifier's single-turn behaviour
against the input phrasing alone); the absolute-vs-relative
classification accuracy on these entries is the operational signal
for whether paired-turn context becomes worth a runner extension at
a future commit.

## Stage 13 — Audit chain integrity + final state capture

Run the audit-chain integrity check at smoke close:

```bash
docker compose exec padhanam-api python -m padhanam.cli audit-event list \
  --tenant tenant_a --page-size 1
```

Verify `chain_integrity.status == "verified"`. Capture the same
counts as Stage 0 and compute the deltas:

- intakes: +N (one per WhatsApp inbound across stages 1-10)
- messages: +N×2 roughly (inbound + outbound per stage; clarifications
  add one extra outbound)
- cases / data_points: +small (Stage 1 adds a data point against
  the Q3 review case; other stages are read-only)
- tenant_audit: +many (every messaging + portfolio + pending
  lifecycle event chains in)

**Smoke close**: the three-cell dispatch routes inbounds correctly
to manual_entry, audit_conversation, and mirror_conversation; the
PendingClarification target_cell field routes confirming and
resolution-ambiguity replies to the correct cell; the cell_payload
column persists mirror-conversation's current_focus_artefact for
drill-down extraction on the next turn; the D139 resolution-
ambiguity routing fires structurally at all three implementers per
the contract harness conformance scenarios; the gold-set
evaluations record component-quality signals for the meta-classifier
and the mirror-conversation classifier. **P14 closes the bet's
read-loop substrate.**
