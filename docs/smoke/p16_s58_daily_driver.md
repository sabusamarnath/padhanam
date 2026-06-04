# P16 / S58 — Daily-driver first slice (procedural smoke)

The first operator-facing daily-driver surface (D157). This smoke is
**operator-driven against the live stack**: the build environment cannot
reach docker, and per the CLAUDE.md discipline a UI acceptance criterion
is met by **browser interactive verification**, not CLI smoke. Run the
stages below against the running Compose stack and record the outcome in
the session-log close.

Tenant: `tenant_a` = `00000000-0000-4000-8000-00000000a001`
(jurisdiction `eu-west`).

---

## Stage 0 — bring the code and schema up

```bash
make sync-code            # fast-path: copy contexts/apps/etc into the api container
# (or `make build-api && docker compose up -d --force-recreate padhanam-api`
#  for the production-shaped image path — required for the FastAPI server to
#  pick up the new /app route and routers, since the server imports at boot)
make migrate              # applies 0028_daily_driver_substrate to each tenant DB
```

Verify the three tables landed on tenant_a:

```bash
docker compose exec postgres-tenant-a \
  psql -U tenant_a -d tenant_a -c "\dt commitments|commitment_completions|day_item_states"
```

Expect all three tables present, each with `tenant_id` and `jurisdiction`
columns and **no** `status` or `overdue` column (compute-at-render, D157).

## Stage 1 — mint a dev token

```bash
docker compose exec padhanam-api python -c \
 "from padhanam.security.auth import issue_dev_token; \
  print(issue_dev_token(subject='operator-001', \
  tenant_id='00000000-0000-4000-8000-00000000a001', roles=['operator']))"
```

Copy the printed JWT. (The daily-driver authorisation comes from the
operator role `get_actor_context` assigns; any valid tenant_a token works.)

## Stage 2 — seed an OVERDUE commitment (so the differentiator is visible)

A commitment created through the UI starts on-track (last activity = now),
so to see the **BEHIND** "behind on this" row at smoke time, seed one with a
backdated `created_at` and no completions:

```bash
docker compose exec postgres-tenant-a psql -U tenant_a -d tenant_a -c \
"INSERT INTO commitments (id, tenant_id, jurisdiction, name, expected_interval_days, authored_by_user_id, created_at) \
 VALUES (gen_random_uuid(), '00000000-0000-4000-8000-00000000a001', 'eu-west', \
 'Weekly 1:1 with each report', 7, 'operator-001', now() - interval '30 days');"
```

Ensure at least one **OPEN Case** exists for tenant_a (create one via the
portfolio surface if needed):

```bash
curl -sk -X POST https://localhost/api/v1/portfolio/cases \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Q3 board deck","raw_text":"Prep the Q3 board deck"}' | head
```

## Stage 3 — browser interactive verification (the success criterion)

Open the surface in a browser at the stack base URL + `/app`
(e.g. `https://localhost/app` via Caddy, or `http://localhost:8000/app` if
hitting the api container directly). Paste the token into the field, click
**Use token**.

Verify, and record each:

1. **The prioritised list renders** today's items for tenant_a.
2. **AC7 — the felt differentiator:** the seeded "Weekly 1:1 with each
   report" commitment appears **at the top** with a red **BEHIND** pill and
   a "behind on this — N days over" detail. *This is the whole point of the
   slice — judge whether it reads as the system noticing something went
   quiet.*
3. The OPEN Case shows a **NEEDS YOU** pill.
4. **Reorder:** use ▲/▼ to move an item; reload the page; the order
   persists (PUT /today/order → day_item_states).
5. **The completion loop:** click **✓ Did it** on the overdue commitment;
   it flips to a green **ON TRACK** pill (overdue cleared by the completion
   log). This is the satisfying active-surfacing loop.
6. **Mark-done overlay:** click **✓ Done** on the Case; it gets a **DONE**
   pill, strikethrough, and sinks to the bottom; reload — it persists.
7. **Open-into-cell:** click **Open** on the Case → the side panel shows the
   Case detail (title, status, data points) fetched from
   `GET /api/v1/portfolio/cases/{id}` (the mirror-conversation read
   context). Click **Open** on a commitment → its detail panel.

## Stage 4 — tenant isolation

Mint a token for tenant_b (`...0000b002`) and load `/app` with it; the
tenant_a commitments and cases must **not** appear. (The bound-tenant
defence-in-depth is also covered by
`tests/contract/tenant_isolation/test_daily_driver_isolation.py`.)

---

## Record at close

- Did the BEHIND item render at the top end-to-end (AC7)? yes/no.
- Did the completion loop clear the overdue signal live? yes/no.
- Did open-into-cell show the Case context? yes/no.
- Did the slice land end-to-end at S58, or did surface polish split to S59?
