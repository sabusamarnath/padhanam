# Dogfooding runbook — personal tenant, scoped wipe, pinned deploy

How to run the daily driver on your own data, on a stable commit, and advance
it deliberately. Single-operator local setup ([dogfood-setup], D32) — not a
production deployment (no production auth/TLS/key-rotation here; that's out of
scope).

| Thing | Value |
|---|---|
| Personal tenant UUID | `00000000-0000-4000-8000-00000000d001` (neutral; encodes no real identity) |
| Personal tenant label | `personal` (env prefix `POSTGRES_TENANT_PERSONAL_`) |
| Postgres container | `postgres-tenant-personal` (its own volume `postgres_tenant_personal_data`) |
| Surface | `http://localhost:8000/app` (or `https://localhost/app` via Caddy) |
| Stable deploy tag | `dogfood-stable` |

All personal creds are **synthetic** (`.env.example` ships `tenant_personal`).
Never put real identity in `.env`, the compose file, seeds, or docs.

---

## 1. One-time setup

Ensure your local `.env` carries the personal-tenant creds (copy from
`.env.example` if missing):

```
POSTGRES_TENANT_PERSONAL_USER=tenant_personal
POSTGRES_TENANT_PERSONAL_PASSWORD=tenant_personal
POSTGRES_TENANT_PERSONAL_DB=tenant_personal
```

`.env` is gitignored — these stay local.

## 2. Deploy from the pinned stable tag

Run the dogfood deploy on the known-good commit, not on whatever is checked
out:

```bash
git checkout dogfood-stable          # the pinned known-good commit
make build-api                       # bake the current code into the api image
make up                              # bring the stack up with that image
```

`make build-api` is what puts the daily-driver code (and the `/app` route)
into the running server — the server imports at boot, so a code change needs
a rebuilt image (or `make sync-code` + an api restart for fast dev iteration).

## 3. Provision the personal tenant

```bash
make dogfood-provision
```

This brings up `postgres-tenant-personal`, registers it in the control plane
(`ops/dogfood_provision.py`, idempotent), and migrates it through the latest
per-tenant revision. Re-running is a no-op.

## 4. Get a token and open the surface

```bash
make dogfood-token        # prints a dev bearer token for the personal tenant
```

Open `http://localhost:8000/app`, paste the token into the field, click **Use
token**. Add your real commitments and cases and run it as your daily driver.
(The token is short-lived; re-run `make dogfood-token` when the page 401s.)

## 5. Wipe — clean slate, personal only

```bash
make dogfood-wipe         # interactive: type 'wipe personal' to confirm
```

Drops and recreates **only** the personal tenant's database, then re-migrates
it. It **cannot** touch tenant-a, tenant-b, or the control plane — three guard
layers enforce that (container boundary, hardcoded target, refuse-list; see
`ops/dogfood_wipe.sh`). Non-interactive use: `DOGFOOD_WIPE_CONFIRM=yes make
dogfood-wipe`.

**Wipe completeness.** Today the daily driver is Postgres-only, so this single
database drop *is* a complete wipe. As personal data spreads, a complete wipe
will also need a **Neo4j delete-by-tenant-property** (the graph is a shared
instance scoped by property per D63, not a per-tenant DB) and a **Langfuse
trace clear** (once conversational cells capture prompts). Those are named out
of scope here and deferred with the "Personal causal-graph isolation and
encryption posture" entry in `charter/deferred-decisions.md` — the later slices
inherit the requirement.

## 6. Advance deliberately (not every build)

The point of the pinned tag is that new code and new migrations land on *your*
terms, not on every `git pull`. To advance:

1. Confirm the newer commit is known-good (tests green, ideally a browser pass).
2. Re-point the tag to it and redeploy:
   ```bash
   git tag -f dogfood-stable <new-known-good-commit>
   git checkout dogfood-stable
   make build-api && make up
   make migrate        # apply any new per-tenant migrations, on your terms
   ```
3. Your personal data survives a redeploy (it lives in the
   `postgres_tenant_personal_data` volume); only `make dogfood-wipe` clears it.

Staying on `dogfood-stable` while you build elsewhere means your daily driver
keeps running on a stable schema until you choose to move it.

---

## Quick reference

```bash
make up                  # stack up
make dogfood-provision   # create + register + migrate the personal tenant
make dogfood-token       # mint a token for it
make dogfood-wipe        # clean wipe (personal only; guarded)
```
