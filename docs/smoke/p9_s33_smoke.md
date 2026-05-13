# P9 / S33 — Live-stack smoke for the run-history read surface

Exercises `PostgresRunHistoryReader.get_run` and
`PostgresRunHistoryReader.list_runs_with_filters` against tenant_a's
runs and citation data on the live `padhanam-postgres-tenant-a-1`
container. The smoke runs inside `padhanam-padhanam-api-1` so the
SQLAlchemy/asyncpg engine reaches the per-tenant Postgres through
the docker network at the canonical `postgres-tenant-a:5432`.

D97 acceptance: get_run returns the run as an aggregate with chunk
and entity citation tuples populated; list_runs_with_filters honours
filter and cursor inputs; cursor pagination at page_size=1 produces
a stable two-page traversal of tenant_a's two existing runs.

## Pre-state on tenant_a

```
SELECT id, agent_template_id, termination_reason, started_at FROM runs ORDER BY started_at DESC;
                  id                  |          agent_template_id           | termination_reason |          started_at
--------------------------------------+--------------------------------------+--------------------+-------------------------------
 2e86d393-96b8-4aca-a12f-ac09d7e35355 | 71d6b39a-79d4-45e8-879a-636967110277 | content            | 2026-05-13 23:00:00+00
 aedbefba-ea30-49fd-bf2e-435e9a4d2375 | 637602a2-b19e-44c5-8f32-e4228f4692b5 | content            | 2026-05-13 19:42:18.793247+00
(2 rows)
```

The newer run (`2e86d393-...`) was written at the S32 smoke and
carries two `run_chunk_citations` rows plus one `run_entity_citations`
row; the older run (`aedbefba-...`) was written at the S31 smoke
and carries no citations.

## Smoke invocation

```
docker build -t padhanam-api:dev-s33 -f apps/api/Dockerfile .
docker tag padhanam-api:dev-s33 padhanam-api:dev
# compose.yaml pins to the new content-addressed digest at line 380:
#   image: padhanam-api:dev@sha256:a05b87b99117779aeebf97948650f1c2950e10e4589b603c4bc9934b9338c098
docker compose up -d --force-recreate --no-deps padhanam-api
docker cp scripts/smoke_p9_s33.py padhanam-padhanam-api-1:/app/scripts_smoke_p9_s33.py
docker compose exec -T padhanam-api python /app/scripts_smoke_p9_s33.py
```

## Captured output

### 1. `get_run` on the known S32 run

```
=== get_run(known S32 run) ===
{
  "id": "2e86d393-96b8-4aca-a12f-ac09d7e35355",
  "tenant_id": "00000000-0000-4000-8000-00000000a001",
  "jurisdiction": "eu-west",
  "agent_template_id": "71d6b39a-79d4-45e8-879a-636967110277",
  "agent_template_version": 1,
  "input_message": "What is LVT?",
  "output_content": "LVT is a Lean Value Tree, a methodology used by senior product leaders.",
  "started_at": "2026-05-13T23:00:00+00:00",
  "completed_at": "2026-05-13T23:00:30+00:00",
  "termination_reason": "content",
  "iteration_count": 2,
  "total_cost_usd": "0.00123",
  "trace_id": null,
  "audit_start_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "audit_end_hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "created_at": "2026-05-13T23:00:30+00:00",
  "chunk_citations": [
    {
      "id": "c2e9167f-bad3-437d-8e30-ec0d4c54f18f",
      "run_id": "2e86d393-96b8-4aca-a12f-ac09d7e35355",
      "chunk_id": "eda98773-76a8-41c1-9a58-d69696def123",
      "tenant_id": "00000000-0000-4000-8000-00000000a001",
      "jurisdiction": "eu-west",
      "chunk_excerpt": "Customer interviews surface jobs-to-be-done patterns.",
      "source_snapshot": {
        "file_name": "03_customer_interviews.md",
        "file_type": "markdown"
      }
    },
    {
      "id": "fffe2062-22b2-475f-9913-e92d1905cb8b",
      "run_id": "2e86d393-96b8-4aca-a12f-ac09d7e35355",
      "chunk_id": "c8c6d59f-5e10-4ea9-b788-f7ddddedc3d4",
      "tenant_id": "00000000-0000-4000-8000-00000000a001",
      "jurisdiction": "eu-west",
      "chunk_excerpt": "Methodologies compose roles; agents adopt methodologies.",
      "source_snapshot": {
        "file_name": "03_customer_interviews.md",
        "file_type": "markdown"
      }
    }
  ],
  "entity_citations": [
    {
      "id": "8382e3ea-0977-43cf-97ad-a426bc37e039",
      "run_id": "2e86d393-96b8-4aca-a12f-ac09d7e35355",
      "entity_tenant_id": "00000000-0000-4000-8000-00000000a001",
      "entity_name": "Lean Value Tree",
      "entity_type": "Framework",
      "tenant_id": "00000000-0000-4000-8000-00000000a001",
      "source_chunk_ids": [
        "eda98773-76a8-41c1-9a58-d69696def123",
        "c8c6d59f-5e10-4ea9-b788-f7ddddedc3d4"
      ]
    }
  ]
}
  chunk_citations_count=2 entity_citations_count=1
```

### 2. `list_runs_with_filters` with no filters

```
=== list_runs_with_filters(no filters) ===
{
  "runs_count": 2,
  "next_cursor": null
}
  - run_id=2e86d393-96b8-4aca-a12f-ac09d7e35355 agent_template_id=71d6b39a-79d4-45e8-879a-636967110277 termination_reason=content started_at=2026-05-13T23:00:00+00:00
  - run_id=aedbefba-ea30-49fd-bf2e-435e9a4d2375 agent_template_id=637602a2-b19e-44c5-8f32-e4228f4692b5 termination_reason=content started_at=2026-05-13T19:42:18.793247+00:00
```

### 3. `list_runs_with_filters` with `termination_reasons=("content",)`

```
=== list_runs_with_filters(termination_reasons=('content',)) ===
{
  "runs_count": 2,
  "next_cursor": null
}
```

Both runs survive the filter because both terminated with `content`.
The filter SQL exercises the `runs.termination_reason IN ('content')`
WHERE clause path.

### 4. Cursor pagination at page_size=1 — page 1

```
=== list_runs_with_filters(page_size=1, future cursor) ===
{
  "runs_count": 1,
  "next_cursor": {
    "started_at": "2026-05-13T23:00:00+00:00",
    "id": "2e86d393-96b8-4aca-a12f-ac09d7e35355",
    "page_size": 1
  },
  "next_cursor_encoded": "eyJzdGFydGVkX2F0IjoiMjAyNi0wNS0xM1QyMzowMDowMCswMDowMCIsImlkIjoiMmU4NmQzOTMtOTZiOC00YWNhLWExMmYtYWMwOWQ3ZTM1MzU1IiwicGFnZV9zaXplIjoxfQ=="
}
  - run_id=2e86d393-96b8-4aca-a12f-ac09d7e35355 started_at=2026-05-13T23:00:00+00:00
```

The initial-page invocation uses a "future cursor" hack
(`started_at=2099-01-01`) to set `page_size=1` while not filtering
out any real row. Page 1 returns the newer run plus a `next_cursor`
whose `started_at` and `id` reflect the page's last (= only) row.
The base64-encoded cursor is returned as `next_cursor_encoded` to
verify the codec round-trips across the HTTP-shaped boundary.

### 5. Cursor pagination at page_size=1 — page 2

```
=== list_runs_with_filters(page2, cursor from page1) ===
{
  "runs_count": 1,
  "next_cursor": null
}
  - run_id=aedbefba-ea30-49fd-bf2e-435e9a4d2375 started_at=2026-05-13T19:42:18.793247+00:00
```

Page 2 returns the older run; `next_cursor` is None because no
further rows exist on tenant_a. The tuple-comparison WHERE clause
(`(started_at, id) < (page1.started_at, page1.id)`) correctly
excluded the page-1 row from page 2's result set.

## Acceptance criteria verified

- `get_run` returned the run as an aggregate with `chunk_citations`
  (2 entries) and `entity_citations` (1 entry) populated; per
  D97's RunRecord-as-aggregate shape rather than a wrapper.
- The `source_snapshot` JSONB round-trips as a Python dict with the
  Phase 1 keys (`file_name`, `file_type`) intact.
- The `source_chunk_ids` text[] round-trips as a tuple of UUIDs on
  the entity citation record.
- `list_runs_with_filters` with no filters returned both tenant_a
  runs sorted by `started_at DESC, id DESC` per D97.
- `list_runs_with_filters` with `termination_reasons=("content",)`
  filter returned both runs (both terminated with `content`).
- Cursor pagination at `page_size=1` paginated stably across two
  pages: page 1 returned the newer run plus a non-null
  `next_cursor`; page 2 used that cursor and returned the older
  run with `next_cursor=None`.
- The base64-encoded cursor format is the same shape the cursor
  codec emits at `contexts/run_history/application/cursor.py`; the
  encoding survives the SQL round-trip via tuple-comparison.

## Reconciliation notes carried to session log

Real-Postgres surfaced one structural finding the unit tests' fake
session did not catch: the tuple comparison
`(runs.started_at, runs.id) < (:cursor_started_at, :cursor_id)`
fails at the operator-resolver step with `operator does not exist:
uuid < character varying` because the `id` column is `pg.UUID` and
the parameter binding defaults to `VARCHAR`. The fix wraps the
parameter in `sa.cast(str(cursor.id), pg.UUID(as_uuid=False))` so
Postgres sees `uuid < uuid` and resolves the operator. The unit
tests still pass because the fake session doesn't enforce
Postgres-strict type matching. Worth noting as a class of finding
that only surfaces at live-stack altitude: type-strict operator
resolution at the database boundary is something fake-session tests
structurally cannot catch.
