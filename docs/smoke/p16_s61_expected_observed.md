# P16 / S61 — Minimal expected-versus-observed loop (procedural smoke)

The minimal expected-versus-observed loop on the Commitment primitive
(D162). This smoke is **operator-driven against the live stack**: the
build environment cannot reach docker, and per the CLAUDE.md discipline a
UI acceptance criterion is met by **browser interactive verification**,
not CLI smoke. Run the stages below against the running Compose stack and
record the outcome in the session-log close (AC8).

Tenant: `tenant_a` = `00000000-0000-4000-8000-00000000a001`
(jurisdiction `eu-west`). (For the personal-tenant dogfooding stack,
substitute the personal tenant id.)

---

## Stage 0 — bring the code and schema up

```bash
make sync-code            # fast-path: copy contexts/apps/etc into the api container
# (or `make build-api && docker compose up -d --force-recreate padhanam-api`
#  for the production-shaped image path — required for the server to pick up
#  the new /observed-outcome route, since the server imports at boot)
make migrate              # applies 0029_commitment_outcome to each tenant DB
```

Verify the four new columns landed on tenant_a's `commitments`:

```bash
docker compose exec postgres-tenant-a \
  psql -U tenant_a -d tenant_a -c "\d+ commitments"
```

Expect `expected_outcome`, `observed_outcome`, `outcome_status`,
`observed_at` (all nullable) and the `commitments_outcome_status_check`
constraint.

## Stage 1 — set a small drop-candidate window (so the nudge is visible)

The default `DROP_CANDIDATE_QUIET_DAYS` is 21; to exercise the nudge
without waiting weeks, set it small for the smoke and restart the api so
the composition root re-reads it:

```bash
# add to the api service env (compose override or .env), then restart:
#   DROP_CANDIDATE_QUIET_DAYS=2
docker compose up -d --force-recreate padhanam-api
```

(Alternatively leave the default and SQL-backdate a commitment's
`created_at` past 21 days, as in Stage 4.)

## Stage 2 — mint a dev token

```bash
docker compose exec padhanam-api python -c \
 "from padhanam.security.auth import issue_dev_token; \
  print(issue_dev_token(subject='operator-001', \
  tenant_id='00000000-0000-4000-8000-00000000a001', roles=['operator']))"
```

Copy the printed JWT (the `operator` role now carries
`daily_driver.commitment.observe`). Or sign in through `/login` on the
dogfooding stack — the minted session is identical at the data routes.

## Stage 3 — browser interactive verification (the success criterion, AC8)

Open `/app` (e.g. `https://localhost/app`), authenticate.

1. **Capture an expectation at creation (AC1):** in the *New commitment*
   form, enter a name (e.g. "Weekly 1:1 with each report"), an interval,
   and an **expected outcome** in the "What do you expect to come of it?"
   field (e.g. "each report feels supported and unblocked"). Add it.
   *Judge the friction (reflection 3): did the expected field feel like a
   natural prompt, or an extra hoop?*

2. **Record what transpired + the gap (AC2, AC3):** open that commitment's
   drawer. Confirm **Expected** shows your text and **Observed** shows "not
   yet recorded". In *Record what transpired*, type an observation (e.g.
   "two of three felt supported; missed the third week") and pick a status
   (e.g. **Partial**). Save. The drawer re-renders with **Expected** and
   **Observed** side by side and an `outcome` badge — *the gap is visible.*

3. **Drop nudge on a stale item (AC4):** see Stage 4 to make a stale item,
   then confirm the row shows a **"gone quiet — drop it?"** nudge, the
   drawer shows the same nudge, and acting on it (set status **Dropped —
   let it go** in the drawer) removes the nudge on reload. *No auto-drop —
   the item only changes because you acted.*

## Stage 4 — a deliberately stale item for the drop nudge

```bash
docker compose exec postgres-tenant-a psql -U tenant_a -d tenant_a -c \
"INSERT INTO commitments (id, tenant_id, jurisdiction, name, expected_interval_days, authored_by_user_id, created_at) \
 VALUES (gen_random_uuid(), '00000000-0000-4000-8000-00000000a001', 'eu-west', \
 'Revive the newsletter', 7, 'operator-001', now() - interval '40 days');"
```

With no completions and no observation, its last-progress is 40 days ago →
a drop candidate at any reasonable N. Reload `/app`; the row carries the
nudge.

## Stage 5 — tenant isolation

Mint a token for tenant_b (`...0000b002`) and load `/app`; the tenant_a
commitments and their outcomes must **not** appear. (Bound-tenant
defence-in-depth on the observed-outcome write is also covered by
`tests/contract/tenant_isolation/test_daily_driver_isolation.py`.)

---

## Record at close (AC8)

- Did the expected outcome capture at creation (AC1)? yes/no — and the felt
  friction (reflection 3).
- Did the observed outcome + status capture, and the expected/observed gap
  render side by side (AC2, AC3)? yes/no.
- Did the stale item show the drop nudge as a recommendation, and did acting
  on it (Dropped) clear it with no auto-drop (AC4)? yes/no.
- Did tenant_b see none of tenant_a's outcomes (AC5)? yes/no.
