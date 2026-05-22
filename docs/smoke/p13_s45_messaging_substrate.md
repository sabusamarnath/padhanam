# P13 S45 — Messaging substrate live-stack smoke

Live-stack smoke for the S45 messaging substrate (D129), the
structured-output discipline (D130), and the ConversationFlow
Protocol (D115 shape) — the full propagation paths exercised
end-to-end against tenant_a on a freshly-rebuilt `padhanam-api`
image with the 0019 and 0020 migrations deployed.

**Execution note.** This document is the smoke *procedure* with
expected outcomes, not executed evidence. Stages 0 and 3–6 require a
Twilio account plus the operator's own WhatsApp number and an ngrok
tunnel — they are inherently operator-executed. Docker was not
reachable from the build environment, so the operator runs the
sequence below and confirms each expected outcome; the LocalEcho
stages (2, 9) and the migration / cross-tenant / audit stages
(1, 7, 8) are runnable as soon as the stack is up. This mirrors the
S39 procedural-walkthrough-plan precedent.

## Stage 0 — Twilio WhatsApp Sandbox setup (operator)

The Twilio Sandbox for WhatsApp gives a working WhatsApp channel
without a verified WhatsApp Business Account (D119). One-time setup:

1. Create a Twilio account; open **Messaging → Try it out → Send a
   WhatsApp message**. The console shows the sandbox number
   (`+14155238886`) and a join keyword.
2. From the operator's WhatsApp, send `join <sandbox-keyword>` to
   `+14155238886`. The console confirms the number joined.
3. Start an ngrok tunnel to the API: `ngrok http 8000`. Note the
   public `https://<id>.ngrok-free.app` URL.
4. In the Twilio sandbox settings, set **"When a message comes in"**
   to `https://<id>.ngrok-free.app/api/v1/messaging/inbound` (POST).
5. Populate `.env`:

```
MESSAGING_ADAPTER=twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=+14155238886
WEBHOOK_TENANT_ID=<tenant_a UUID>
WEBHOOK_JURISDICTION=eu-west
WEBHOOK_URL=https://<id>.ngrok-free.app/api/v1/messaging/inbound
```

Sandbox limits — per-number opt-in, one message per three seconds,
pre-approved templates for business-initiated messages outside the
24-hour window — are minimal here because dogfooding is
operator-initiated.

## Stage 1 — image rebuild plus migration verification

```
make build-api
docker compose up -d --force-recreate padhanam-api   # -> healthy
make migrate
# -> Running upgrade 0018_intake_id_columns -> 0019_messaging_substrate
# -> Running upgrade 0019_messaging_substrate -> 0020_intake_source_whatsapp
#    applied to tenant_a AND tenant_b
```

Expected:

```
alembic head, postgres-tenant-a: 0020_intake_source_whatsapp   ✓
alembic head, postgres-tenant-b: 0020_intake_source_whatsapp   ✓
information_schema: messages table present on tenant_a          ✓
messages.intake_id FK -> intakes(id) present                    ✓
intakes_intake_source_check admits WHATSAPP_INBOUND             ✓
```

## Stage 2 — outbound send via LocalEcho (default development path)

With `MESSAGING_ADAPTER=local_echo` (the default), no Twilio
credentials are needed — the local-first path. Dev JWT for
tenant_a's operator via `padhanam.security.auth.issue_dev_token`;
httpx against `http://localhost:8000`.

```
POST /api/v1/messaging/send
  {"to_address": "+447700900123", "body": "S45 local-echo smoke"}
  -> 201
     direction=OUTBOUND  channel=WHATSAPP  status=DELIVERED
     external_id=local-echo-<uuid>
```

The LocalEcho adapter logs the send and synthesises a DELIVERED
result; the Message persists on tenant_a's `messages` table. This
is the stage that exercises the LocalEcho adapter at S45 close
(reflection prompt 5).

## Stage 3 — outbound send via the Twilio adapter

Restart the API with `MESSAGING_ADAPTER=twilio`.

```
POST /api/v1/messaging/send
  {"to_address": "whatsapp:+<operator number>", "body": "S45 Twilio smoke"}
  -> 201
     direction=OUTBOUND  channel=WHATSAPP  status=QUEUED
     external_id=SM<...>   (the Twilio MessageSid)
```

Expected: the message arrives on the operator's WhatsApp; the
persisted Message carries the Twilio MessageSid as `external_id`.

## Stage 4 — inbound webhook with a valid signature

From the operator's WhatsApp, reply to the sandbox number with a
portfolio update, e.g. `status: Acme deal moved to legal review`.
Twilio POSTs the inbound message to the webhook URL with a valid
`X-Twilio-Signature`.

Expected:

```
POST /api/v1/messaging/inbound  (from Twilio)  -> 200
  {"status": "received", "message_id": "...", "intake_id": "..."}
```

The webhook bypasses bearer auth (its path is in the middleware
public-path set) and verifies the signature against the configured
`WEBHOOK_URL` before processing.

## Stage 5 — inbound webhook with an invalid signature (rejection)

Replay the Stage 4 request with a tampered body (or a garbage
`X-Twilio-Signature` header) via curl:

```
curl -X POST https://<id>.ngrok-free.app/api/v1/messaging/inbound \
  -H 'X-Twilio-Signature: not-a-real-signature' \
  -d 'From=whatsapp:%2B447700900123&Body=tampered&MessageSid=SMx'
  -> 403  {"error_code": "webhook_signature_invalid", ...}
```

Expected: 403; no IntakeRecord and no Message written; an
`AUTH_FAILURE` security event in `logs/security.jsonl` with reason
`twilio_signature_verification_failed`.

## Stage 6 — inbound lands as IntakeRecord plus Message

For the Stage 4 inbound message, verify the intake-canonical
propagation (D128):

```
GET /api/v1/intakes?source=WHATSAPP_INBOUND   -> 200
  one IntakeRecord, intake_source=WHATSAPP_INBOUND,
  payload.raw_text = the message body

GET /api/v1/messaging/messages?direction=INBOUND   -> 200
  one Message, direction=INBOUND, status=RECEIVED,
  intake_id = the IntakeRecord id above
```

The orchestration recorded the IntakeRecord first, then the Message
carrying its `intake_id` — second-instance evidence for D128.

## Stage 7 — cross-tenant probes

With tenant_b's operator JWT, probe tenant_a's message:

```
GET /api/v1/messaging/messages/<tenant_a message id>  (as tenant_b)
  -> 404  message_not_found

GET /api/v1/messaging/messages  (as tenant_b)
  -> 200  empty list (no tenant_a messages leak)
```

The bound-tenant adapter returns None / empty cross-tenant; the
route surfaces 404 / an empty page. Adapter-level cross-tenant
isolation is additionally covered by
`tests/contract/tenant_isolation/test_messaging_isolation.py`.

## Stage 8 — audit chain verification

Every messaging write emits an audit event (D110 commitment 7):

```
GET /audit/events?resource_type=message   -> 200
  messaging.message.send    events for the Stage 2 / 3 outbound sends
  messaging.message.receive event  for the Stage 4 inbound message
  chain integrity: intact
```

The audit context's existing hash chain transitively covers the
messaging records; no parallel hash chain on the `messages` table.

## Stage 9 — GET routes with cursor pagination

Send a handful of messages, then page:

```
GET /api/v1/messaging/messages?page_size=2   -> 200
  2 messages, next_cursor present
GET /api/v1/messaging/messages?page_size=2&cursor=<next_cursor>  -> 200
  the following page; next_cursor null on the final page
```

Newest-first ordering on `(created_at DESC, id DESC)`; the cursor is
the opaque base64-JSON codec.

## Carryovers

- The LocalEcho-versus-Twilio split (reflection prompt 5): Stage 2
  exercises LocalEcho at the default path; the operator confirms it
  is a real dev cycle, not unused substrate.
- D131 provenance-aware response composition is not exercised — no
  Phase 2-A surface implements a ConversationFlow consumer
  (reflection prompt 6); first exercise at P14.
- The structured-output port has no Phase 2-A caller; the contract
  harness verifies structural conformance offline.
