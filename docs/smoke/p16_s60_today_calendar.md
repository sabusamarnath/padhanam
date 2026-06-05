# P16 / S60 — Calendar items in the Today surface + the Connections page (procedural smoke)

The Today surface becomes the whole-life driver (D159): the operator's
**real calendar** events render in one list alongside OPEN Cases and
Commitments, typed by domain, and a calendar item opens into the
**calendar-conversation cell** over the same HTTP-cell path as the Case
cell. **This slice is the Phase 2-A dogfooding entry point** — the
week-of-use restraint gate (D156) runs against the artefact this smoke
brings up, on the operator's real calendar, not a seeded demo.

This smoke is **operator-driven and operator-gated** (AC8): the build
environment cannot reach docker, Nango, Google, or a browser, and per the
CLAUDE.md discipline a UI acceptance criterion is met by **browser
interactive verification**, not CLI smoke. Two prerequisites are
operator-only and are why AC8 is gated (the S56a precedent):

1. **google-calendar is OAuth-provisioned for the personal tenant.** The
   dogfood-setup chore provisioned the personal tenant's *database
   connection*, not a google-calendar Connection — so the operator
   connects the calendar at runtime (Stage 1).
2. **A live model credential** for the conversation turn: gpt-4o-mini (the
   personal stack's global tier default), **not** the qwen fallback.

Personal tenant: `00000000-0000-4000-8000-00000000d001`
(tag `dogfood-stable`).

---

## Stage 0 — bring the code up

```bash
make sync-code            # copy contexts/apps/etc into the api container
# (or `make build-api && docker compose up -d --force-recreate padhanam-api`
#  for the production-shaped image path — required for the FastAPI server to
#  pick up the new connections router + the rebuilt static pages, since the
#  server imports at boot and serves the static files from the image)
```

**No migration this session** — the calendar today-item is read-through
(no daily-driver table), and the calendar-to-domain tag is config-resolved
(`CalendarSettings.calendar_domain_tag`, default `work`; no calendar-context
migration). Confirm the new routes are mounted:

```bash
docker compose exec padhanam-api python -c \
 "import apps.api.routers.connections as c; \
  print([r.path for r in c.router.routes] + [r.path for r in c.ui_router.routes])"
```

Expect `/api/v1/connections` and `/connections`.

## Stage 1 — connect the operator's real Google Calendar (operator-gated)

Provision a `google-calendar` Connection for the **personal tenant** via
the self-hosted Nango connect flow (the same path tenant_a used at the
S55a smoke). Confirm a row exists:

```bash
docker compose exec postgres-tenant-personal psql -U tenant_personal -d tenant_personal -c \
 "select provider_config_key, left(provider_connection_ref, 8) from connections \
  where provider_config_key = 'google-calendar';"
```

Then seed the meetings store so the Today list has rows immediately. The
Today list reads the **cached meeting store** (the `CalendarEventsReader`
does not refresh on list — unlike the calendar-conversation cell, which
refreshes before answering, D150; a refresh-on-list is a named refinement,
below). Drive a pull through the wired refresh adapter:

```bash
docker compose exec padhanam-api python -c \
 "import asyncio; \
  from apps.cli._calendar import build_calendar_refresh_adapter; \
  from apps.cli._runtime import build_tenant_wiring; \
  import sqlalchemy as sa; \
  from contexts.calendar.adapters.outbound.postgres._tables import connections as t; \
  tid='00000000-0000-4000-8000-00000000d001'; \
  w=build_tenant_wiring(tid); \
  async def run(): \
    async with w.session_factory() as s: \
      cid=(await s.execute(sa.select(t.c.id).where(t.c.provider_config_key=='google-calendar'))).first()[0]; \
    await build_calendar_refresh_adapter(tenant_id=tid, connection_id=cid).refresh(tenant_context=w.tenant_context); \
  asyncio.run(run())"
```

Confirm at least one meeting with a **today** start exists:

```bash
docker compose exec postgres-tenant-personal psql -U tenant_personal -d tenant_personal -c \
 "select left(title,40), start_at from meetings \
  where start_at::date = current_date and status <> 'cancelled' order by start_at;"
```

## Stage 2 — confirm the live model credential (operator-gated)

The conversation turn calls the cell's REAL_TIME intent extraction. Confirm
the personal stack's inference is **gpt-4o-mini**, not the qwen fallback
(the OpenAI key is set in the personal api container's environment). A
spurious-clarification storm or an obviously-degraded answer at Stage 4 is
the tell that the fallback is in play.

## Stage 3 — the Connections page (browser, AC5)

```bash
docker compose exec padhanam-api python -c \
 "from padhanam.security.auth import issue_dev_token; \
  print(issue_dev_token(subject='operator', \
  tenant_id='00000000-0000-4000-8000-00000000d001', roles=['operator']))"
```

Open `https://localhost/connections`, paste the dev token, **Use token**.
Confirm:

- The **Google Calendar** row shows **Connected** with the green badge.
- The **read-only** posture is visible (the `calendar.readonly` scope /
  read-only badge per D148).
- The **calendars-to-include** manage panel shows the primary calendar with
  the **domain tag** (`work` by default; design-language §9).
- **Gmail** and **Google Drive** render as connectable but carry the
  "connectable — not yet wired into the Today list" note (§9; D159 scopes
  email-into-list to S61).

## Stage 4 — the Today surface on real calendar data (browser, AC1–4, AC8)

Open `https://localhost/app`, paste the dev token, **Use token**. Confirm:

1. **AC1** — today's **real calendar events** render in the one list
   alongside any OPEN Cases and Commitments, typed by domain.
2. **AC2/AC3** — each calendar event renders with the three-channel
   identity (icon = category, colour = tier) and a shared status pill; the
   surface matches the design language (domain surfaces, legend, the
   right-fixed drawer, the dark/light theme toggle, the domain-cue toggle).
3. **AC4 / AC8** — click a calendar event: the drawer opens the
   **calendar-conversation cell**, the opening turn answers on the **real
   event** (gpt-4o-mini), a follow-up turn round-trips, and the reply
   renders **source-typed citation chips** (`meeting …`). No raw UUID on
   the surface.

Then the felt-quality read (reflection 3): with the real calendar in the
list, does the surface read as the whole-life driver D156 describes, or as
a calendar clone with extra rows? Record the **first honest read** in the
session-log close.

## Stage 5 — tenant isolation spot-check (AC6)

With a second tenant's dev token, `GET /api/v1/connections` and
`GET /api/v1/daily-driver/today` return **only that tenant's** state — no
personal-tenant events leak. (The calendar reader is bound-tenant; the
unit isolation harness covers the invariant structurally.)

---

## Outcome (fill at close)

- Stage 0 routes mounted: ____
- Stage 1 calendar connected + today's meetings present: ____
- Stage 2 gpt-4o-mini live (not qwen): ____
- Stage 3 Connections page (connect/connected, read-only, manage panel + tag, mail/Drive connectable): ____
- Stage 4 Today surface — real events in list, domain typing, calendar drawer turn + citation chips: ____
- Stage 5 tenant isolation: ____
- Felt-quality first read (reflection 3): ____
- Any gap → forward correction in the S58/S59 shape: ____
