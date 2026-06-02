# P15 S55a — Calendar data substrate: scoped full-pull round-trip

Procedural smoke walking the calendar data substrate end-to-end against
`tenant_a` and the running self-hosted Nango: a scoped full pull through Nango
Proxy (the five verified handles), storing events as Meetings keyed on the
Google event id (upsert/tombstone), and indexing into the inherited retrieval
substrate (D148).

**Revised at S55a-fix (2026-06-02, D149).** The live Stage-1 run on 2026-06-02
falsified D148's assumption that a bounded initial sync returns `nextSyncToken`:
Google's `events.list` returns the token only on an *unbounded* sync, so a
time-bounded request (`timeMin`/`timeMax`/`orderBy`) returns events but no
token. Per D149 the calendar syncs by **scoped full pull on every refresh**
carrying `showDeleted=true` (cancellations tombstone via the `status=cancelled`
path); the incremental syncToken/410 machinery is built but dormant. Stage 1
below now asserts *no* token is expected; Stage 2 is the refresh path (idempotent
re-pull + cancellation tombstone), and the bogus-token→410 check has moved from a
live stage to the dormant-path unit test `test_410_raises_sync_token_expired`.

**Procedural** — the operator executes the stages below live. The build
environment cannot reach docker, the public internet, Nango, or Google, so
the round-trip is operator-executed (mirroring the S45/S46/S47/S53/S54 and
the Nango-provisioning precedent). Record evidence inline.

## Prerequisites (executed at smoke-open)

- **Nango provisioning green** (the gate that started S55): the Nango
  bring-up-and-verify runbook (`docs/runbooks/nango-self-hosted.md`) passed
  stage 6 — an active Google Calendar connection plus a `200` from the Proxy
  `events.list` call. Verified handles: env id 2; provider-config-key
  `google-calendar`; connection id `d46195b2-ad85-4d1c-a876-b978b9347ccd`;
  proxy base `/proxy/calendar/v3/...`; scope `calendar.readonly`. Auth is
  `Authorization: Bearer <secret_key>` — Nango 0.70.5 rejects HTTP Basic on the
  Proxy with a misleading `not a UUID v4` error even for a valid key, so Bearer
  is required (the adapter sends Bearer; pinned by `test_proxy_auth_is_bearer_not_basic`).
- **Migration 0026 applied** to BOTH tenant synthetic databases:
  `docker compose exec padhanam-api alembic -c alembic/tenant/alembic.ini upgrade head`
  (per-tenant per the two-plane migration convention). Verify:
  `\d meetings` shows the `ux_meetings_tenant_event` UNIQUE constraint, the
  `meetings_status_check` CHECK, and the `embedding` column typed `vector(768)`
  with the `meetings_embedding_hnsw_idx` index; `\d connections` shows
  `ux_connections_tenant_provider_config`. (The `connections.sync_token` column
  remains in the schema but is dormant per D149.)
- **`.env` configured** (the calendar-context consumer side, D148 /
  CalendarSettings):
  - `NANGO_BASE_URL` — the URL Padhanam uses to reach Nango Proxy. **Inside the
    `padhanam-api` container this is the compose service name `http://nango-server:3003`,
    not `localhost`** (localhost would not resolve to the Nango container).
  - `NANGO_SECRET_KEY` — the Nango dashboard secret key for env id 2 (the Proxy
    bearer token; read from the nango db / dashboard at runbook stage 3).
- `padhanam-api` rebuilt if the image predates this session
  (`make build-api`; `docker compose up -d --force-recreate padhanam-api`). The
  `NANGO_BASE_URL`/`NANGO_SECRET_KEY` env passthrough into the `padhanam-api`
  service is committed in `compose.yaml` (S55a-fix).

> S55a deliberately ships no HTTP/CLI sync surface — the cross-context
> composition that drives sync from a user turn lands at S55b (the calendar
> conversation). The round-trip below is exercised through a
> `docker compose exec padhanam-api python` shell, which is sufficient to
> verify the verified-handles pull and the store, and is the honest minimum
> for the operator live-verification gate.

## Stage 1 — Verified-handles full pull (the load-bearing round-trip)

Confirm the calendar adapter pulls real events through the running Nango,
proving the verified handles + Bearer auth + request shape against live Google
Calendar. In a `docker compose exec padhanam-api python` shell:

```python
import asyncio, time
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from padhanam.config import CalendarSettings
from contexts.calendar.domain.connection import Connection
from contexts.calendar.adapters.outbound.nango.nango_proxy_calendar_adapter import (
    NangoProxyCalendarAdapter,
)

s = CalendarSettings()
conn = Connection(
    id=uuid4(),
    tenant_id=uuid4(),
    jurisdiction="eu-west",
    provider="google_calendar",
    provider_config_key="google-calendar",
    provider_connection_ref="d46195b2-ad85-4d1c-a876-b978b9347ccd",
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
)
adapter = NangoProxyCalendarAdapter(base_url=s.nango_base_url, secret_key=s.nango_secret_key)
now = datetime.now(timezone.utc)
t0 = time.perf_counter()
page = asyncio.run(
    adapter.list_events_full(
        connection=conn,
        time_min=now - timedelta(days=30),
        time_max=now + timedelta(days=90),
    )  # show_deleted defaults True
)
dt = time.perf_counter() - t0
print("events:", len(page.events))
print("next_sync_token present:", page.next_sync_token is not None)  # expect False (D149)
print(f"ROUND-TRIP LATENCY: {dt*1000:.0f} ms")
for e in page.events[:3]:
    print(e.google_event_id, e.status, e.summary, e.start)
```

**Expected:** a non-empty (or at least error-free) `events` list pulled from
the operator's real calendar, and **`next_sync_token present: False`** — a
bounded full pull returns no token (D149); this is correct, not a failure. A
clean return here proves Bearer auth + Proxy + the verified handles + the
events.list request shape work end-to-end against real Google Calendar.

**Record:** the event count, that **no** sync token was returned (D149), and
the **measured round-trip latency** (the `time.perf_counter()` delta) — the
local→Nango→Google→back floor S55b's refresh-before-answer tiering budgets
against (D122). The S55a-fix authoring baseline measured **376 ms** for 3 events;
record the re-measured number and whether it holds at ~376 ms.

## Stage 2 — Refresh idempotency + cancellation tombstone (the full-pull refresh path)

Confirm the scoped full pull is an idempotent refresh: a re-run with no calendar
change is a no-op upsert (same ids, no `changed_event_ids`), and a cancelled
event tombstones via the full pull's `showDeleted=true`. Using `tenant_a`'s
session factory (the same per-tenant resolver the API composition root builds),
construct `PostgresConnectionRepository` + `PostgresMeetingStore` bound to
`tenant_a`, save a Connection, then run `sync_calendar` (store-only; the
embedder/graph ports are wired at S55b):

```python
# (sketch — uses tenant_a's bound session factory + the two Postgres adapters)
r1 = asyncio.run(sync_calendar(tenant_context=ctx_a, connection_id=conn_id,
        trigger=CalendarSyncTrigger.POLL, event_source=adapter,
        connections=conn_repo, meetings=store, meeting_reader=store))
print("run 1:", r1.mode, r1.fetched, r1.upserted, r1.tombstoned, len(r1.changed_event_ids))
r2 = asyncio.run(sync_calendar(...same args...))
print("run 2 (no change):", r2.upserted, "changed:", len(r2.changed_event_ids))  # changed == 0
```

Then, in Google Calendar, **cancel one event inside the 30-day-back/90-day-forward
window** and re-run `sync_calendar`. The cancelled event returns with
`status=cancelled` (via `showDeleted=true`) and tombstones:

```python
r3 = asyncio.run(sync_calendar(...same args...))
print("run 3 (one cancellation):", r3.tombstoned)  # expect >= 1
```

**Record:** that run 2 reports `changed_event_ids == 0` (idempotent refresh; same
`content_hash`), `mode == "full"` on every run, and that run 3 tombstones the
cancelled event. (The bogus-token→410 check is no longer a live stage; it is
covered by the dormant-path unit test `test_410_raises_sync_token_expired`.)

## Stage 3 — Store round-trip (Meeting encryption + tombstone at rest)

Inspect the `tenant_a` `meetings` rows produced by Stage 2 and confirm:

- the rows landed keyed on `google_event_id`, content encrypted (the `enc_*`
  columns are populated, no plaintext title/description/location in the row —
  cross-check with the `test_no_plaintext_in_state` enforcement expectation);
- the run-2 no-op left ids and `content_hash` unchanged, and `connections.sync_token`
  remains NULL (dormant; never written on the active path, D149);
- the cancelled event from run 3 tombstoned (status `cancelled`; `enc_*` +
  `content_hash` + `embedding` NULL; `cancelled_at` set), leaving the row.

**Record:** the upserted/tombstoned counts and that the stored content is
encrypted at rest (P3 envelope encryption, D21).

## Stage 4 — Index round-trip (optional, needs Ollama + Neo4j)

If the operator wants to exercise the inherited indexing substrate before
S55b wires it into the app, construct the embedding + graph bridges over
ingestion's `LiteLLMChunkEmbedder` and `Neo4jGraphRepository` and pass them
to `sync_calendar(..., embedder=..., graph_index=...)`. Confirm the
`meetings.embedding` column is populated for changed events and that
`:Entity` Person/Place nodes plus relationships appear in Neo4j scoped to
`tenant_a`. (This is forward-exercise; the load-bearing S55a verification is
stages 1–3. The bridge adapters land at S55b.)

## Result

Record per stage: pass/fail, the event count and measured latency floor
(stage 1, expecting **no** sync token per D149), the refresh idempotency +
cancellation tombstone (stage 2), the store + encryption evidence (stage 3),
and optionally the index evidence (stage 4). Green stages 1–3 confirm the
calendar data substrate pulls (scoped full, Bearer auth), stores (encrypted,
keyed, upsert/tombstone), and refreshes idempotently against the real running
Nango — without any dependency on a sync token.

**Status: pending operator execution after S55a-fix** (the build environment
cannot reach docker, Nango, or Google; recorded per the procedural-then-executed
precedent). **S55b opens only after the operator re-runs stages 1–3 green** on
the corrected full-pull substrate.
