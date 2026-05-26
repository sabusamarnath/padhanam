# P13 S50 — Resolver disambiguation live-stack smoke

Live-stack smoke walking the S50 substrate end-to-end against
tenant_a: multi-match resolution at the `find_cases` adapter
producing CaseSummary discriminators, the cell's numbered
disambiguation rendering at the WhatsApp surface, positional-
selection resolution of the PendingClarification, and audit-chain
integrity across the two-turn cascade.

**Procedural** — the operator executes the stages below against the
freshly-rebuilt `padhanam-api` image. tenant_a already carries three
"Q3 portfolio review" cases accumulated from the S46/S47/S48a
smokes; S50 exercises the disambiguation surface against them
directly without seeding additional fixture data.

## Prerequisites (executed at smoke-open)

- `padhanam-api` rebuilt via `make build-api`; new digest pin
  recorded in `compose.yaml` and the container force-recreated:
  `docker compose up -d --force-recreate padhanam-api`.
- No Alembic migration required at S50 — the cell-layer extension
  reuses the existing `pending_clarifications` table per the S50
  pre-write reconciliation Surface 3 finding (PendingClarification
  schema accommodates the resolution-ambiguity sub-case via the
  existing `proposed_intent dict[str, Any]` field).
- `gpt-4o-mini` pin still active at REAL_TIME_REQUIRED tier
  (`INFERENCE_REAL_TIME_REQUIRED_MODEL=gpt-4o-mini`, verified in
  `padhanam/config/inference.py`); `OPENAI_API_KEY` in the
  operator's `.env`.
- Twilio Sandbox for WhatsApp still opted-in for the operator's
  number (joined at S46 smoke).
- ngrok tunnel pointed at the local API webhook; Twilio Console
  webhook URL match verified.

## Stage 0 — baseline state

Expected tenant_a portfolio state at smoke-open (carried from
S48a smoke close):

```sql
SELECT
  (SELECT COUNT(*) FROM cases) AS cases_count,
  (SELECT COUNT(*) FROM cases WHERE title = 'Q3 portfolio review')
    AS q3_dupe_count,
  (SELECT COUNT(*) FROM data_points) AS data_points_count,
  (SELECT COUNT(*) FROM pending_clarifications
    WHERE status = 'PENDING') AS pending_count,
  (SELECT COUNT(*) FROM tenant_audit) AS audit_events_count;
```

Expected: `q3_dupe_count = 3` (one each from S46, S47, S48a smokes).
The three cases have distinct `created_at` timestamps and may have
different `data_points` counts depending on which smokes wrote
against them.

## Stage 1 — multi-match disambiguation render

Send via WhatsApp to the Twilio Sandbox number:

```
add a goal to the Q3 portfolio review: ship Wave 1 by end of June
```

**Expected cell behaviour.** The cell extracts AddDataPointIntent
at high confidence (`gpt-4o-mini` should classify this cleanly per
S48a evidence — 4/4 correct on the four AddDataPointIntent phrasings
at the smoke). `find_cases` returns three CaseSummary entries with
title="Q3 portfolio review", each carrying its created_at,
last_activity_at, and data_point_count. `resolve_target` returns
AMBIGUOUS with three candidates. The cell renders a numbered
clarification phrased as a question:

```
More than one case matches "Q3 portfolio review". Which did you mean?
1. Q3 portfolio review — created N days ago, X data points, last activity N days ago
2. Q3 portfolio review — created N days ago, X data points, last activity N days ago
3. Q3 portfolio review — created N days ago, X data points, last activity N days ago
(reply with the number)
```

**PendingClarification persistence verified at the database:**

```sql
SELECT id, user_id, status, proposed_action_summary,
       proposed_intent::jsonb ? 'resolution_candidates'
         AS has_candidates_sidecar
FROM pending_clarifications
WHERE status = 'PENDING'
ORDER BY created_at DESC LIMIT 1;
```

Expected: one PENDING row whose `proposed_action_summary` reads
`choose among 3 cases matching "Q3 portfolio review"` and whose
`proposed_intent` carries the `resolution_candidates` sidecar
(`has_candidates_sidecar = TRUE`).

**Audit events expected:**
- `messaging.inbound.received` (the inbound webhook intake)
- `messaging.pending_clarification.create` (the cell's resolution-
  ambiguity pending)
- `messaging.outbound.sent` (the WhatsApp clarification render)

## Stage 2 — positional-selection resolution

Operator replies with `2` (or whichever positional index the
disambiguation surface shows for the case the operator wants to
add the goal to):

```
2
```

**Expected cell behaviour.** The cell's reply-handling consults
the active PendingClarification, sees the `resolution_candidates`
sidecar in `proposed_intent`, parses "2" as a positional selection,
validates 1 ≤ 2 ≤ 3 (range check), reads the chosen candidate's
id from the sidecar's index-1 entry, resolves the pending as
confirmed, executes `create_data_point` against the chosen case_id,
and renders the cited confirmation:

```
Added a goal to Q3 portfolio review: ship Wave 1 by end of June.

— ref <ref-short-hex> · intake <intake-short-hex> · HH:MM UTC
```

**Database verification:**

```sql
SELECT id, status, resolved_at
FROM pending_clarifications
WHERE id = '<pending-id-from-stage-1>';
```

Expected: status `RESOLVED`; resolved_at populated within seconds
of the inbound "2".

```sql
SELECT id, case_id, data_point_type, value
FROM data_points
WHERE case_id = '<chosen-case-id>'
ORDER BY created_at DESC LIMIT 1;
```

Expected: one new DataPoint with type `GOAL` and
`value->>'text' = 'ship Wave 1 by end of June'`, on the chosen
case_id (the operator confirms this is the correct case).

**Audit events expected:**
- `messaging.inbound.received` (the "2" inbound webhook intake)
- `messaging.pending_clarification.resolve` (resolution=confirmed)
- `intake.received` (the orchestration's intake record)
- `portfolio.data_point.create` (the data point write)
- `messaging.outbound.sent` (the cited confirmation render)

## Stage 3 — out-of-range positional selection (re-render)

Trigger a new disambiguation cascade by sending a different
add-data-point intent against the duplicate-title cases:

```
add a status to the Q3 portfolio review: on track for end of June
```

Cell creates a new PendingClarification with three candidates.
Operator replies with an out-of-range integer:

```
5
```

**Expected cell behaviour.** Cell detects the active resolution-
ambiguity pending, parses "5" as positional, range check fails
(5 > 3), re-renders the numbered clarification without resolving
the pending:

```
I only have 3 options — please reply with a number between 1 and 3.
1. Q3 portfolio review — ...
2. Q3 portfolio review — ...
3. Q3 portfolio review — ...
```

**Database verification:** the same PENDING row remains; status
unchanged.

**Audit events expected:**
- `messaging.inbound.received` (the "5" intake)
- `messaging.outbound.sent` (the re-render)
- No `pending_clarification.resolve` event yet.

Operator then completes the cascade by sending a valid index (e.g.
`1`). Stage 2-shape verification re-applies.

## Stage 4 — correcting reply cancels the resolution pending

Trigger another disambiguation cascade and reply `no` instead of a
positional integer:

```
add a goal to the Q3 portfolio review: experiment with daily standups
```

Operator replies:

```
no
```

**Expected cell behaviour.** Cell's `_classify_reply` returns
"cancel"; the cell resolves the pending with `resolution=cancelled`;
the cell falls through to fresh-turn classification of "no" (which
classifies as UnclearIntent / low confidence at gpt-4o-mini per
S48a evidence) and renders a Case 3 generic clarification.

**Database verification:** the pending transitions to RESOLVED
with `resolved_at` populated; no DataPoint written.

## Stage 5 — audit chain integrity end-to-end

After all four stages plus any operator-elected variations:

```sql
SELECT COUNT(*) AS event_count,
       COUNT(DISTINCT event_hash) AS distinct_hashes,
       SUM(CASE WHEN previous_event_hash = '' THEN 1 ELSE 0 END)
         AS genesis_rows,
       SUM(CASE WHEN previous_event_hash != '' AND NOT EXISTS (
             SELECT 1 FROM tenant_audit p
             WHERE p.event_hash = tenant_audit.previous_event_hash
           ) THEN 1 ELSE 0 END) AS broken_links
FROM tenant_audit;
```

Expected:
- `event_count` increased by the sum of events emitted across
  Stages 1-4.
- `distinct_hashes` equals `event_count` (no duplicate hashes).
- `genesis_rows = 1` (the original genesis from 2026-05-12).
- `broken_links = 0`.

## Smoke close — tenant_a state delta

Record the deltas across the smoke run (cases, data_points,
pending_clarifications terminal states, audit events). Capture as a
brief paragraph appended below this section after operator
execution.

## S50 verdict

Substrate disposition closes at S50 if Stages 1-2 land
operationally (numbered disambiguation render plus positional
selection executes the action against the chosen case). Stage 3
and Stage 4 are robustness checks; minor rendering deviations
(formatting nits) are recordable as captures entries rather than
S50-blocking findings. Audit chain integrity at Stage 5 is the
load-bearing closure of the procurement-grade defensibility the
substrate carries.

**Forward.** P14 epic framing inherits the resolver-disambiguation
disposition (resolution-ambiguity routes to D134's shape-aware
clarification surface via the cell-layer extension at S50). The
captures entry at `log/captures.md` records the disposition with
the P14 second-instance recurrence test named for explicit
architecture.md prose addition.
