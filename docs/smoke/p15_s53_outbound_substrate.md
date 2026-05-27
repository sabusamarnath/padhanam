# P15 S53 — Outbound initiation substrate smoke

Procedural smoke walking the S53 substrate end-to-end against tenant_a:
the BroadcastFlow Protocol at shared_kernel; the BroadcastDispatch
substrate at messaging context with the in-process adapter; the
BroadcastFlow registry mechanism; the ChannelResolver Protocol with
the StaticConfigChannelResolverAdapter at Phase 2-A; and the reactive
outbound use case's ChannelResolver consultation.

**Procedural** — the operator executes the stages below against the
freshly-rebuilt `padhanam-api` image. **Substrate-only**: S53 carries
no user-facing BroadcastFlow implementer (daily-briefing lands at S54;
threshold-briefing plus ThresholdEvaluator at S57). The smoke exercises
the dispatch substrate directly through a helper script that registers
a synthetic implementer at composition root (for smoke purposes only,
not persisted) and dispatches against it. The HTTP trigger endpoint
(D145) lands at S54; this smoke does not exercise it.

The reactive outbound path (Stage 4) IS user-facing: the smoke sends a
real inbound through Twilio Sandbox and verifies the reactive outbound
consults ChannelResolver before send.

## Prerequisites (executed at smoke-open)

- `padhanam-api` rebuilt via `make build-api`; new digest pin recorded
  in `compose.yaml` and the container force-recreated:
  `docker compose up -d --force-recreate padhanam-api`.
- No Alembic migration required at S53 — the BroadcastDispatch
  substrate is in-process; ChannelResolver consults static config; the
  reactive outbound refactor adds no persistence. The next available
  migration number (0025) consumes at S54 if D145's HTTP trigger
  endpoint substrate ends up needing schema (likely no, since the
  BROADCAST_INITIATED audit event class extends the existing
  audit_events table).
- `OPERATOR_DEFAULT_ADDRESS` configured in the operator's `.env` to
  the operator's WhatsApp E.164 phone number (the Twilio Sandbox
  number the operator messages from); the static-config
  ChannelResolver returns this as the operator-default destination.
- tenant_a's existing manual_entry / audit-conversation /
  mirror-conversation surfaces are operational from P14 close
  (S52 smoke baseline).

## Stage 0 — Baseline state capture

Record the audit-chain row count, the latest Message id, and verify
chain integrity before running the smoke:

```sql
SELECT COUNT(*) FROM tenant_audit;
SELECT MAX(created_at), MAX(id) FROM messages;
```

Record the InProcessBroadcastDispatchAdapter's registered_types set
via the helper script (should be empty at fresh composition because
no BroadcastFlow implementer registers at S53; S54+ implementers
register at composition root).

## Stage 1 — Register a synthetic BroadcastFlow implementer

Operator executes a smoke-helper script that:
1. Constructs a `MessagingComposition` via `build_messaging_composition`.
2. Constructs a synthetic implementer satisfying BroadcastFlow Protocol
   (returns a minimal BroadcastResponse satisfying CitedResponse).
3. Calls `composition.broadcast_flow_registry.register(...)` for
   `BroadcastTriggerType.MANUAL`.
4. Verifies `composition.broadcast_flow_registry.registered_types()`
   returns `frozenset({BroadcastTriggerType.MANUAL})`.

Expected: registration succeeds; the registry surfaces the new
trigger type.

## Stage 2 — Dispatch the synthetic implementer

Operator's smoke-helper script:
1. Constructs a `TriggerContext` with `trigger_type=MANUAL`,
   `trigger_id=uuid4()`, `triggered_at` set to a recent ISO timestamp.
2. Calls `await composition.broadcast_dispatch.dispatch(tenant_id,
   user_id="operator-001", trigger_context=context)`.
3. Awaits the spawned task briefly (two `asyncio.sleep(0)` yields).
4. Verifies the synthetic implementer recorded the call with the
   passed tenant_id and user_id; verifies the returned
   BroadcastResponse satisfies CitedResponse via isinstance check.

Expected: dispatch routes deterministically by `trigger_type`;
implementer's `fire` invokes with the correct tenant_id and user_id;
no exception.

## Stage 3 — Dispatch missing-implementer failure mode

Operator's smoke-helper script:
1. Calls `await composition.broadcast_dispatch.dispatch(...)` with
   `trigger_type=DAILY_SCHEDULED` (no implementer registered for
   this trigger type at S53; daily-briefing registers at S54).
2. Verifies `NoRegisteredBroadcastImplementerError` raises
   synchronously with `trigger_type="daily_scheduled"` on the
   exception.

Expected: missing implementer fails fast; the structured error names
the trigger type so the composition-root registration gap surfaces
clearly. (S54+ implementer registration closes this for each
production trigger type.)

## Stage 4 — Reactive outbound consults ChannelResolver

Operator sends a real inbound to the Twilio Sandbox number (e.g.,
"hi"). The webhook handler:
1. Records the inbound IntakeRecord and Message.
2. Invokes `dispatch_inbound.execute(...)` which threads
   `channel_resolver=messaging.channel_resolver` through to the
   `send_message` call sites.
3. The meta-classifier classifies "hi" as low-confidence; Step 5
   creates a dispatch_clarification PendingClarification; sends the
   routing-prompt outbound via `send_message`.
4. `send_message` consults the StaticConfigChannelResolverAdapter
   which returns the operator-default ChannelDestination (WhatsApp +
   `OPERATOR_DEFAULT_ADDRESS`).
5. Delivery proceeds via the Twilio adapter to the operator's
   WhatsApp; the routing-prompt arrives in the operator's WhatsApp
   conversation.

Expected: identity routing at Phase 2-A (the resolved channel
matches the inbound channel; the operator receives the
routing-prompt on WhatsApp). No user-visible behaviour change from
S52. The structured logging emits no error.

## Stage 5 — Verify integration test parity

Operator runs `python -m pytest tests/integration/api/test_messaging_routes.py -q`
against the live test Postgres + control-plane setup; verifies all
11 messaging route tests pass. This confirms the
MessagingComposition extension (BroadcastDispatch +
BroadcastFlowRegistry + ChannelResolver fields) plus the reactive
outbound refactor preserve the existing integration contract.

Expected: all 11 tests pass; no regression from S52 close baseline.

## Stage 6 — Verify dispatch-task lifecycle (in-process)

Operator's smoke-helper script:
1. Registers a synthetic implementer that takes ~100ms to complete.
2. Dispatches a trigger; verifies `dispatch` returns immediately
   (well under 100ms).
3. After awaiting, verifies the implementer's `fire` completed
   (the spawned task ran).
4. Verifies the asyncio Task set on the adapter is drained
   (`len(adapter._tasks) == 0` after completion).

Expected: dispatch is fire-and-forget; the spawned task completes
without leaking task references; the in-process adapter behaviour
mirrors the CellDispatch adapter pattern from S47.

## Audit chain integrity verification (post-smoke)

Re-run the chain integrity verifier at page granularity:

```python
from contexts.audit.adapters.outbound.postgres.repository import PostgresAuditRepository
# ... verify chain_integrity == "verified" against tenant_a
```

S53 does not emit BROADCAST_INITIATED audit events (the event class
extends at S54 when the HTTP trigger endpoint substrate lands). The
audit chain should show only Stage 4's reactive-outbound events:

- MESSAGE_RECEIVE (Stage 4 inbound).
- PENDING_CLARIFICATION_CREATE (Stage 4 dispatch_clarification).
- MESSAGE_SEND (Stage 4 routing-prompt outbound).

Expected: chain integrity status remains `"verified"`; no duplicate
hashes; no broken links; the three Stage 4 events chain cleanly onto
the existing tenant_a audit chain.

## Smoke close

At smoke close the operator records:

- Per-stage executed-evidence summary (each stage green / yellow with
  caveat / red with finding).
- Any structural-honesty findings surfaced during execution (the
  S48a smoke-driven captures cadence).
- Total audit-chain event delta from baseline (~3 events from
  Stage 4 only).
- Forward dispositions: each finding routes to either a same-session
  fix, a captures entry, or a deferred-decisions entry per the
  Phase 2-A operator-dogfooding rhythm.

**S53 substrate-only smoke posture.** The smoke validates the
dispatch substrate and the channel resolver mechanically against
tenant_a; the user-facing implementer surfaces (daily-briefing,
threshold-briefing, ThresholdEvaluator) land at S54 and S57 and
inherit this substrate. The Stage 4 reactive-outbound consultation
is the only user-visible exercise at S53; it verifies the refactor
preserves Phase 2-A behaviour. The substrate's correctness at the
implementer-side surfaces at S54 close (daily-briefing first
implementer) and S57 close (threshold-briefing + ThresholdEvaluator
plus P15 close).
