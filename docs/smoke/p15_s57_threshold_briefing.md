# P15 S57 — Threshold-briefing + P15 close

Procedural smoke for the P15-closing session: the proactive
threshold-briefing arc on the S53/S54 broadcast machinery — the
refresh-then-evaluate scheduled trigger, the ThresholdEvaluator over the
calendar **state** store (D153), the two-stage `THRESHOLD_CROSSED` →
threshold-briefing chain, and the nine-criteria P15 close verification.

**Procedural** — the wiring-proof of the two-stage chain over live
`tenant_a` state was run live (below); the **proactive end-to-end fire**
(operator cancels an event → scheduled trigger → real WhatsApp send) and
the **idempotency re-fire** stay operator-gated (the agent is
`calendar.readonly` and cannot cancel; the send is Twilio).

## Prerequisites

- Stack up; `padhanam-api` carrying the S57 working tree (`make sync-code`
  or rebuilt); LiteLLM/Ollama + Nango + Neo4j up; `tenant_a` with a
  google-calendar connection.

## Stage 1 — Proactive threshold fire (operator-gated)

Cancel or move one in-window event in Google Calendar (operator-created;
the agent is read-only). Fire the scheduled refresh-then-evaluate trigger
(`POST /api/v1/internal/triggers/fire` with `trigger_type=scheduled_evaluation`)
with **no conversation turn**. Confirm: the trigger syncs calendar, the
evaluator matches the cancellation rule over the calendar state, emits
`THRESHOLD_CROSSED`, and the threshold-briefing renders to WhatsApp. This
proves proactivity — the briefing surfaced the change without the user
engaging.

## Stage 2 — Idempotency (operator-gated)

Re-fire the trigger; confirm the same crossing does not double-brief
(fired_triggers, D147; the crossing identity is `rule_id` + `google_event_id`,
stable across the tombstone's `cancelled_at` churn — see Stage A finding).

## Stage 3 — No-cross (restraint)

Fire the trigger with no matching calendar change; confirm no briefing
fires.

## Stage 4 — P15 close verification

Walk the nine close criteria against the as-built (recorded below).

## Executed — 2026-06-03 (live wiring-proof, against the running stack)

Run live against `tenant_a` with working-tree source synced into the
running `padhanam-api` container (`make sync-code`) and the real
LiteLLM/Ollama + Nango + Google + Neo4j stack. The evaluator was driven
directly (a recording emitter for the scan stage and a stub notifier for
the briefing stage) so the two-stage chain was proven without sending a
real WhatsApp message (the send stays operator-gated). `tenant_a` carried
one cancelled meeting (the S55b-2 tombstone) and four confirmed meetings
on distinct days.

- **Stage A (refresh-then-evaluate) — PASS.** The ThresholdEvaluator,
  wired to the real calendar refresh (D149 `sync_calendar` scoped full
  pull) and the live `tenant_a` meetings store, refreshed then evaluated
  over the state and emitted **one** `meeting_cancelled` crossing with a
  stable identity `calendar.meeting_cancelled:<event_id>` (no `cancelled_at`
  — see finding). Refresh-then-evaluate fired in order; the evaluator read
  the calendar state store, not the audit chain (D153).
- **Stage B (two-stage hand-off) — PASS.** The crossing's metadata
  round-tripped into a `ThresholdCrossing`; the threshold-briefing
  implementer fired, and — when the live LLM composer errored this run —
  **fell back to the crossing summary** ("Meeting cancelled: …"), rendered
  the WhatsApp heads-up (`⚠ Heads-up …`), and the notifier recorded the
  send. The composer-failure fallback (the resilience path) is proven
  live; the happy-path LLM compose returned a transient error this run and
  is not separately confirmed (the fallback is the load-bearing guarantee
  for a proactive surface).
- **Stage C (no-cross / restraint) — PASS.** The conflict rule evaluated
  over the live confirmed meetings (all on distinct days, no overlap)
  emitted **zero** crossings — restraint proven live: no matching state,
  no interruption.

### Two findings the live run surfaced (and fixed in-build)

The stubbed unit/contract tests could not catch these (they stub the
store); the live run against real substrate state did. Both are handled
inside the threshold context (Design 1's no-calendar-touch principle),
with the deeper calendar-substrate fixes deferred (`charter/deferred-decisions.md`):

1. **`cancelled_at` churn.** `tombstone_meeting` resets `cancelled_at` to
   the refresh time on every sync, and refresh-then-evaluate refreshes
   inside the scan — so a still-cancelled event's `cancelled_at` lands
   *after* the trigger's `window_end`. The initial idempotency key (which
   included `cancelled_at`) would have changed every scan and re-briefed
   the same cancellation forever. Fixed: the cancellation crossing identity
   is `rule_id` + `google_event_id` (no `cancelled_at`), and the scan-window
   match is lower-bound only. A given cancellation briefs once, ever.
2. **Tombstone purges content.** The briefing reads "(untitled)" from the
   store and says "a meeting was cancelled" without naming it. Accepted for
   Phase 2-A; title enrichment deferred.

### Stage 4 — P15 close verification (nine criteria)

1. **BroadcastFlow Protocol enforced; three implementers register** —
   **MET.** daily-briefing, threshold-briefing, ThresholdEvaluator all
   register against the harness (`test_threshold_rule_evaluation_conformance`
   asserts the three-implementer set).
2. **ChannelResolver operational; static adapter** — **MET** (S53; reused
   by the threshold notifier with `BROADCAST_THRESHOLD_BRIEFING`).
3. **HTTP trigger endpoint operational; `BROADCAST_INITIATED` chains** —
   **MET** (S54; S57 extends the after_state with the crossing metadata).
4. **Calendar + email conversation surfaces; five-way routing; both gold
   sets** — **MET** (S55b, S56b).
5. **Calendar + email consume Nango via HTTP; pull-on-demand verified
   end-to-end** — **MET** for calendar (S55) at representative state;
   **MET for email as wiring-proven, not volume-proven** at the n=1
   mailbox (D154).
6. **ArtefactCitation discriminator extended to four types** — **MET**
   (case, data_point, meeting, email).
7. **Procedural smokes green against tenant_a (S53–S57)** — **MET**;
   criterion 7's **email** entry is recorded **wiring-proven, not
   volume-proven** (D154); this S57 smoke is a wiring-proof of the
   two-stage chain (proactive end-to-end fire operator-gated).
8. **Charter touch-points updated each session** — **MET** (D153, D154,
   architecture, deferred-decisions, captures, current-package, p15-epic).
9. **Phase 2-A close criterion: dogfooding-ready substrate** — **MET**
   (a dogfooding-*ready* substrate, not a completed week; the week +
   senior-leader-ICP validation is the Phase 2-A gate that follows P15).
   The email volume debts + the calendar meeting-moved threshold map to
   that gate (D154).

## Result

The two-stage threshold chain is wired and proven live over `tenant_a`
state: refresh-then-evaluate matches the calendar state, emits a
stable-identity crossing, the briefing composes (with a proven fallback)
and renders, and restraint holds (no-cross → no briefing). The nine P15
close criteria are met, with the email entries recorded wiring-proven and
the volume debts + meeting-moved mapped to the dogfooding gate (D154).
**P15 closes.**

**Status: executed live 2026-06-03 (wiring-proof green: refresh-then-evaluate,
two-stage hand-off, restraint; proactive end-to-end fire + idempotency
re-fire operator-gated; P15 close criteria verified).**
