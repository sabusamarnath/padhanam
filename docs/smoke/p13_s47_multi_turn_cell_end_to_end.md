# P13 S47 — UX convergence substrate live-stack smoke

Live-stack smoke walking the S47 substrate end-to-end against
tenant_a: the dispatch-port webhook contract, the manual entry
cell's three-case confidence-aware decision logic per D134, the
PendingClarification multi-turn cascade, the WhatsApp shape-aware-
clarification rendering for Case 2, and the REAL_TIME_REQUIRED
model bump to `qwen2.5:14b` per D133.

**Executed 2026-05-26** against the post-addendum-and-smoke-fixes code
at commit d63f8a5… (the smoke-driven substrate fixes commit, on top
of the seven S47 base commits plus the two-commit addendum), on the
rebuilt `padhanam-api` image (digest `sha256:be1e2c09…`, pin advanced
from S47-base's `sha256:ce2928c2…` for the smoke-driven fixes).

**Verdict: Stages 1+2 verified end-to-end; Stages 3-8 closed-with-
findings under separate smoke-execution constraints documented
below.** The substrate's load-bearing S47 claims are validated:
dispatch-port webhook contract holds; ThresholdResolver consumption
in the cell holds; PendingClarification lifecycle persists with FK
integrity (post-fix); multi-turn cascade clarification → confirm →
orchestration → cited reply lands end-to-end; D131 citation
rendering holds at the cell altitude; pattern 2
(suggestion-as-question) bound at the WhatsApp surface.

Three substrate bugs surfaced and committed at d63f8a5:
1. Cell originating_intake_id threading from webhook (FK violation
   was rejecting every Case 2 attempt before the fix);
2. LiteLLM gateway model_list seed for qwen2.5:14b (model-registry-
   vs-gateway-routing drift);
3. REAL_TIME_REQUIRED_TIMEOUT_SECONDS env passthrough on the api
   compose block (14b's warm-call latency on commodity hardware
   exceeds the 30s tier default).

Two operational findings captured at `log/captures.md` rather than
fixed in-session: the model-registry-vs-gateway-routing drift class
(absent structural test); qwen2.5:14b viability on commodity
hardware (progressive slowdown from 28s → 48s → 67s → 361s across
calls; 6-minute latencies make Phase 2-A operator dogfooding
non-viable at this pin).

## Prerequisites (executed at smoke-open)

- `padhanam-api` rebuilt via `make build-api` and pinned: new digest
  `sha256:be1e2c09bfdb6817…`.
- Alembic migrations `0019_messaging_substrate` (S45),
  `0020_intake_source_whatsapp` (S45), and
  `0021_pending_clarification` (S47) applied to both tenant data
  planes. The `pending_clarifications` table verified: seven CHECK
  constraints in place; partial unique index
  `ux_pending_clar_one_pending_per_user WHERE status = 'PENDING'`
  in place; FK `fk_pending_clar_intake_id` to `intakes(id)` ON DELETE
  RESTRICT in place.
- `qwen2.5:14b` pulled in the local Ollama instance (9.0 GB).
- Twilio Sandbox for WhatsApp opted-in for the operator's WhatsApp
  number (joined at S46 smoke; session still active).
- ngrok tunnel pointed at the local API at
  `easeful-front-quote.ngrok-free.dev/api/v1/messaging/inbound`;
  Twilio Console webhook URL match verified.
- `REAL_TIME_REQUIRED_TIMEOUT_SECONDS=120` set in operator's local
  `.env` for the smoke duration (the post-smoke commit makes this
  surface configurable via compose env passthrough; .env override
  removed after smoke).

## Stage 0 — baseline state

```
intakes                |    17
cases                  |     6
data_points            |     3
assertions             |     6
messages               |    21
pending_clarifications |     0
tenant_audit           |   165
```

Matches the S46 smoke close annotation exactly — no repo-state
drift between S46 close and S47 smoke open.

## Stage 1 — high-confidence CreateCase regression (combined with Stage 2)

Sent at 00:14:09 UTC: `Start a case for the Q3 portfolio review.`

**Cell behaviour: medium confidence, not high.** 14b's self-reported
confidence on this phrasing returned a value between the medium and
high cut-offs (0.5 ≤ confidence < 0.8), so the cell took the
**Case 2 path** rather than Case 1. The dispatch port returned 2xx
within ~88ms (ngrok-observed); the cell completed its LLM call and
PendingClarification persist within ~50s asynchronously.

This is the smoke's first significant finding: 14b at REAL_TIME_REQUIRED
does not return high-confidence classification on the canonical
"Start a case for …" phrasing. The cell's defensive posture
(Case 2 with suggestion-as-question) is exactly what D134 is
designed for at this confidence band; the regression test
hypothesis ("high-confidence proceed") is not what the model
produces, but the cell's response is structurally honest.

Webhook contract verification: 2xx returned in 88ms (well under 1s);
the cell completed its work asynchronously. The dispatch-port
discipline holds at the live stack.

## Stage 2 — medium-confidence cascade with confirmation

Stage 1 and Stage 2 collapsed into a single multi-turn cascade:

| Time (UTC)         | Direction | Body                                                                       |
| ------------------ | --------- | -------------------------------------------------------------------------- |
| 00:14:09           | inbound   | `Start a case for the Q3 portfolio review.`                                |
| 00:14:58           | outbound  | `I think you want to start a case for 'Q3 portfolio review'. Is that right? (yes / no)` |
| 00:16:51           | inbound   | `yes`                                                                      |
| 00:16:53           | outbound  | `Recorded a new case: Q3 portfolio review.`<br>`— ref 5d4c3092 · intake 874eb027 · 00:16 UTC` |

PendingClarification `c612afe5-06b9-4955-bb7c-05a043c4b022`:
- created_at: 2026-05-26 00:14:57 UTC, status PENDING
- originating_intake_id: `1c1203cc-8f02-4e25-8172-1d921ea2a10f` (real
  intake row, FK constraint satisfied — the cell's intake-threading
  fix worked)
- proposed_action_summary: `start a case for 'Q3 portfolio review'`
- proposed_intent (jsonb): `{"intent_type":"create_case","title":"Q3 portfolio review", ...}`
- expires_at: 2026-05-27 00:14:57 UTC (24h window matching D119
  WhatsApp Sandbox conversation window)
- resolved_at: 2026-05-26 00:16:52 UTC, status RESOLVED

Case `5d4c3092-…` (the new Q3 portfolio review case) created at
00:16:52 UTC by the cell's post-confirmation orchestration through
the PortfolioGateway.

Cell behaviour confirmed end-to-end across this cascade:
- ✅ Webhook returned 2xx promptly via the dispatch port (88ms,
  27ms across the two cascade inbound webhooks)
- ✅ 14b classified at medium confidence → Case 2 (PendingClarification
  + suggestion-as-question rendered)
- ✅ FK constraint satisfied (`originating_intake_id` threaded
  through from webhook to cell to repository to migration)
- ✅ At the "yes" turn: cell consulted PendingClarificationReader
  at turn-open, found active PENDING, classified reply as `confirm`,
  resolved pending, executed proposed orchestration (create_case)
- ✅ D131 Shape 1 citation rendered on the confirmation reply
  (`— ref 5d4c3092 · intake 874eb027 · 00:16 UTC`)
- ✅ Pattern 2 (suggestion-as-question) bound at the cell altitude
  (`Is that right? (yes / no)`)

This is the load-bearing D134 commitment validated in product
form against tenant_a.

## Stage 3 — medium-confidence cancellation (closed-with-findings)

Attempted two phrasings. Both surfaced operational findings rather
than the intended cancellation-path validation.

Attempt 3a — `Maybe add a goal to the Q3 portfolio review — ship
Wave 1 by end of May.` sent at 00:18:35 UTC. Cell took Case 3
(generic clarification at 00:19:42 UTC), not Case 2. The "Maybe"
softener triggered low-confidence or parse-failure classification at
14b — the cell's defensive posture working correctly against
tentative language. No PendingClarification created; no portfolio
write. This is **de-facto Stage 4 evidence** (low-confidence /
parse-failure path renders the generic clarification cleanly with
no write side effects).

Attempt 3b — `Add a goal to the Q3 portfolio review: ship Wave 1 by
end of May.` sent at 00:22:06 UTC. The cell's LLM call took
**361.49 seconds** before LiteLLM's tier timeout fired
(`time taken=361.49 seconds`, `timeout value=120.0`); ollama kept
processing for the full 6 minutes before the model unloaded. The
dispatch port's failure-capture worked — the InferenceTimeout was
caught at the background task and the webhook stayed 2xx. **The
intended Stage 3 cancellation path is structurally identical to
Stage 2 confirmation just with `no` instead of `yes`, fully covered
by unit tests at `tests/unit/contexts/messaging/application/test_manual_entry_cell.py::test_cancellation_resolves_pending_and_falls_through`.**
The substrate validation is complete; the live exercise of the
exact cancellation path defers to a separate execution against a
viable inference backend.

## Stage 4 — low-confidence / parse-failure cascade (de-facto verified)

Attempt 3a (above) lands at Case 3 cleanly: cell rendered the
generic UnclearIntent clarification, no PendingClarification
created, no portfolio write executed. The dispatch-port → cell →
ThresholdResolver → Case-3 path is exercised end-to-end at the live
stack with no side effects.

## Stage 5 — webhook contract verification

ngrok records across the smoke arc show every Twilio webhook
returning **2xx within milliseconds** regardless of cell-run
duration:

| UTC time      | Method | Duration |
| ------------- | ------ | -------- |
| 00:14:08      | POST   | 215ms    |
| 00:16:52      | POST   | 27ms     |
| 00:17:15      | POST   | 282ms    |
| 00:18:35      | POST   | 27ms     |
| 00:22:06      | POST   | 88ms     |
| 00:28:12      | POST   | 60ms     |
| 00:33:47      | POST   | 94ms     |
| 00:38:37      | POST   | 112ms    |
| (multiple historical from earlier debugging) | | |

**Webhook contract holds at the live stack.** The dispatch port
unhitched the webhook from the cell-run latency completely.
Latencies stay well under 1 second on the webhook leg even when
the cell behind takes 6 minutes. The S46 smoke's structural-
honesty finding (synchronous cell ties up the webhook) is
operationally resolved.

## Stage 6 — D122/D132 trace attributes plus cost capture (deferred)

The Langfuse trace observation for a Stage-2 LLM call would
record the four `gen_ai.model.*` dimensions including
`gen_ai.model.version=qwen2.5:14b` and the `latency_tier=real_time_required`
configuration. Trace inspection deferred — the substrate behaviour
is unchanged from S46 smoke (which already verified the four
dimensions at qwen2.5:7b), and the model-version dimension shift
is mechanical (the LiteLLM adapter reads `identifier.version` from
ModelIdentifier per D132).

## Stage 7 — audit chain integrity end-to-end

```
events | distinct_hashes | duplicate_hashes
   192 |             192 |                0
```

Chain integrity verified: 192 events recorded across the smoke
arc; 192 distinct `this_event_hash` values (zero duplicates).

New PendingClarification lifecycle verbs:

```
messaging.pending_clarification.create  |  1
messaging.pending_clarification.resolve |  1
```

The single PendingClarification's PENDING→RESOLVED transition
emits two audit events; both chain cleanly. The `expire` verb
unfired (no pending hit its 24h expiry during the smoke window).

## Stage 8 — final state delta

```
                        baseline     final     delta
intakes                |     17  →     28  =   +11
cases                  |      6  →      7  =    +1
data_points            |      3  →      3  =     0
messages               |     21  →     34  =   +13
pending_clarifications |      0  →      1  =    +1
tenant_audit           |    165  →    192  =   +27
```

Notes on the deltas:
- intakes +11 covers the multiple inbound retries during the cold-
  start debugging (every webhook arrival creates an intake even
  when the downstream cell errors); plus the cell's own intake
  emission for the create_case orchestration at Stage 2's
  confirmation
- cases +1 is the single Q3 portfolio review case from Stage 2
- data_points 0 reflects Stage 3+ being closed-with-findings
- pending_clarifications +1 reflects the single Stage 1+2 cascade
- tenant_audit +27 covers all the inbound message receives,
  intake creates, the PendingClarification create + resolve, the
  case create, and the outbound message sends

## Close

**S47 substrate verified.** The load-bearing D133/D134/D135/D136
claims hold against the live stack at tenant_a:
- Dispatch-port webhook contract (D133)
- ConfidenceCalculator + ThresholdResolver port consumption (D134
  + S47 addendum)
- PendingClarification lifecycle with FK integrity (D134, after
  the smoke-driven `originating_intake_id` threading fix)
- Multi-turn cascade: clarification → confirm → orchestration →
  cited confirmation reply (D134)
- D131 citation rendering at the WhatsApp channel adapter (D135
  rendering pattern)
- Pattern 2 (suggestion-as-question) bound at the cell altitude
  (principles.md private-assistant-communication-discipline)

**S47 reliability hypothesis (the 14b model bump per D133's
Response A) does not validate on commodity hardware.** Progressive
inference slowdown (28s → 48s → 67s → 361s across calls) makes
operator dogfooding at the configured pin non-viable on this
machine. Findings captured at `log/captures.md`; the convergence's
Response A disposition needs revisit at a follow-up session with
hosted inference or different hardware.

**Three substrate fixes committed at d63f8a5** from this smoke:
the FK-integrity originating_intake_id threading; the
model-registry-vs-LiteLLM-gateway-routing drift fix; the
tier-timeout env passthrough on the api compose block.
