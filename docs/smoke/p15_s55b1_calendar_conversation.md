# P15 S55b-1 — Calendar conversation surface: end-to-end + refresh fallback

Procedural smoke for the calendar conversation surface (S55b-1, the first
of the S55b split): the `calendar_conversation` cell classifies a calendar
intent, refreshes the calendar within the D150 tier budget, queries the
Meeting store, and returns a cited response — exercised directly (not via
MetaClassifier; dispatch is S55b-2). Also closes the S55a-fix residue: it
**rebuilds the baked image first** so the calendar fix is verified in the
artifact, not just synced source.

**Procedural** — the operator executes the stages below live. The build
environment cannot reach docker/Nango/Google/Ollama as a standing
guarantee, so this is recorded per the procedural-then-executed precedent
(S45/S46/S47/S53/S54/S55a). Record evidence inline. **S55b-2 opens only
after stages 1 and 3 run green.**

## Prerequisites

- **Rebuild the baked image first** (retires the S55a-fix synced-source
  residue — see `log/captures.md` 2026-06-02 [S55b-1]):
  `make build-api && docker compose up -d --force-recreate padhanam-api`.
- Nango provisioning green and `.env` configured per the S55a smoke
  (`NANGO_BASE_URL=http://nango-server:3003` inside the container;
  `NANGO_SECRET_KEY` the dev env-2 secret; Bearer auth).
- Migration 0026 applied to `tenant_a`; the Meeting store reachable.
- Ollama up (the cell's intent classification calls the real LLM through
  the StructuredOutputPort at REAL_TIME_REQUIRED) and Neo4j up (indexing).

## Stage 1 — Baked-image calendar pull re-confirm (closes the S55a-fix residue)

Re-run the S55a Stage 1 scoped full pull **against the rebuilt image** to
confirm the D149 fix is in the artifact, not just synced source. In a
`docker compose exec padhanam-api python` shell, run the S55a smoke's
Stage 1 snippet (scoped full pull, `show_deleted` default True).

**Expected:** events returned, `next_sync_token is None: True`, and the
round-trip latency recorded fresh against the ~340–400 ms steady /
~513 ms cold S55a-fix baseline. **Record** the latency and that no token
was returned.

## Stage 2 — Cancellation tombstone (operator-gated; closes the S55a-fix sub-step)

If the operator has cancelled an in-window event since S55a-fix, re-run
the S55a Stage 2 refresh and confirm the cancelled event tombstones
(status `cancelled`; `enc_*` + `content_hash` + `embedding` NULL;
`cancelled_at` set; row retained). If no event was cancelled, record this
sub-step as **still operator-gated** (the build agent cannot mutate the
`calendar.readonly` calendar; the tombstone path is unit-proven at
`test_cancelled_event_is_tombstoned_via_full_pull`).

## Stage 3 — Calendar conversation end-to-end

Invoke the `CalendarConversationCell` directly against `tenant_a` with a
real StructuredOutputPort (LiteLLM), the refresh adapter from
`apps.cli._calendar.build_calendar_refresh_adapter`, and the `tenant_a`
Meeting store as the reader. Drive a calendar question, e.g. "what's on my
calendar this week?". Confirm:

- the refresh fires (the D150 scoped full pull runs at turn-open; the
  Meeting store is fresh);
- the cell classifies the intent (high confidence → query);
- a `CalendarConversationResponse` renders with `meeting`-discriminated
  `ArtefactCitation`s for the meetings surfaced (or a clean "no meetings"
  if the window is empty);
- `render_for_whatsapp` produces the citation line.

**Record** the classified intent class, the meetings cited, and that the
refresh fired (no staleness note on the happy path).

## Stage 4 — Refresh fallback

Stop Nango (`docker compose stop nango-server`), re-run the same turn, and
confirm the cell serves the **cached** Meeting store with the staleness
note ("Showing your cached calendar — the live refresh ...") and does not
fail the turn (D150 Option A). Restart Nango
(`docker compose start nango-server`).

**Record** the staleness note text and that the turn still answered from
the cache.

## Result

Record per stage: pass/fail, the Stage 1 baked-image latency + no-token
confirmation, the Stage 2 cancellation status (tombstoned or operator-
gated), the Stage 3 classified intent + citations + refresh-fired, and the
Stage 4 staleness-note fallback. Green stages 1 and 3 confirm the calendar
conversation surface answers from a freshly-refreshed Meeting store with
meeting citations, and the fix is in the baked artifact.

**Status: pending operator execution** (build environment cannot reach
docker/Nango/Google/Ollama as a standing guarantee). S55b-2 opens after
the operator runs stages 1 and 3 green.
