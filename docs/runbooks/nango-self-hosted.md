# Nango self-hosted — bring-up and verify runbook

Brings up the Nango self-hosted service that the calendar build (S55) and the
email build (S56) consume over HTTP per D14, and verifies it end-to-end with a
real Google Calendar connection. Nango provisioning is **the gate that starts
S55**: S55 does not begin until the verify stage below succeeds and the
operator reports back.

**Procedural** — the operator executes the stages below on the host. The build
environment cannot reach docker, the public internet for OAuth, or Google, so
the steps are run live (mirroring the S45/S46/S47/S53/S54 smoke precedent). The
compose service, image pins, ports, and env were reconciled against the
upstream `NangoHQ/nango` compose and Docker Hub on 2026-05-28; the Nango
dashboard UI evolves between versions, so where a step depends on the exact
click-path, the **current Nango docs are authoritative** and this runbook gives
the shape plus the values that are stable.

## Scope and constraints

- **Free self-hosting is Auth + Proxy only.** Syncs, Functions, Actions, and
  Webhooks are Enterprise. The calendar plan is deliberately pull-on-demand via
  Proxy and stays inside this scope (see the 2026-05-28 calendar-retrieval-design
  captures entry and `charter/deferred-decisions.md` "Calendar tool service").
  If a future need wants background Syncs or Functions, that is a tier change to
  surface, not a config tweak.
- **Image is `linux/amd64` only.** On Apple Silicon / ARM it runs under
  emulation (slower start, higher memory). The compose carries the
  `platform: linux/amd64` directive; expect a longer `start_period` on first
  boot.
- **Loopback-only host bindings.** The dashboard (`SERVER_PORT`, default 3003)
  and the Connect UI (`CONNECT_UI_PORT`, default 3009) bind `127.0.0.1` only —
  the S5-rule dev exception, same shape as `postgres-control-plane` and
  `padhanam-api`. They are reachable from the operator's browser on the host,
  not from the network. Production removes these bindings.

## Prerequisites

1. **Env filled.** In `.env` (copied from `.env.example`):
   - Generate the encryption key once and paste it in. Rotation is not
     supported, so set it before first bring-up and never change it:
     ```
     openssl rand -base64 32
     ```
     ```
     NANGO_ENCRYPTION_KEY=<the base64 value above>
     ```
   - Set a real `NANGO_DASHBOARD_PASSWORD` (the username defaults to `admin`).
   - Leave `SERVER_PORT=3003`, `CONNECT_UI_PORT=3009`, and the
     `NANGO_SERVER_URL` / `NANGO_PUBLIC_SERVER_URL` at `http://localhost:3003`
     unless a port collides on the host.
2. **Google Cloud project.** Enable the Google Calendar API, and create an OAuth
   2.0 client of type **Web application**. You will need its client ID and
   client secret in stage 4. Keep the OAuth consent screen in testing mode and
   add your own Google account as a test user.

## Stage 1 — Bring up

```
docker compose up -d nango-db nango-server
```

`nango-db` must reach `healthy` before `nango-server` starts (the compose
`depends_on` enforces this). On Apple Silicon the first boot can take a minute
or two under emulation.

## Stage 2 — Health check

```
docker compose ps nango-server
```
Expect `STATUS` to show `healthy`. The compose healthcheck is a path-independent
TCP-connect to `SERVER_PORT`, which is exactly what the port gotcha (below)
breaks. Then confirm the HTTP surface from the host:

```
curl -i http://localhost:3003/health
```
Expect `HTTP/1.1 200`. If you get **connection refused**, the port gotcha is the
first suspect — see Troubleshooting.

## Stage 3 — Dashboard access

Open `http://localhost:3003` in the browser. Authenticate with Basic Auth using
`NANGO_DASHBOARD_USERNAME` / `NANGO_DASHBOARD_PASSWORD` from `.env`
(`FLAG_AUTH_ENABLED=true`). Note the **secret key** the dashboard shows for API
access — you need it for the Proxy verification in stage 6.

## Stage 4 — Configure the Google Calendar integration

In the dashboard, create an **Integration** for the Google Calendar provider and
supply:
- the Google OAuth **client ID** and **client secret** from the prerequisite
  Google Cloud project;
- the scope `https://www.googleapis.com/auth/calendar.readonly` (read-only is
  the assumption the calendar design commits; a write scope is a separate,
  larger bidirectional design that must be flagged).

Then register the callback in Google Cloud Console. Under the OAuth client's
**Authorized redirect URIs**, add exactly:
```
http://localhost:3003/oauth/callback
```
(this is `<NANGO_SERVER_URL>/oauth/callback`). Google permits `http://localhost`
redirect URIs for testing OAuth clients, so no tunnel or HTTPS is required for
dev.

> The exact dashboard field labels for adding an integration and its scopes
> change between Nango versions. Follow the current Nango "configure an
> integration" docs for the precise click-path; the values above (provider,
> scope, callback URL) are what matter and are stable.

## Stage 5 — Establish a test connection

Open the Connect UI at `http://localhost:3009` (or use the dashboard's add-a-
connection flow). Start the Google Calendar connection, complete the Google
consent screen with your test-user account, and let Google redirect back to the
`/oauth/callback` URL registered in stage 4. Give the connection a memorable
**connection ID** (you supply or read it here).

## Stage 6 — Confirm the token is stored (the S55 gate)

1. In the dashboard, the new connection should list as **active**, with a stored
   access/refresh token and the Google account shown.
2. Prove Proxy works end-to-end — this is the live verification S55's calendar
   adapter depends on. Through the Nango Proxy, list a few events from the
   primary calendar:
   ```
   curl -i "http://localhost:3003/proxy/calendar/v3/calendars/primary/events?maxResults=1" \
     -H "Authorization: Bearer <dashboard secret key from stage 3>" \
     -H "Provider-Config-Key: <the integration id from stage 4>" \
     -H "Connection-Id: <the connection id from stage 5>"
   ```
   Expect `HTTP/1.1 200` with a JSON `items` array. A 200 here means Auth +
   Proxy are working against real Google Calendar through Nango, which is the
   substrate S55 builds the calendar HTTP adapter against.

   > Header names and the proxy path prefix are Nango Proxy API, stable across
   > versions, but confirm against the current Nango Proxy docs if a header is
   > rejected.

3. **Report back.** A green stage 6 (active connection + a 200 from the Proxy
   list call) is the gate that starts S55. Record the integration id and the
   connection id; S55's brief references them.

## Troubleshooting

- **`connection refused` / `curl` fails on 3003 (the port gotcha, NangoHQ/nango
  issue #5305, 2026-01-24).** The published image bakes `PORT=8080` and resolves
  `SERVER_PORT → PORT → 3003`. If `SERVER_PORT` is not set in the container, the
  server listens on 8080 while only 3003 is published, so it is unreachable. The
  compose sets `SERVER_PORT` explicitly so the listen port matches the published
  port. Confirm `SERVER_PORT=3003` is in `.env` and `docker compose config`
  shows `SERVER_PORT: "3003"` under `nango-server`.
- **OAuth redirect mismatch.** The redirect URI registered in Google Cloud
  Console must match `<NANGO_SERVER_URL>/oauth/callback` exactly, including
  scheme and port.
- **Slow first boot on Apple Silicon.** Expected under amd64 emulation; the
  healthcheck `start_period` allows for it. If it never goes healthy, check
  `docker compose logs nango-server` for a DB connection error (verify
  `nango-db` is healthy and the `NANGO_DB_*` values match).
- **Logs.** `NANGO_LOGS_ENABLED=false`, so logs go to stdout
  (`docker compose logs nango-server`); Elasticsearch is intentionally not run.
