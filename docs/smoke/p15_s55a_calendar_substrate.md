# P15 S55a — Calendar data substrate: pull-store-sync-index round-trip

Procedural smoke walking the calendar data substrate end-to-end against
`tenant_a` and the running self-hosted Nango: a scoped pull through Nango
Proxy (the five verified handles), storing events as Meetings keyed on the
Google event id (upsert/tombstone), self-driven sync tokens, and indexing
into the inherited retrieval substrate (D148).

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
  proxy base `/proxy/calendar/v3/...`; scope `calendar.readonly`.
- **Migration 0026 applied** to BOTH tenant synthetic databases:
  `docker compose exec padhanam-api alembic -c alembic/tenant/alembic.ini upgrade head`
  (per-tenant per the two-plane migration convention). Verify:
  `\d meetings` shows the `ux_meetings_tenant_event` UNIQUE constraint, the
  `meetings_status_check` CHECK, and the `embedding` column typed `vector(768)`
  with the `meetings_embedding_hnsw_idx` index; `\d connections` shows
  `ux_connections_tenant_provider_config`.
- **`.env` configured** (the calendar-context consumer side, D148 /
  CalendarSettings):
  - `NANGO_BASE_URL` — the URL Padhanam uses to reach Nango Proxy (dev:
    `http://localhost:3003`).
  - `NANGO_SECRET_KEY` — the Nango dashboard secret key (the Proxy bearer
    token; read from the dashboard at runbook stage 3).
- `padhanam-api` rebuilt if the image predates this session
  (`make build-api`; `docker compose up -d --force-recreate padhanam-api`).

> S55a deliberately ships no HTTP/CLI sync surface — the cross-context
> composition that drives sync from a user turn lands at S55b (the calendar
> conversation). The round-trip below is exercised through a
> `docker compose exec padhanam-api python` shell, which is sufficient to
> verify the verified-handles pull and the store, and is the honest minimum
> for the operator live-verification gate.

## Stage 1 — Verified-handles pull (the load-bearing round-trip)

Confirm the calendar adapter pulls real events through the running Nango,
proving the verified handles + headers + request shape against live Google
Calendar. In a `docker compose exec padhanam-api python` shell:

```python
import asyncio
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
page = asyncio.run(
    adapter.list_events_full(
        connection=conn,
        time_min=now - timedelta(days=30),
        time_max=now + timedelta(days=90),
    )
)
print("events:", len(page.events))
print("next_sync_token present:", page.next_sync_token is not None)
for e in page.events[:3]:
    print(e.google_event_id, e.status, e.summary, e.start)
```

**Expected:** a non-empty (or at least error-free) `events` list pulled from
the operator's real calendar, and `next_sync_token present: True`. A clean
return here proves Auth + Proxy + the verified handles + the events.list
request shape work end-to-end against real Google Calendar.

**Record:** the event count, that a sync token was returned, and the
**measured round-trip latency** (wrap the `asyncio.run(...)` in
`time.perf_counter()` deltas) — the local→Nango→Google→back floor S55b's
refresh-before-answer tiering budgets against (D122). Record the number.

## Stage 2 — Incremental sync + the 410 path (no live Google needed)

Confirm the syncToken-only incremental request shape and the
`SyncTokenExpiredError` mapping. A second `list_events_incremental` call with
the `next_sync_token` from stage 1 should return only changes (likely an
empty `items` plus a fresh `nextSyncToken`). Passing a deliberately bogus
token should surface a `410` → `SyncTokenExpiredError`:

```python
from contexts.calendar.domain.errors import SyncTokenExpiredError
try:
    asyncio.run(adapter.list_events_incremental(connection=conn, sync_token="BOGUS_STALE_TOKEN"))
    print("UNEXPECTED: no 410")
except SyncTokenExpiredError:
    print("410 -> SyncTokenExpiredError OK (full resync path)")
```

**Record:** that incremental returns deltas and that a stale token raises
`SyncTokenExpiredError`.

## Stage 3 — Store round-trip (Meeting upsert + tombstone + encryption)

Using `tenant_a`'s session factory (the same per-tenant resolver the API
composition root builds), construct `PostgresConnectionRepository` +
`PostgresMeetingStore` bound to `tenant_a`, save a Connection, then run
`sync_calendar` (store-only; the embedder/graph ports are wired at S55b).
Confirm:

- the `meetings` rows landed keyed on `google_event_id`, content encrypted
  (the `enc_*` columns are populated, no plaintext title/description/location
  in the row — cross-check with the `test_no_plaintext_in_state` enforcement
  expectation);
- a re-run with no calendar change is a no-op upsert (same ids, same
  `content_hash`), and `connections.sync_token` advanced;
- a cancelled event tombstones (status `cancelled`, `enc_*` + `content_hash`
  + `embedding` NULL, `cancelled_at` set), leaving the row.

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
(stage 1), the 410 mapping (stage 2), the store + encryption evidence
(stage 3), and optionally the index evidence (stage 4). A green stages 1–3
confirm the calendar data substrate pulls, stores (encrypted, keyed,
upsert/tombstone), and syncs against the real running Nango.

**Status: pending operator execution** (the build environment cannot reach
docker, Nango, or Google; recorded per the procedural-then-executed
precedent).
