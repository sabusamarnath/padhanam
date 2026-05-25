# P13 S47 — UX convergence substrate live-stack smoke

Live-stack smoke walking the S47 substrate end-to-end against
tenant_a: the dispatch-port webhook contract, the manual entry
cell's three-case confidence-aware decision logic per D134, the
PendingClarification multi-turn cascade (medium-confidence
classification → PendingClarification persists → operator
confirmation resolves the pending → orchestration executes → cited
confirmation reply renders), the WhatsApp shape-aware-clarification
rendering for Case 2, and the REAL_TIME_REQUIRED model bump to
`qwen2.5:14b` per D133.

This smoke doc is **procedural** — the build environment cannot
reach docker or the Twilio Sandbox. The operator executes the stages
live and the smoke document carries the executed-evidence
annotations the operator records back into this file under each
stage's "evidence" line.

## Prerequisites

- `padhanam-api` image freshly rebuilt and pinned via `make build-api`
  + `make compose-pin-api`; record the new digest at the close of
  this smoke.
- Alembic migrations `0019_messaging_substrate` (S45),
  `0020_intake_source_whatsapp` (S45), and `0021_pending_clarification`
  (S47) applied to both tenant data planes.
- `qwen2.5:14b` pulled in the local Ollama instance:
  `docker exec padhanam-ollama-1 ollama pull qwen2.5:14b`.
- Twilio Sandbox for WhatsApp opted-in for the operator's WhatsApp
  number; ngrok tunnel pointed at the local API; webhook URL set in
  the Twilio Console.
- `INFERENCE_REAL_TIME_REQUIRED_MODEL` left unset (defaults to
  `qwen2.5:14b` per S47) or explicitly set to the operator-validated
  pin.

## Stage 0 — baseline state

Capture tenant_a state before the smoke runs.

```bash
docker exec padhanam-tenant-a-postgres-1 psql -U postgres -d tenant_a -c "
  SELECT 'intakes' AS t, count(*) FROM intakes
  UNION ALL SELECT 'cases', count(*) FROM cases
  UNION ALL SELECT 'data_points', count(*) FROM data_points
  UNION ALL SELECT 'assertions', count(*) FROM assertions
  UNION ALL SELECT 'messages', count(*) FROM messages
  UNION ALL SELECT 'pending_clarifications', count(*) FROM pending_clarifications
  UNION ALL SELECT 'tenant_audit', count(*) FROM tenant_audit;
"
```

Evidence: _baseline counts pasted at execution time_

## Stage 1 — regression: high-confidence CreateCaseIntent

Send a single high-confidence CreateCase from the operator's
WhatsApp number through the Sandbox. Verify the existing S46-shape
behaviour still works under the new dispatch-port webhook handler
and the bumped model pin.

**Operator message:**
> Start a case for the Q3 portfolio review.

Expected:
- Webhook returns 200 within ~200ms (dispatch port returns promptly
  via `asyncio.create_task`; the cell completes asynchronously).
- Cell extracts `create_case` intent at high confidence (≥ 0.8).
- The portfolio orchestration creates a new Case.
- Outbound reply renders: `Recorded a new case: Q3 portfolio
  review.\n\n— ref XXXXXXXX · intake YYYYYYYY · HH:MM UTC`.
- D131 citation contract holds.

Evidence: _ngrok status code + outbound text + new case id pasted_

## Stage 2 — medium-confidence cascade with confirmation

Send a phrasing the model classifies at medium confidence (between
0.5 and 0.8). The exact phrasing depends on `qwen2.5:14b`'s
calibration — the operator picks a phrasing the model finds
borderline. Suggestions:

- `Maybe add a goal to the Q3 portfolio review — ship Wave 1?`
- `Goal for Q3 portfolio review — ship Wave 1.`

Expected on the first message:
- Webhook returns 200 promptly.
- Cell classifies at medium confidence.
- WhatsApp reply renders the shape-aware clarification:
  `I think you want to add a goal to <ref>: ship Wave 1. Is that
  right? (yes / no)`.
- PendingClarification row appears in `pending_clarifications` with
  status `PENDING`, scoped to the webhook tenant and the
  `twilio-webhook` actor_id.
- One `messaging.pending_clarification.create` audit event lands in
  `tenant_audit`.
- No `data_points` row created (Case 2 does not write to the
  portfolio).

**Operator follow-up:**
> yes

Expected:
- Cell detects the active PendingClarification at turn-open and the
  confirming reply.
- One `messaging.pending_clarification.resolve` audit event with
  `resolution: confirmed`.
- The proposed orchestration runs: a new DataPoint appears under the
  Case.
- WhatsApp reply renders the Case-1-style cited confirmation:
  `Added a goal to <Case title>: ship Wave 1.\n\n— ref ... · intake ...`.
- The PendingClarification transitions to `RESOLVED` with
  `resolved_at` populated.

Evidence: _outbound texts, pending_clarifications row, audit verbs,
data_point id pasted_

## Stage 3 — medium-confidence cascade with cancellation

Send another medium-confidence phrasing, then correct it.

**Operator message:** (a borderline phrasing)

**Operator follow-up:**
> no

Expected:
- PendingClarification persists from the first message (as in
  Stage 2).
- The correcting reply resolves the pending as cancelled
  (`messaging.pending_clarification.resolve` with `resolution:
  cancelled`).
- The cell falls through to fresh-turn handling on the correcting
  inbound; since `no` has low confidence at any phrasing, the cell
  emits the generic UnclearIntent clarification.
- No portfolio write executes; the data_point count for Stage 3
  remains unchanged.

Evidence: _audit-verb sequence, pending status pasted_

## Stage 4 — low-confidence / parse-failure cascade

Send a message that classifies at low confidence (below 0.5) or that
the model produces unparseable output for.

**Operator message:**
> do the thing

Expected:
- Cell classifies at low confidence or `StructuredOutputParseFailure`
  fires.
- WhatsApp reply renders the generic UnclearIntent text: `I could
  not tell what you would like me to do. Could you say a little
  more?`.
- No PendingClarification row created.
- No portfolio write.

Evidence: _outbound text + absence-of-write pasted_

## Stage 5 — webhook contract verification

Inspect ngrok for the response codes and timing across all four
stages above.

Expected: all webhook calls return `200` within a small budget
(target: under one second from request receipt to response on the
happy path, independent of LLM latency). The cell completes
asynchronously in the background; the dispatch port unhitched the
webhook from the LLM call chain.

Evidence: _ngrok request log entries pasted_

## Stage 6 — D122/D132 trace attributes plus cost capture

Open Langfuse at the LLM call observation for one stage-1 turn.
Verify:

- `gen_ai.model.provider` = `ollama`
- `gen_ai.model.account` = `default`
- `gen_ai.model.version` = `qwen2.5:14b` (S47 pin)
- `gen_ai.model.configuration` contains `latency_tier=real_time_required;temperature=0.0;structured_output_schema=present`
- Scope `padhanam.inference.litellm`
- Token counts + cost (zero for local Ollama; D41 pricing table)

Evidence: _Langfuse observation attribute pasted_

## Stage 7 — audit chain integrity end-to-end

Run the chain-verification query across all S47 audit additions.

```bash
docker exec padhanam-tenant-a-postgres-1 psql -U postgres -d tenant_a -c "
  SELECT count(*) AS events,
         count(*) FILTER (WHERE previous_event_hash IS NULL) AS genesis_entries,
         count(DISTINCT this_event_hash) AS distinct_hashes,
         count(*) - count(DISTINCT this_event_hash) AS duplicate_hashes
    FROM tenant_audit;
"
```

Expected: `genesis_entries = 1`, `duplicate_hashes = 0`,
`distinct_hashes = events`. List the new
`messaging.pending_clarification.*` verbs to confirm lifecycle audit
events landed.

```bash
docker exec padhanam-tenant-a-postgres-1 psql -U postgres -d tenant_a -c "
  SELECT action_verb, count(*)
    FROM tenant_audit
   WHERE action_verb LIKE 'messaging.pending_clarification.%'
   GROUP BY 1 ORDER BY 1;
"
```

Evidence: _chain-integrity counts + verb breakdown pasted_

## Stage 8 — final state delta

Re-run the baseline query from Stage 0 and compute the delta.

Expected from the four stages above:
- intakes: at least +4 (one per inbound message)
- cases: +1 (Stage 1's Case)
- data_points: +1 (Stage 2's confirmed DataPoint)
- messages: +8 (four inbound + four outbound replies)
- pending_clarifications: +2 (Stage 2 resolved; Stage 3 cancelled)
- tenant_audit: at least +12 (Case create + DataPoint create + two
  pending.create + two pending.resolve + outbound messages + inbound
  messages)

Evidence: _final delta pasted_

## Close

Record at session-log:
- final container digest pin
- per-stage evidence summary
- any structural-honesty findings that surfaced (capture into
  `log/captures.md` rather than fix in-session if they fall outside
  S47's scope)
- the operator-validated REAL_TIME_REQUIRED model pin (whether the
  S47 default `qwen2.5:14b` held or the operator overrode to a
  hosted alternative)
