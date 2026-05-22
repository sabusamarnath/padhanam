# P13 S45 — Messaging substrate live-stack smoke

Live-stack smoke for the S45 messaging substrate (D129), the
structured-output discipline (D130), and the ConversationFlow
Protocol (D115 shape). Executed evidence for all ten stages (0–9)
end-to-end against tenant_a on the freshly-rebuilt `padhanam-api`
image, including a real Twilio WhatsApp Sandbox round trip in both
directions.

Executed 2026-05-22 across S45-close commits db5274d…6079b9d.

## Stage 0 — Twilio WhatsApp Sandbox setup plus the ngrok-binding gap

The operator created a Twilio account, enabled the Sandbox for
WhatsApp, joined it from `+447966957282`, installed ngrok
(`3.39.4`), authenticated it, and ran `ngrok http 8000`
(forwarding URL `https://easeful-front-quote.ngrok-free.dev`).

**Methodology gap fixed at this stage.** The original draft of this
smoke document (commit c068c87) named `ngrok http 8000` in stage 0
without verifying the compose topology: `padhanam-api` does not bind
a host port (the S5 "only Caddy binds host ports" rule), so
`ngrok http 8000` had nothing to forward to. The gap surfaced when
the operator asked which port to use. The fix — commit 7af8e88 — adds
a loopback-only `127.0.0.1:8000:8000` binding to `padhanam-api`, a
deliberate dev-only exception matching the postgres-control-plane
precedent; the webhook tunnel goes straight to uvicorn because
Caddy's `handle_path /api/*` strips the prefix the messaging router
needs. This is brief-vs-codebase-actuality drift at the
smoke-document altitude — the same shape as the SMS-vs-WhatsApp
finding at the S45 brief, scaled down to a procedural concern.

## Stage 1 — image rebuild plus migration verification

`make build-api` rebuilt the image carrying the S45 substrate. New
digest `sha256:77ad47bf048858d08c8718991ea8c8207ccf79b1517690a29f4c4ac2e2fff666`;
the compose.yaml `padhanam-api` digest pin advanced (commit 0f50c80).
The container started cleanly — "Application startup complete", no
errors; `MessagingSettings` resolved; all four messaging routes
registered.

`make migrate` applied `0018 → 0019_messaging_substrate →
0020_intake_source_whatsapp` to both tenant planes. On tenant_a:
`alembic_version = 0020_intake_source_whatsapp`; the `messages`
table present (13 columns, 2 list indexes, 8 CHECK constraints,
`fk_messages_intake_id` → `intakes(id)` ON DELETE RESTRICT);
`intakes_intake_source_check` admits `MANUAL_ENTRY, WHATSAPP_INBOUND`.

## Stage 2 — outbound send via LocalEcho (the local-first default)

With `MESSAGING_ADAPTER=local_echo` — no Twilio credentials needed.
`POST /api/v1/messaging/send` (tenant_a operator JWT) → **201**.

```
Message 2cb6d146-ad72-4625-8bb9-1fb4d5632b6d
  direction=OUTBOUND  channel=WHATSAPP  status=DELIVERED
  external_id=local-echo-7a8d977a-3430-477b-8a11-b1776e079380
  intake_id=null  actor_id=s45-stage2-operator
```

The `messages` row and the `messaging.message.send` audit event
both persisted on tenant_a. The LocalEcho path made no Twilio API
call and needed no credentials — route → use case → adapter →
persistence → audit ran entirely in-process.

## Stage 3 — outbound send via the Twilio adapter

With `MESSAGING_ADAPTER=twilio`. `POST /api/v1/messaging/send` →
**201**; the Twilio API accepted the message and returned a real
MessageSid.

```
Message 97e5d4c5-0a29-4df4-88fe-fae20bd05a5f
  direction=OUTBOUND  channel=WHATSAPP  status=QUEUED
  external_id=SM81b3ed894d0a3bfb5fcc56723e71a2e7
  from=whatsapp:+14155238886  to=whatsapp:+447966957282
```

The message arrived on the operator's WhatsApp (operator-confirmed).
The `messages` row and the `messaging.message.send` audit event
persisted. The stage-2 and stage-3 audit `after_state` payloads are
byte-structurally identical except `status` (DELIVERED vs QUEUED)
and `external_id` (`local-echo-…` vs `SM…`) — the two
adapter-outcome fields D129's substrate-depth justification
anticipated. LocalEcho is confirmed a faithful local substitute.

## Stage 0b — inbound webhook wiring

`WEBHOOK_TENANT_ID` / `WEBHOOK_JURISDICTION` / `WEBHOOK_URL` added to
`.env`; the three `compose.yaml` passthroughs landed (commit
6079b9d). Container force-recreated; the vars resolve inside the
container. Reachability curl through the tunnel —
`POST https://easeful-front-quote.ngrok-free.dev/api/v1/messaging/inbound`
with no signature → **403 `webhook_signature_invalid`** — confirming
the tunnel reaches the route and signature verification fires. The
Twilio Console "when a message comes in" field was pointed at the
same URL.

## Stage 4 — inbound webhook with a valid signature

The operator sent `Padhanam s45 smoke stage 4 inbound at 20:56`
from `+447966957282` to the sandbox number. Twilio POSTed to the
webhook with a valid `X-Twilio-Signature`; the route returned
**200** in 97 ms (Twilio POST receipt → response).

```
IntakeRecord b165f334-3936-4fd9-9a3e-f5bc3c2af323
  intake_source=WHATSAPP_INBOUND  authored_by=twilio-webhook
  payload.raw_text="Padhanam s45 smoke stage 4 inbound at 20:56"

Message c4ae90e6-ba65-4947-8a24-472d03e8fc0a
  direction=INBOUND  channel=WHATSAPP  status=RECEIVED
  intake_id=b165f334-3936-4fd9-9a3e-f5bc3c2af323
  external_id=SM63855a245329ab3a9dab690ca52c20ba
  from=+447966957282  to=+14155238886  actor_id=twilio-webhook

audit: intake.record.create (intake) + messaging.message.receive (message)
```

The full cascade fired — signature verification → operator
ActorContext synthesised for tenant_a → `record_intake_and_record_inbound_message`
orchestration → IntakeRecord recorded first → inbound Message
carrying its `intake_id`. **D128's intake-canonical commitment,
second-instance evidence, operationally demonstrated** across a real
cross-context webhook (S44b portfolio writes were the first
instance).

## Stage 5 — inbound webhook with an invalid signature

`POST …/api/v1/messaging/inbound` with `X-Twilio-Signature:
fake-invalid-signature` → **403 `webhook_signature_invalid`**. No
side effects: zero `intakes` and zero `messages` rows for the
rejected payload. An `AUTH_FAILURE` security event
(`reason=twilio_signature_verification_failed`) landed in
`logs/security.jsonl`.

## Stage 6 — verify stage 4's persisted state via GET routes

`GET /api/v1/intakes/b165f334…` → 200, `intake_source=WHATSAPP_INBOUND`,
`raw_text` matches the sent body. `GET /api/v1/messaging/messages/c4ae90e6…`
→ 200, `direction=INBOUND`, `channel=WHATSAPP`, `status=RECEIVED`,
`intake_id` linking to the IntakeRecord, `from_address=+447966957282`.

## Stage 7 — cross-tenant isolation

With a tenant_b operator JWT: `GET /api/v1/intakes/b165f334…` →
**404**; `GET /api/v1/messaging/messages/c4ae90e6…` → **404**;
`GET /api/v1/messaging/messages` → 200 with an empty list. The
privacy-preserving 404 policy holds — no tenant_a record leaks to
tenant_b.

## Stage 8 — audit chain end-to-end

tenant_a's `tenant_audit` chain: **134 events, exactly one chain
entry point (the genesis), zero broken links, zero duplicate
`this_event_hash` values** — every non-genesis event's
`previous_event_hash` incorporates the prior event's
`this_event_hash`, a single connected hash chain. The four S45
smoke audit events are absorbed into it:

```
s45-stage2-operator  messaging.message.send     message  205e142efc7b…
s45-stage3-operator  messaging.message.send     message  997eb07eb8ba…
twilio-webhook       intake.record.create       intake   cd184cd16b96…
twilio-webhook       messaging.message.receive  message  f3bca8b714a5…
```

## Stage 9 — GET routes with pagination and filters

`GET /api/v1/messaging/messages?page_size=10` → 200, 3 messages,
`next_cursor=null`. Direction filter: `?direction=OUTBOUND` → 2
(stages 2, 3); `?direction=INBOUND` → 1 (stage 4). Channel filter:
`?channel=WHATSAPP` → 3 (all WhatsApp at S45).

## Carryovers

- The messaging audit events carry an empty `correlation_id` — the
  use cases do not thread the HTTP request's correlation_id, matching
  the intake precedent. Forward hygiene, deferred to Phase 2-A close
  per the prior disposition.
- D131 (provenance-aware response composition) is not exercised — no
  Phase 2-A surface implements a ConversationFlow consumer; first
  exercise at P14, verification a Phase 3 close audit input.
- The smoke-doc stage-0 ngrok-binding gap is recurrence evidence for
  the brief-vs-codebase-actuality drift pattern, accruing toward the
  Phase 2-A close methodology assessment.
