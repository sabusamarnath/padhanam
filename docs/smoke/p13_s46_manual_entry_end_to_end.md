# P13 S46 — Manual entry cell end-to-end live-stack smoke

Live-stack smoke for the S46 manual entry cell — the first
ConversationFlow implementer (D115) — exercising the
operator-WhatsApp-to-portfolio-state cascade against tenant_a:
inbound WhatsApp message → intent extraction via structured output
→ target resolution → intake-canonical portfolio orchestration →
cited confirmation rendered back to the operator's WhatsApp. Also
exercises the D122 latency-tier routing and the D132 four-layer
model ontology: every LLM call carries a `latency_tier` and the
adapter span captures the four `gen_ai.model.*` dimensions.

Executed 2026-05-22 against the S46-close code at commits
a49a34a…cf7633f, on the rebuilt `padhanam-api` image (digest
`sha256:523e9419…`, pin advanced from S45's `sha256:77ad47bf…`).
Two CreateCaseIntent cascades verified end-to-end (stages 1 and
8e-i); seven AddDataPointIntent attempts across four phrasings all
classified to UnclearIntent. Two structural-honesty findings
surfaced and were captured at `log/captures.md` rather than fixed
in-session: the synchronous-LLM-vs-Twilio-webhook-timeout finding
(with cold-vs-warm latency dynamic) and the intent-extraction
reliability finding at REAL_TIME_REQUIRED with `qwen2.5:7b`.

S46 ships **no Alembic migration** — the cell, the intent value
objects, the four-layer ontology, and the latency-tier routing are
all code. The cell writes through the existing `cases`,
`data_points`, `assertions`, `intakes`, and `messages` tables;
migrations `0019`/`0020` from S45 are already applied to both tenant
planes.

## Stage 0 — image rebuild and webhook tunnel

`make build-api` rebuilt the `padhanam-api` image to carry S46 code;
the `compose.yaml` digest pin advanced from `sha256:77ad47bf…` to
`sha256:523e9419…`. The container started clean ("Application
startup complete", no errors); `MessagingSettings` and
`InferenceSettings` both resolved (verified by exercising the full
dependency chain at the reachability curl below); the four
messaging routes registered.

The webhook tunnel: the loopback-only `127.0.0.1:8000:8000` binding
from S45 (commit 7af8e88) plus
`ngrok http --url=easeful-front-quote.ngrok-free.dev 8000`. The
ngrok free-tier static domain made `.env`'s `WEBHOOK_URL` stable
across S45 and S46 with no edits needed; the Twilio Console
"When a message comes in" required setting at S46 start (had not
persisted from S45). Once set: reachability curl through the tunnel
to `POST .../api/v1/messaging/inbound` with no signature → **403
`webhook_signature_invalid`** (S45's reachability gate held).

`MESSAGING_ADAPTER=twilio`; the operator's number remained joined to
the Twilio Sandbox (same-day as S45 smoke, no 72h lapse).

**Baseline tenant_a state at smoke open**: intakes 6, cases 4,
data_points 3, assertions 6, messages 3, tenant_audit 134.

## Stage 1 — operator sends a create-case message

The operator sent from their joined WhatsApp number:

> Start a case for the Q3 portfolio review.

at 2026-05-22 21:45 UTC.

## Stage 2 — the webhook records the inbound (intake-canonical)

The webhook verified the `X-Twilio-Signature`, then
`record_intake_and_record_inbound_message` recorded:

```
IntakeRecord acc60e9b
  intake_source=WHATSAPP_INBOUND  authored_by_user_id=twilio-webhook
  payload.raw_text="Start a case for the Q3 portfolio review."
  created_at=2026-05-22 21:45:28.711+00

Message 28dff3c1
  direction=INBOUND  channel=WHATSAPP  status=RECEIVED
  intake_id=acc60e9b
  external_id=SM33b0fbd8a2510a8e1afd300e8e310b71
  created_at=2026-05-22 21:45:28.794+00

audit: intake.record.create (intake) + messaging.message.receive (message)
```

D128's intake-canonical commitment held across the cross-context
cascade (third-instance evidence after S44b portfolio writes and S45
stage 4 messaging-substrate inbound).

## Stage 3 — the cell extracts CreateCaseIntent

The webhook built `ManualEntryCell` and ran `open` / `turn` /
`close`. `turn` called `StructuredOutputPort.generate_structured`
with `latency_tier=REAL_TIME_REQUIRED`. The Langfuse trace span
verified all D122/D132 attributes (observation `6c340b7d2b6a4f66`):

```
name: structured_output qwen2.5:7b
type: GENERATION  scope: padhanam.inference.litellm
duration: 23.152s (cold start)
input_tokens: 160  output_tokens: 62
metadata.attributes:
  gen_ai.operation.name      = structured_output
  gen_ai.system              = litellm
  gen_ai.request.model       = qwen2.5:7b
  gen_ai.model.provider      = ollama            ← D132 layer 1
  gen_ai.model.account       = default           ← D132 layer 2
  gen_ai.model.version       = qwen2.5:7b        ← D132 layer 3
  gen_ai.model.configuration = latency_tier=real_time_required;temperature=0.0;structured_output_schema=present   ← D132 layer 4, carries D122 tier
```

All four `gen_ai.model.*` dimensions present (D132); the
configuration dimension carries the latency tier verbatim (D122).
The model parsed to `CreateCaseIntent(title="Q3 portfolio review")`
— cleanly stripped the leading "the".

**As-built note (carried from procedural draft).** The framing
brief's stage 3 expected target resolution to run and return
`no_match` for a new case. The as-built cell does *not* resolve for
CreateCaseIntent — a new case has no existing target — so the cell
creates directly. Resolution is reserved for AddDataPointIntent and
ReviseDataPointIntent; those paths did not exercise in this smoke
(see Stage 8).

## Stage 4 — the cell drives record_intake_and_create_case

`PortfolioGateway.create_case` routed via `PortfolioGatewayAdapter`
to `record_intake_and_create_case`. Recorded:

```
IntakeRecord 85622595
  intake_source=MANUAL_ENTRY  authored_by_user_id=twilio-webhook
  created_at=2026-05-22 21:45:51.951+00

Case fa6401b0
  title="Q3 portfolio review"  case_type=PORTFOLIO_ITEM  status=OPEN
  intake_id=85622595
  created_at=2026-05-22 21:45:51.981+00

audit: intake.record.create + portfolio.case.create
```

The two IntakeRecords for one inbound message — `acc60e9b`
(WHATSAPP_INBOUND, "a message arrived") and `85622595`
(MANUAL_ENTRY, "a case was created") — held structurally honest
without operator-facing confusion at the citation surface
(Stage 6).

## Stage 5 — the cell composed the cited response

`CellResponse` carrying:

- `cited_intake_records`: `[85622595]` (the MANUAL_ENTRY IntakeRecord)
- `cited_artefacts`: `[fa6401b0]` (the Case)
- `cited_audit_events`: `[]` (empty per the D131-first-instance gap
  captured at `log/captures.md` 2026-05-22 [S46] entry)

## Stage 6 — outbound WhatsApp reply with compact citations

Rendered reply, sent via `send_message`:

```
Message b9c417f1
  direction=OUTBOUND  channel=WHATSAPP  status=QUEUED (Twilio: read)
  external_id=SM394ee3992b9bf94f4bc279baa2af7000
  intake_id=null  actor=twilio-webhook
  body:
    Recorded a new case: Q3 portfolio review.

    — ref fa6401b0 · intake 85622595 · 21:45 UTC

audit: messaging.message.send
```

D131 Shape 1: short-hex prefix per cited Case and IntakeRecord plus
the composition timestamp. The 8-character prefixes match the
persisted IDs exactly.

## Stage 7 — operator receipt and citation legibility

Twilio reported the outbound message status `read` at 21:45:52 UTC.
The full create-case cascade (Twilio POST receipt → outbound message
persisted) measured **23.67 seconds end-to-end** against tenant_a —
the LLM call dominates at 22.95s cold. ngrok recorded webhook
`status 0` (Twilio's ~15s timeout fired before the webhook
responded); the outbound delivered out-of-band via the separate
Twilio REST API call (the synchronous-LLM-vs-webhook-timeout finding
captured at `log/captures.md`).

## Stage 8 — ambiguity, clarification, and failure scenarios

The procedural plan named five scenarios: add-data-point,
revise-data-point, ambiguous, unclear-intent, no-match. The executed
smoke exercised what the cell's intent-extraction at
REAL_TIME_REQUIRED could reach: an attempt at AddDataPointIntent
(8a), three structural rephrasings to test phrasing-sensitivity
(each sent twice), and a second CreateCase to confirm the positive
path holds with a similar-named existing case (8e-i). The remaining
procedural scenarios (8b revise, 8c original unclear-intent test, 8d
no-match, 8e-ii ambiguous) all gate on AddDataPointIntent
classification first; none became reachable.

### 8a — AddDataPointIntent attempt (smoke document's own template phrasing)

Operator sent:

> Add a goal to the Q3 review: ship Wave 1 by end of May

(Note: typed `add` lowercase; Twilio/iOS delivered `Add` —
auto-capitalisation. Doesn't change classification but worth noting
the delivered text isn't always the typed text.) Result:

```
IntakeRecord 071ebcee  WHATSAPP_INBOUND  created_at 22:02:46.605+00
Message      17db88cb  INBOUND   SM42aed8e4019996add28a938be3b7075c

LLM call: 21.12s (cold)
Cell classification: UnclearIntent
No portfolio write, no MANUAL_ENTRY intake, no citation line.

Message fd82a405  OUTBOUND  status=QUEUED
  external_id=SM5d63c11c3b2c77a1187828f8916351bb
  body: "I could not tell what you would like me to do.
         You can ask me to create a case, add a goal or status
         to a case, or revise an existing data point."

audit: intake.record.create + messaging.message.receive + messaging.message.send (3 events; no MANUAL_ENTRY, no case)
```

The cell's behaviour was contract-correct (UnclearIntent triggers
clarification, no write, no citation line). The failure is upstream
at intent classification — captured at `log/captures.md` as the
intent-extraction-reliability-at-REAL_TIME_REQUIRED-with-qwen2.5:7b
finding.

### 8a-rephrasings — three structural variants, each sent twice

To test whether the AddDataPoint failure was phrasing-sensitive
(model coaxable) or class-systematic (model blind across the
discriminated union variant), the operator sent three rephrasings
exercising distinct surface-cue patterns. Each sent twice (rounds at
~22:07 and ~22:20 UTC):

1. **Verb-first with full title** —
   `Add this goal to the Q3 portfolio review: ship Wave 1 by end of May.`
   → UnclearIntent (both runs)
2. **Target front-loaded** —
   `For the Q3 portfolio review case, add a goal: ship Wave 1 by end of May.`
   → UnclearIntent (both runs)
3. **No verb, noun-phrase opener** —
   `Goal for Q3 portfolio review — ship Wave 1 by end of May.`
   → UnclearIntent (both runs)

Six cascades total; all six produced byte-identical UnclearIntent
clarifications (same body as 8a). Phrasing-sensitivity empirically
falsified at this surface; intent-class blindness on AddDataPoint at
`qwen2.5:7b` / REAL_TIME_REQUIRED is the surviving claim.

### 8e-i — CreateCase against similar-named existing case (positive path)

To confirm CreateCase classification still holds when a similar-
named case already exists, operator sent:

> Start a case for the Q3 budget review.

```
IntakeRecord 583c7c36  MANUAL_ENTRY
Case 4fac3ae0  title="Q3 budget review"  case_type=PORTFOLIO_ITEM  status=OPEN
  intake_id=583c7c36

Message fc3c4dce  OUTBOUND  status=QUEUED (Twilio: delivered)
  body:
    Recorded a new case: Q3 budget review.

    — ref 4fac3ae0 · intake 583c7c36 · 22:30 UTC

LLM call: 20.97s (cold; ~9 min idle had unloaded the model)
audit: 5 events (intake.record.create × 2, messaging.message.receive, portfolio.case.create, messaging.message.send)
```

The model correctly disambiguated "Q3 budget review" from the
existing "Q3 portfolio review" — no conflation, no resolution
involved (CreateCase doesn't resolve), the new case created cleanly.

### Procedural scenarios that did not exercise

- **8b (revise data point)**: depends on 8a having created the
  "Wave 1" goal — never created. Not exercised.
- **8c (deliberate unclear-intent test)**: would have sent a
  message with no actionable intent; the UnclearIntent path is
  already evidenced seven times via 8a + the six rephrasing runs.
  Not exercised separately.
- **8d (no-match)**: requires AddDataPointIntent classification
  first; classification doesn't reach AddDataPoint. Not exercised.
- **8e-ii (ambiguous match)**: same gating problem; the two Q3
  cases now exist but no AddDataPoint phrasing would have
  classified. Not exercised.

## Verification checklist

- [x] Inbound message records one `WHATSAPP_INBOUND` IntakeRecord
      plus one INBOUND Message (intake-canonical) — stages 1 and
      8e-i confirm.
- [x] The cell extracts the correct intent via structured output at
      the REAL_TIME_REQUIRED tier — for CreateCaseIntent (stages 1,
      8e-i). **Failed for AddDataPointIntent across 4 phrasings / 7
      runs (8a + rephrasings); see `log/captures.md`.**
- [x] CreateCaseIntent creates directly (no resolution);
      Add/ReviseDataPointIntent resolve their reference first —
      CreateCaseIntent confirmed; Add/Revise paths did not reach
      because intent classification did not produce them.
- [x] A successful write records a `MANUAL_ENTRY` IntakeRecord plus
      the Case / DataPoint, with audit events — confirmed at stages
      4 and 8e-i.
- [x] The outbound reply carries D131 compact citations
      (short-hex-prefix-plus-timestamp); a clarification carries
      none — confirmed across all 9 outbound replies (2 cited; 7
      clarification with no citation line).
- [x] Every LLM-call span carries the four `gen_ai.model.*`
      dimensions (D132); the configuration dimension carries the
      latency tier (D122) — verified on the stage-1 trace.
- [x] An invalid `X-Twilio-Signature` is rejected 403 with no
      writes — confirmed at stage-0 reachability curl.
- [x] The audit chain holds — **165 events post-smoke, exactly 1
      chain entry point (genesis), 165 distinct `this_event_hash`
      values (zero duplicates), 0 broken links**. The 31 cascade
      audit events from 9 cascades chain in (stage 1: 5; 8a: 3;
      6 rephrasings: 18; 8e-i: 5).

## Latency-tier observations

The cell's only LLM call is the `REAL_TIME_REQUIRED` intent-
extraction structured generation; no `ASYNC_TOLERANT` call fires on
the cell path.

Cold-vs-warm latency dynamic (`qwen2.5:7b` on local Ollama, default
5-min keep-alive):

| Run | LLM latency | Cold / warm | ngrok status |
|---|---|---|---|
| Stage 1 (fresh container) | 22.95s | cold | 0 |
| Stage 8a (~17 min later) | 21.12s | cold | 0 |
| Round-1 rephrasings (×3, 22:07) | not captured | mixed (all under 15s; first probably cold, rest warm) | 200, 200, 200 |
| Round-2 rephrase 1 (~13 min idle) | 18.62s | cold | 0 |
| Round-2 rephrase 2 (35s later) | 9.07s | warm | 200 |
| Round-2 rephrase 3 (18s later) | 8.05s | warm | 200 |
| Stage 8e-i (~9 min idle) | 20.97s | cold | 0 |

Cold: 18–23s, exceeds Twilio's ~15s webhook timeout (ngrok records
`status 0`, webhook completes server-side). Warm: 8–9s, well within
timeout. The webhook-contract violation captured at
`log/captures.md` incorporates this datum; the synchronous-cell-in-
webhook shape is wrong on contract grounds independent of which side
of the timeout a given run falls.

For reference: S45's 97ms inbound-only cascade measured
`record_intake_and_record_inbound_message` only; S46's cascade adds
the structured-output LLM call plus the cell's downstream
orchestration plus the outbound send.

## Supplemental convergence-session-relevant observations

Three observations beyond the stage-by-stage cascade outcomes,
gathered for the convergence session's confidence-aware response
composition framing.

### Intent-extraction quality per phrasing pattern

The bet's messaging-first delivery path rests on operator natural-
language input mapping reliably to the cell's intent union at
REAL_TIME_REQUIRED. The smoke produced direct evidence on this:

- **CreateCaseIntent (2/2 runs)**: reliable. Template phrasing
  ("Start a case for X") classified cleanly; correctly disambiguated
  similar-named existing case at 8e-i.
- **AddDataPointIntent (0/7 runs)**: not reliable. Four distinct
  phrasings (the smoke doc's own template plus three structural
  variants) all classified to UnclearIntent.
- **ReviseDataPointIntent**: not reached (gating on AddDataPoint).
- **UnclearIntent**: evidenced seven times via misclassified
  AddDataPoint inputs rather than via a deliberate unclear-intent
  test; the clarification-text content was consistent and
  contract-correct.

The convergence session's confidence-aware composition framing has
to account for systematic misclassification across the discriminated
union, not only within-class uncertainty. See the intent-extraction
reliability captures.md entry for the full architectural disposition.

### Resolution behavior with real natural-language

The framing-time settled on pure significant-token-overlap matching
for `resolve_target` as a deliberately-simple shape. Because
AddDataPointIntent never classified at REAL_TIME_REQUIRED +
`qwen2.5:7b`, the resolution surface itself was not exercised
against real operator inputs in this smoke. CreateCaseIntent does
not invoke resolution (new cases have no existing target). The
resolution-behavior evidence question remains open until intent
extraction is unblocked or a non-WhatsApp surface exercises the
Add/Revise paths.

### Citation legibility at the WhatsApp surface

D131 Shape 1 — compact textual citations as
`— ref <hex8> · intake <hex8> · HH:MM UTC` — rendered in two
outbound replies (stages 1 and 8e-i). Operator-facing legibility:
the citation line sat below a blank line beneath the confirmation
prose, scanned as a single short line. Whether operators find the
citations useful, intrusive, or ignorable is convergence-session-
relevant; the smoke surface confirms the rendering shape but does
not stress operator preference at any volume. The clarification-
path replies (8a + rephrasings) carried no citation line — D131
contract held in all seven cases.

## Findings captured

Two structural-honesty findings landed at `log/captures.md` rather
than being fixed in-session:

1. **Webhook synchronous-cell-run-vs-Twilio-timeout finding** — the
   webhook awaits the full cell run including the structured-output
   LLM call; the synchronous shape is wrong on webhook-contract
   grounds (cold runs at 18–23s exceed Twilio's ~15s timeout; warm
   at 8–9s is still wrong on contract grounds). Architectural fix:
   webhook returns 2xx immediately and dispatches cell run to a
   background task (Path A: in-process asyncio). The fix must pair
   with cell-failure logging because the current bare-`except` at
   `apps/api/routers/messaging.py:267` makes silent background-task
   failure strictly worse.

2. **Intent-extraction reliability at REAL_TIME_REQUIRED with
   `qwen2.5:7b` finding** — 0/7 AddDataPointIntent classifications
   across 4 distinct phrasings; intent-class blindness on
   AddDataPoint at this model/tier. Convergence session's
   confidence-aware response composition framing has to address
   Responses A (raise model size), B (constrain classification
   surface or expand prompt), and C (render model uncertainty as
   user-facing clarification more honestly). Phase 2-A operator-
   dogfooding-via-WhatsApp viability question opens. Instrumentation
   gap (no prompt/output capture in Langfuse trace) obscures the
   clean-UnclearIntent-JSON vs coerced-malformed-output distinction.

Both feed convergence-session inputs. See `log/captures.md` for the
full entries.
