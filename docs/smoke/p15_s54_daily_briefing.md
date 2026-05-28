# P15 S54 — First end-to-end broadcast: HTTP trigger endpoint + daily-briefing

Procedural smoke walking the first platform-initiated broadcast end-to-end
against tenant_a: the HTTP trigger endpoint (D145) authenticating an
external-scheduler fire; the fired_triggers race-safe idempotency check
(D147); the BROADCAST_INITIATED audit event; the daily-briefing BroadcastFlow
implementer composing from three producer contexts (D146); and the WhatsApp
render plus outbound send.

**Procedural** — the operator executes the stages below against the
freshly-rebuilt `padhanam-api` image. The build environment cannot reach docker
or the Twilio Sandbox; the operator runs the stages live and records evidence
inline (mirroring the S45/S46/S47/S53 smoke precedent).

## Prerequisites (executed at smoke-open)

- `padhanam-api` rebuilt via `make build-api`; new digest pin recorded in
  `compose.yaml` and the container force-recreated:
  `docker compose up -d --force-recreate padhanam-api`.
- Alembic 0025 (`fired_triggers`) applied to BOTH tenant synthetic databases:
  `docker compose exec padhanam-api alembic -c alembic/tenant/alembic.ini upgrade head`
  (run per-tenant per the existing two-plane migration convention). Verify the
  table exists: `\d fired_triggers` shows the four-column UNIQUE constraint
  `ux_fired_triggers_tenant_user_type_key`.
- `.env` configured:
  - `INTERNAL_SECRET` set to a non-empty secret (the scheduler's bearer).
  - `OPERATOR_TIMEZONE` set (e.g. `UTC` or the operator's IANA zone).
  - `OPERATOR_DEFAULT_ADDRESS` set to the operator's WhatsApp E.164 number
    (the ChannelResolver returns it as the briefing destination).
  - `WEBHOOK_TENANT_ID` set to tenant_a's id (the broadcast tenant).
  - `MESSAGING_ADAPTER=twilio` plus Twilio credentials for a real WhatsApp
    round trip (or `local_echo` to verify the persistence/audit path without a
    live send).
- tenant_a's manual_entry / audit-conversation / mirror-conversation surfaces
  operational from P14 close; the daily-briefing reads compose against
  tenant_a's existing portfolio + intake + audit state.

## Stage 0 — Baseline state capture

Capture the baseline counts against tenant_a:

```
intake count:        SELECT count(*) FROM intakes;
message count:       SELECT count(*) FROM messages;
audit chain count:   SELECT count(*) FROM tenant_audit;
fired_triggers count:SELECT count(*) FROM fired_triggers;   -- expect 0
```

Record: `intakes=__, messages=__, tenant_audit=__, fired_triggers=0`.

## Stage 1 — Simulate operator activity

Send a manual_entry inbound (via the Twilio webhook or `padhanam` CLI) that
creates an IntakeRecord and a Case write, so the briefing window has activity:

> "Start a case for the Q3 portfolio review."

Verify: a new IntakeRecord (`intakes += 1`), a Case created, and audit events
chained (`tenant_audit` grows). Record the Case id and intake id.

## Stage 2 — External scheduler fires DAILY_SCHEDULED

Simulate the deployment's scheduler firing the daily trigger via curl:

```
curl -sS -X POST https://localhost/api/v1/internal/triggers/fire \
  -H "X-Internal-Secret: $INTERNAL_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"trigger_type":"daily_scheduled","trigger_id":"'"$(uuidgen)"'","triggered_at":"'"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"'"}'
```

Verify:
- HTTP 200 with `{"trigger_id": "...", "status": "accepted"}`.
- `fired_triggers += 1`; the row carries `trigger_type='daily_scheduled'` and
  `idempotency_key` = today's date in `OPERATOR_TIMEZONE`.
- A BROADCAST_INITIATED audit event chained
  (`SELECT * FROM tenant_audit WHERE action_verb='messaging.broadcast.initiated'`):
  one row with `resource_type='broadcast'`, `resource_id` = the trigger_id.

## Stage 3 — Daily-briefing implementer composes + sends

Verify BroadcastDispatch invoked the daily-briefing implementer (it is the
registered implementer for `DAILY_SCHEDULED`):
- The implementer composed a DailyBriefingResponse with non-empty citations
  (the Stage 1 intake + audit event + the active Case).
- The WhatsApp render produced a briefing message beginning
  `Daily briefing · <window>` with the prose body and a Shape-1 citation
  footer (`ref … · intake … · audit … · HH:MM UTC`).
- An outbound Message persisted (`messages += 1`, `direction='OUTBOUND'`) and
  delivered (Twilio: operator receives the briefing on WhatsApp; local_echo:
  the message persists with `external_id` = `local-echo-…`).

## Stage 4 — Outbound Message cell_payload is null

Verify the outbound briefing Message has `cell_payload IS NULL` — daily-briefing
does not persist cell_payload at first instance (D146; broadcasts have no
user-driven follow-up turns).

## Stage 5 — Scheduler retry within the same day (idempotency)

Fire the SAME trigger again within the same operator day (new trigger_id, same
date):

```
curl -sS -X POST https://localhost/api/v1/internal/triggers/fire \
  -H "X-Internal-Secret: $INTERNAL_SECRET" -H "Content-Type: application/json" \
  -d '{"trigger_type":"daily_scheduled","trigger_id":"'"$(uuidgen)"'","triggered_at":"'"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"'"}'
```

Verify:
- HTTP 200 with `{"status": "already_fired"}`.
- `fired_triggers` count UNCHANGED (the UNIQUE constraint rejected the dup).
- NO second BROADCAST_INITIATED audit event.
- NO second outbound Message.

## Stage 6 — Next-day fire (window rollover)

Advance the operator clock one day (or inject a `triggered_at` whose
`OPERATOR_TIMEZONE` date is the next day). Fire DAILY_SCHEDULED again. Verify:
- HTTP 200 `accepted`; `fired_triggers += 1` (new date key).
- A second BROADCAST_INITIATED audit event.
- A second outbound briefing Message.

## Stage 7 — Empty-day briefing

On a quiet day (no recent IntakeRecords or audit events in the window), fire
DAILY_SCHEDULED. Verify:
- The briefing still SENDS (always-send per D146) with portfolio-state-only
  prose ("Nothing changed in the last day; your portfolio stands at N cases").
- The response cites the active Cases only (`cited_artefacts` non-empty;
  `cited_intake_records` and `cited_audit_events` empty).

## Stage 8 — Authentication failure

Fire without (or with a wrong) `X-Internal-Secret`:

```
curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
  https://localhost/api/v1/internal/triggers/fire \
  -H "Content-Type: application/json" \
  -d '{"trigger_type":"daily_scheduled","trigger_id":"'"$(uuidgen)"'","triggered_at":"2026-05-28T06:00:00+00:00"}'
```

Verify:
- HTTP 401 with `{"error_code": "internal_secret_invalid", ...}`.
- NO fired_triggers row inserted.
- NO BROADCAST_INITIATED audit event.
- An AUTH_FAILURE security event recorded in the security-event stream.

## Acceptance

All eight stages green against tenant_a on the rebuilt image. The smoke
demonstrates: the HTTP trigger endpoint authenticating an external-scheduler
fire; race-safe idempotency at the fired_triggers UNIQUE constraint (Stage 5
retry skip; Stage 6 next-day fresh); the BROADCAST_INITIATED audit chain
anchoring; the daily-briefing composition across three producer contexts; the
WhatsApp render with briefing-period header and citation footer; and the
always-send empty-day behaviour.

---

**Execution status:** Procedural — pending live operator execution. The build
environment cannot reach docker or the Twilio Sandbox; the operator executes the
stages above against the live stack and records evidence inline at smoke time
(the S45/S46/S47/S53 procedural-then-executed precedent).
