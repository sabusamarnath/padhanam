# P16 / S60b — Live e2e: sign in, connect a real calendar, see it on Today (procedural smoke)

S60b completes S60's surface to a live loop (D160): sign in through a real
login, connect the operator's real calendar, and run the daily driver on
live data inside the app shell — then move or cancel a meeting and confirm
the surface reflects it after refresh (the live-change dynamic a static
seed cannot test). **Gate-enabling, not a new value surface.**

Operator-driven and operator-gated (AC7). Two seams are operator-gated by
construction (the build environment cannot reach Google, Nango, or a
browser, and per the S55a-fix discipline their vendor contracts are
reconciled here, not asserted from memory):

- **Sign-in.** The dev login (a passphrase) is wired and closes the
  paste-token backdoor; the Google one-tap path (§9) is operator-gated.
- **Connect.** The connect callback + first-sync are wired; the Nango
  connect-session **initiate** is operator-gated. The fallback is the Nango
  self-hosted runbook (`docs/runbooks/nango-self-hosted.md`) + the callback.

Personal tenant: `00000000-0000-4000-8000-00000000d001` (tag `dogfood-stable`).

---

## Stage 0 — bring the code up

```bash
make sync-code   # or build-api + recreate for the boot-time router/static pickup
```

No migration (the connections + meetings tables exist from S55a). Confirm
the new routes are mounted:

```bash
docker compose exec padhanam-api python -c \
 "import apps.api.routers.auth as a, apps.api.routers.connections as c; \
  print([r.path for r in a.router.routes] + [r.path for r in a.ui_router.routes]); \
  print([r.path for r in c.router.routes])"
```

Expect `/api/v1/auth/login`, `/`, `/login`, and the connections routes
including `/api/v1/connections/calendar/initiate` and `.../callback`.

## Stage 1 — sign in (AC1)

Set the dogfooding login passphrase in the personal `padhanam-api`
environment (`SecuritySettings.dev_login_passphrase`, default `dev`; set a
real value for the operator's stack) and confirm `dev_login_tenant_id` is
the personal tenant. Then open `https://localhost/` — the **login page**,
not `/app`. Enter the passphrase, **Continue**. Confirm you land in the
**app shell** (the rail + Today), and that `/app` no longer prompts for a
pasted token. Signing out (the account block) returns to `/login`.

> Google one-tap is operator-gated: wire the Google ID-token verifier +
> email→tenant resolver and set `login_backend=google` to exercise it;
> reconcile Google's token contract at this stage. Until then the
> passphrase is the dogfooding entry.

## Stage 2 — the shell + honest placeholders (AC2)

In the shell, confirm Today renders live and the other rail items
(Week, How am I doing, Journal, Map & Flow, Settings) render **honest
placeholders** naming where they land — not dead links. **Connections** is
a live nav item to the Connections page.

## Stage 3 — connect the real calendar (AC3, AC4)

On the Connections page, click **Connect** on Google Calendar.

- **If the Nango initiate is wired** (operator wired the connect-session
  creator): the connect URL opens; complete the Google consent (add your
  Google account as a test user if the consent screen is in testing mode),
  then paste the issued connection reference when prompted.
- **If operator-gated (503):** connect via the Nango self-hosted runbook
  out of band, then paste the issued **connection reference** when prompted.

The callback stores the per-tenant `Connection` and triggers the first
`sync_calendar` pull. Confirm the row + today's meetings:

```bash
docker compose exec postgres-tenant-personal psql -U tenant_personal -d tenant_personal -c \
 "select provider_config_key, left(provider_connection_ref,8) from connections where provider_config_key='google-calendar';"
docker compose exec postgres-tenant-personal psql -U tenant_personal -d tenant_personal -c \
 "select left(title,40), start_at from meetings where start_at::date = current_date and status<>'cancelled' order by start_at;"
```

Back on **Today**, confirm live calendar events render in the list, typed
by domain, and open one into the calendar-conversation cell (the S60
drawer; gpt-4o-mini, not the qwen fallback).

## Stage 4 — the live-change dynamic + isolation (AC4, AC5)

Move or cancel a meeting in your real Google Calendar, then trigger a
refresh (open a calendar item — the conversation cell refreshes before
answering, D150 — or re-run the seed pull from the S60 smoke) and confirm
**Today reflects the change** (a moved meeting re-times; a cancelled one
leaves the list). Then with a second tenant's token, `GET /api/v1/connections`
and `/api/v1/daily-driver/today` show **only that tenant's** state — the
personal connection and events do not leak (AC5; bound-tenant).

---

## Outcome (fill at close)

- Stage 0 routes mounted: ____
- Stage 1 sign in → shell, /app backdoor closed: ____
- Stage 2 shell + honest placeholders, Connections live: ____
- Stage 3 connect (wired initiate / runbook fallback) → connection stored → live events on Today: ____
- Stage 4 live-change reflected after refresh; tenant isolation holds: ____
- e2e felt-quality first read (reflection 3): ____
- Day-one read (reflection 4) — explicitly NOT the restraint verdict: ____
- Any gap → forward correction in the S58/S59 shape: ____
