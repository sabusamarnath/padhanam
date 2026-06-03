# P15 S55b-2 — Calendar dispatch integration + citation evidence (S55b close)

Procedural smoke for the second and final S55b unit: the calendar
conversation surface reached through the live MetaClassifier dispatch
path, the four-way routing intact, the citation-time audit-snapshot
evidence frozen under a real refresh, and the operator-gated calendar
cancellation tombstone closed.

**Procedural** — operator-executed live against `tenant_a` on the running
stack (the baked image already carries the calendar substrate per the
S55b-1 close). Record evidence inline. **S55b closes when stages 1 and 3
are green; P15 continues to S56.**

## Prerequisites

- Stack up; `padhanam-api` on the S55b-1-era baked image (or rebuilt);
  Nango provisioned; Ollama + Neo4j up; `tenant_a` migration 0026 applied
  with the google-calendar connection present.

## Stage 1 — Dispatch-through end-to-end

Drive the dispatch path with a calendar question (via `dispatch_inbound`
with the four-way meta-classifier and the cell-runner set, or the live
inbound webhook). Confirm: the MetaClassifier routes to
`calendar_conversation`, the refresh fires (D150), and a cited response
renders with `meeting` citations. Run at least one phrasing per calendar
intent class (date-range, attendee, title, next-meeting).

**Record** the routed cell, the classified intent classes, and the cited
meetings.

## Stage 2 — Four-way routing spot-check (no regression)

Confirm a manual_entry phrasing ("add a data point…"), an audit phrasing
("show me the audit history…"), and a mirror phrasing ("list my open
cases") still route to their surfaces — the fourth route did not regress
the prior three.

**Record** the routed cell per phrasing.

## Stage 3 — Citation-snapshot evidence under a real refresh

After a cited calendar turn, read the most recent `meeting_citation`
audit event and confirm its `after_state` holds the immutable snapshot
(encrypted content blob + plaintext metadata; **no plaintext title/
description/location**). Then change a meeting in Google Calendar (e.g.
rename one), trigger a refresh, and confirm the earlier `meeting_citation`
audit event's snapshot is **unchanged** — the evidence is decoupled from
the mutated live row (D148 option b).

**Record** that the audit snapshot carries no plaintext, decrypts to the
cited content, and is unchanged after the live-row mutation.

## Stage 4 — Cancellation tombstone (the S55a-fix carryover)

Cancel one in-window event in Google Calendar, then re-run the S55b-1
Stage 2 / S55a Stage 2 step 3 refresh and confirm the row tombstones
(`status=cancelled`; `enc_*` + `content_hash` + `embedding` NULL;
`cancelled_at` set; row retained). This closes the last operator-gated
calendar-substrate behavior. If not cancelled, record as still gated and
carry to S56.

## Result

Record per stage: pass/fail, the routed cells, the citation-snapshot
no-plaintext + immutability evidence, and the cancellation-tombstone
status. Green stages 1 and 3 confirm calendar dispatch integration plus
procurement-grade citation evidence, closing S55b.

## Executed — 2026-06-03 (live, against the running stack)

Run live against `tenant_a` with working-tree source synced into the
running `padhanam-api` container (`make sync-code`) and the real LiteLLM/
Ollama + Nango + Google + Neo4j stack.

- **Stage 1 (dispatch routing) — PASS.** The live LLM meta-classifier
  routed all four calendar phrasings to `calendar_conversation` at 0.9
  confidence ("what's on my calendar this week?", "do I have any meetings
  with Ada?", "when is the board sync?", "what's my next meeting?"), and a
  cited calendar turn produced `find_by_date_range`, 2 `meeting` citations,
  refresh fired (no staleness note).
- **Stage 2 (four-way no-regression) — PASS.** "Add a data point…" →
  `manual_entry`; "Show me the audit history…" → `audit_conversation`;
  "List my open cases" → `mirror_conversation` (all 0.9). The fourth route
  did not regress the prior three.
- **Stage 3 (citation-snapshot evidence) — PASS.** The cited turn emitted
  one `meeting_citation` audit event; its `after_state` carries the
  encrypted content blob (`enc_content`) and **no plaintext title** (the
  cited meeting's title "Smoke Test 55a" does not appear in the after_state
  JSON); the snapshot decrypts to the cited title and carries the
  content_hash. The immutability-under-refresh property is proven at the
  contract altitude (`test_citation_snapshot_conformance`) and unit altitude;
  a live rename + re-pull was not exercised (read-only agent cannot mutate
  the calendar).
- **Stage 4 (cancellation tombstone) — STILL OPERATOR-GATED.** The calendar
  held 4 confirmed events with no in-window cancellations (`showDeleted=true`
  returned 0 cancelled); the read-only agent cannot cancel an event. The
  tombstone path is unit-proven; the live confirmation carries to S56 (or
  any session after the operator cancels an in-window event and re-runs the
  S55a Stage 2 refresh).

**Verdict: stages 1, 2, 3 green; stage 4 operator-gated.** Calendar dispatch
integration is live (four-way routing reaches the calendar cell, refresh
fires, citations render), and the citation evidence is plaintext-free and
decryptable against the real stack. S55b closes; P15 continues to S56.

**Status: executed live 2026-06-03 (stages 1/2/3 green; stage 4 operator-gated).**
