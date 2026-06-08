# S65 smoke — task ingestion (Google Tasks)

Live verification of the P17 task-ingestion build against the running stack
(Docker reachable). The api image was rebuilt and recreated before migrate/pull
(the S41/S56a baked-image discipline; the S62 stale-image lesson).

## Procedure (run, this session)

1. `make build-api` — rebuilt the image (new digest pinned in `compose.yaml`).
2. `docker compose up -d --force-recreate padhanam-api` — recreated on the new image.
3. `make migrate` — applied `0030_tasks_substrate` (task_connections + tasks) to
   all tenant DBs (personal, a, b).

## Results (live, 2026-06-08)

- **Tables exist (D167, AC4).** `tasks` and `task_connections` present on the
  personal tenant DB (0 rows, fresh).
- **`GET /tasks` reads the live cache (AC5).** Personal-tenant token → `[]`
  (empty cache, no connection yet) — the route, `TasksReaderAdapter`,
  `PostgresTaskStore`, and the `tasks` table all execute against the live DB (an
  absent table would error, not return `[]`).
- **Tenant isolation (AC4, AC8).** tenant_b token → `GET /tasks` returns `[]`.
- **The Tasks panel serves (AC5).** `GET /app` returns 200 and carries the Tasks
  panel (`loadTasks`, `id="tasks"`, the read-only "Your Google Tasks" copy).
- **The pull is wired and operator-gated (AC7).** `make pull-tasks` with no
  connection provisioned exits with a clear actionable message
  (`TASKS_CONNECTION_REF is empty — provision the Nango google-tasks connection
  (tasks.readonly) …`), not a stack trace — the path is wired; the live Google
  pull is the operator's step.

## Operator-gated: the live pull against real Google Tasks (AC7)

The build env has no Nango `google-tasks` integration and no `tasks.readonly`
consent, so the live pull is the operator's final confirmation (the S56a
operator-gated-provisioning precedent). The mock unit/contract tests verify the
adapter *parses* a shape and the pipeline upserts/tombstones/set-diffs; they
cannot verify what real Google *emits* (the S55a MockTransport lesson) — the
live pull is the emit-side gate.

Operator pre-flight, then run:

1. In self-hosted Nango, create a `google-tasks` integration on the connected
   Google provider with the `https://www.googleapis.com/auth/tasks.readonly`
   scope; complete the OAuth connect and copy the connection reference. (Set the
   integration's base URL to `https://tasks.googleapis.com` so the Proxy path
   `/proxy/tasks/v1/...` routes; reconcile the exact proxy path here, not from
   memory — the S55a lesson.)
2. Set `TASKS_CONNECTION_REF` (and `NANGO_SECRET_KEY` if not already) in the
   gitignored `.env`.
3. `make pull-tasks` — ensures the `google_tasks` connection then full re-pulls
   into the cache. Re-run to confirm **idempotency** (same rows; vanished tasks
   tombstoned via set-diff).
4. Open `http://localhost:8000/app` and confirm the **Tasks** panel lists the
   real Google tasks (title, due, notes, source list), read-only, **not** linked
   to calendar or goals (correlation is P18). Confirm tenant_b still reads empty.
