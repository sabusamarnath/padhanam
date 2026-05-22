# P13 S46 — Manual entry cell end-to-end live-stack smoke

Live-stack smoke for the S46 manual entry cell — the first
ConversationFlow implementer (D115) — exercising the full
operator-WhatsApp-to-portfolio-state cascade against tenant_a:
inbound WhatsApp message → intent extraction via structured output
→ target resolution → intake-canonical portfolio orchestration →
cited confirmation rendered back to the operator's WhatsApp.

Also exercises the D122 latency-tier routing and the D132 four-layer
model ontology: every LLM call carries a `latency_tier` and the
adapter span captures the four `gen_ai.model.*` dimensions.

**Status: procedural.** The build environment cannot reach docker or
the Twilio Sandbox; this document is the script the operator
executes live. Executed evidence is appended after the run (the S45
smoke followed the same procedural-then-executed shape).

S46 ships **no Alembic migration** — the cell, the intent value
objects, the four-layer ontology, and the latency-tier routing are
all code. The cell writes through the existing `cases`,
`data_points`, `assertions`, `intakes`, and `messages` tables;
migrations `0019`/`0020` from S45 are already applied to both tenant
planes.

## Stage 0 — image rebuild and webhook tunnel

`make build-api` rebuilds the `padhanam-api` image carrying the S46
code; the `compose.yaml` digest pin advances. The container starts
clean ("Application startup complete"); `MessagingSettings` and
`InferenceSettings` resolve; the four messaging routes register.

The webhook tunnel is unchanged from S45: the loopback-only
`127.0.0.1:8000:8000` binding on `padhanam-api` (the dev-only S5
exception, commit 7af8e88) plus `ngrok http 8000`. Point the Twilio
Sandbox "When a message comes in" webhook at the ngrok URL +
`/api/v1/messaging/inbound`.

`MESSAGING_ADAPTER=twilio` so the outbound reply reaches real
WhatsApp; the operator's number is joined to the Sandbox.

## Stage 1 — operator sends a create-case message

The operator sends, from their joined WhatsApp number, a message
with a clear create-case intent — for example:

> Start a case for the Q3 portfolio review.

## Stage 2 — the webhook records the inbound (intake-canonical)

The webhook verifies the `X-Twilio-Signature`, then
`record_intake_and_record_inbound_message` records one IntakeRecord
(`intake_source=WHATSAPP_INBOUND`) and one inbound Message
(`direction=INBOUND`, `intake_id` linked) — the canonical record
that the message arrived (D128, second-instance evidence carried
from S45).

Verify in the tenant_a database:

```
docker compose exec postgres-tenant-a psql -U padhanam -d tenant_a -c \
  "SELECT intake_source, created_at FROM intakes ORDER BY created_at DESC LIMIT 2;"
docker compose exec postgres-tenant-a psql -U padhanam -d tenant_a -c \
  "SELECT direction, body, intake_id FROM messages ORDER BY created_at DESC LIMIT 2;"
```

## Stage 3 — the cell extracts CreateCaseIntent

The webhook builds the `ManualEntryCell` and runs `open` / `turn` /
`close`. `turn` calls `StructuredOutputPort.generate_structured`
with `latency_tier=REAL_TIME_REQUIRED` and the intent-extraction
JSON Schema. `parse_intent` maps the result to a `CreateCaseIntent`
carrying `title="Q3 portfolio review"`.

**As-built note.** The framing brief's stage 3 expected target
resolution to run and return `no_match` for a new case. The as-built
cell does *not* resolve for `CreateCaseIntent` — a new case has no
existing target to resolve against, so the cell creates directly.
Resolution runs only for `AddDataPointIntent` and
`ReviseDataPointIntent` (the scenarios below).

Verify the structured-output span carries the D122/D132 attributes
in the trace (`gen_ai.operation.name=structured_output`,
`gen_ai.model.provider`, `.account`, `.version`,
`.configuration` — the last containing
`latency_tier=real_time_required`).

## Stage 4 — the cell drives record_intake_and_create_case

The cell calls `PortfolioGateway.create_case`, which the apps/-layer
`PortfolioGatewayAdapter` routes to the `record_intake_and_create_case`
orchestration. This records a second IntakeRecord
(`intake_source=MANUAL_ENTRY`) and the Case, each emitting audit
events. Two IntakeRecords for one inbound message is structurally
honest — "a WhatsApp message arrived" and "a Case was created" are
two distinct intake events.

```
docker compose exec postgres-tenant-a psql -U padhanam -d tenant_a -c \
  "SELECT title, case_type, status, intake_id FROM cases ORDER BY created_at DESC LIMIT 1;"
docker compose exec postgres-tenant-a psql -U padhanam -d tenant_a -c \
  "SELECT action_verb, resource_type FROM tenant_audit ORDER BY recorded_at DESC LIMIT 6;"
```

## Stage 5 — the cell composes the cited response

The cell composes a `CellResponse` carrying D131 citation fields:
`cited_intake_records` (the MANUAL_ENTRY IntakeRecord id),
`cited_artefacts` (the Case id). `cited_audit_events` is empty at
S46 — the intake-owned write-result DTOs do not surface audit-event
ids (the convention-versus-structural-enforcement gap recorded at
`charter/captures.md`).

## Stage 6 — outbound WhatsApp reply with compact citations

The webhook sends the rendered reply outbound via `send_message`
(an OUTBOUND Message persists, `external_id` carrying the Twilio
`SM…` sid). The operator's WhatsApp receives, for example:

> Recorded a new case: Q3 portfolio review.
>
> — ref 3b001430 · intake 5e9b2740 · 14:23 UTC

D131 Shape 1: a short-hex prefix per cited artefact and intake
record, plus the composition timestamp.

## Stage 7 — operator confirms receipt and citation legibility

The operator confirms the reply arrived on WhatsApp and the compact
citation line is legible — the short-hex prefixes match the Case and
IntakeRecord ids from stage 4.

## Stage 8 — ambiguity, clarification, and failure scenarios

- **Add a data point (resolution match).** Send "add a goal to the
  Q3 review: ship Wave 1 by end of May." The cell extracts
  `AddDataPointIntent`, resolves "the Q3 review" to the Case from
  stage 4, and drives `record_intake_and_create_data_point`. The
  reply: "Added a goal to Q3 portfolio review: ship Wave 1 by end of
  May." with citations.
- **Revise a data point.** Send "revise the Wave 1 goal to mid-June."
  The cell resolves the data-point reference and drives
  `record_intake_and_revise_data_point`; a new REVISION assertion
  appends.
- **Ambiguous reference.** With two similarly-named cases, an
  add-data-point message whose reference matches both yields a
  clarification ("More than one case matches …") and **no write**.
- **Unclear intent.** Send a message with no actionable intent; the
  cell replies with a clarification and touches no portfolio state.
- **No match.** An add-data-point message referencing a non-existent
  case yields "I could not find a case matching …" and no write.

A clarification reply carries no citation line (D131: only a
confirmation of a real write cites artefacts).

## Verification checklist

- [ ] Inbound message records one `WHATSAPP_INBOUND` IntakeRecord
      plus one INBOUND Message (intake-canonical).
- [ ] The cell extracts the correct intent via structured output at
      the REAL_TIME_REQUIRED tier.
- [ ] CreateCaseIntent creates directly (no resolution);
      Add/ReviseDataPointIntent resolve their reference first.
- [ ] A successful write records a `MANUAL_ENTRY` IntakeRecord plus
      the Case / DataPoint, with audit events.
- [ ] The outbound reply carries D131 compact citations
      (short-hex-prefix-plus-timestamp); a clarification carries none.
- [ ] Every LLM-call span carries the four `gen_ai.model.*`
      dimensions (D132); the configuration dimension carries the
      latency tier (D122).
- [ ] An invalid `X-Twilio-Signature` is rejected 403 with no writes.
- [ ] The audit chain holds (one genesis, zero broken links).

## Latency-tier observations (Phase 2-A baseline)

Record the observed latency of the cell's `REAL_TIME_REQUIRED`
structured-output call here at execution. The cell's intent
extraction is a small structured generation; against local Ollama
`qwen2.5:7b` it is the load-bearing real-time latency data point for
Phase 2-A. No `ASYNC_TOLERANT` call fires on the cell path.

## Executed evidence

_To be appended after the operator runs the smoke live._
