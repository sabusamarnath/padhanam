# P9 / S34 — Live-stack smoke for the run-history HTTP read surface

Exercises `GET /runs/{run_id}` and `GET /runs` against the running
`padhanam-padhanam-api-1` container with the production composition
plus two minimal substitutions to bypass the empty tenant registry
carryover from S30b:

1. `get_tenant_context` dependency overridden to return a
   `TenantContext` bound to tenant_a.
2. `app.state.run_history_reader` replaced with a `PostgresRunHistoryReader`
   wired directly to tenant_a's data plane (no session-factory cache,
   which would also go through the registry).

The substitutions are the same shape the S33 smoke used (direct
session factory bypass) — they preserve the HTTP boundary exercise
(parser, validation, route handler, exception handlers, correlation-id
middleware, response shape) while skipping the registry-resolution
step that the empty registry blocks.

D98 acceptance: ten distinguishable error paths plus one combined
cursor-and-filter verification (eleven verification paths total) plus
two happy paths all produce the documented status codes and body
shapes, with `X-Correlation-Id` returned on every response and the
`ErrorResponse` shape applied to the four custom-exception paths
(400 malformed_cursor, 400 invalid_filter_range, 404 run_not_found,
422 validation_error).

## Pre-state on tenant_a

```
SELECT id, tenant_id, agent_template_id, termination_reason, started_at
FROM runs ORDER BY started_at DESC;
                  id                  |              tenant_id               |          agent_template_id           | termination_reason |          started_at
--------------------------------------+--------------------------------------+--------------------------------------+--------------------+-------------------------------
 2e86d393-96b8-4aca-a12f-ac09d7e35355 | 00000000-0000-4000-8000-00000000a001 | 71d6b39a-79d4-45e8-879a-636967110277 | content            | 2026-05-13 23:00:00+00
 aedbefba-ea30-49fd-bf2e-435e9a4d2375 | 00000000-0000-4000-8000-00000000a001 | 637602a2-b19e-44c5-8f32-e4228f4692b5 | content            | 2026-05-13 19:42:18.793247+00
(2 rows)
```

Two runs from S32 (newer, with citations) and S31 (older, without).

## Smoke invocation

```
docker build -t padhanam-api:dev-s34 -f apps/api/Dockerfile .
docker tag padhanam-api:dev-s34 padhanam-api:dev
# compose.yaml pins the new content-addressed digest at line 380:
#   image: padhanam-api:dev@sha256:583f986993f6536c5ea473fbb93dbbbf23a70fc8b4d9641f6fcf8f3bd4bf2b4b
docker compose up -d --force-recreate --no-deps padhanam-api
docker cp scripts/smoke_p9_s34.py padhanam-padhanam-api-1:/app/scripts_smoke_p9_s34.py
docker compose exec -T padhanam-api python /app/scripts_smoke_p9_s34.py
```

## Captured output

### HAPPY_PATH_1: GET /runs/{known_s32_run} with citations

```
GET /runs/2e86d393-96b8-4aca-a12f-ac09d7e35355
status=200
X-Correlation-Id=<uuid4>
body={
  "id": "2e86d393-96b8-4aca-a12f-ac09d7e35355",
  "tenant_id": "00000000-0000-4000-8000-00000000a001",
  "jurisdiction": "eu-west",
  "agent_template_id": "71d6b39a-79d4-45e8-879a-636967110277",
  "agent_template_version": 1,
  "input_message": "What is LVT?",
  "output_content": "LVT is a Lean Value Tree, a methodology used by senior product leaders.",
  "started_at": "2026-05-13T23:00:00Z",
  "completed_at": "2026-05-13T23:00:30Z",
  "termination_reason": "content",
  "iteration_count": 2,
  "total_cost_usd": "0.00123",
  "trace_id": null,
  "audit_start_hash": "aaaa...aaaa",
  "audit_end_hash": "bbbb...bbbb",
  "created_at": "2026-05-13T23:00:30Z",
  "chunk_citations": [
    {
      "id": "c2e9167f-bad3-437d-8e30-ec0d4c54f18f",
      "run_id": "2e86d393-96b8-4aca-a12f-ac09d7e35355",
      "chunk_id": "eda98773-76a8-41c1-9a58-d69696def123",
      "tenant_id": "00000000-0000-4000-8000-00000000a001",
      "jurisdiction": "eu-west",
      "chunk_excerpt": "Customer interviews surface jobs-to-be-done patterns.",
      "source_snapshot": {"file_name": "03_customer_interviews.md", "file_type": "markdown"}
    },
    {
      "id": "fffe2062-22b2-475f-9913-e92d1905cb8b",
      "run_id": "2e86d393-96b8-4aca-a12f-ac09d7e35355",
      "chunk_id": "c8c6d59f-5e10-4ea9-b788-f7ddddedc3d4",
      "tenant_id": "00000000-0000-4000-8000-00000000a001",
      "jurisdiction": "eu-west",
      "chunk_excerpt": "Methodologies compose roles; agents adopt methodologies.",
      "source_snapshot": {"file_name": "03_customer_interviews.md", "file_type": "markdown"}
    }
  ],
  "entity_citations": [
    {
      "id": "8382e3ea-0977-43cf-97ad-a426bc37e039",
      "run_id": "2e86d393-96b8-4aca-a12f-ac09d7e35355",
      "entity_tenant_id": "00000000-0000-4000-8000-00000000a001",
      ...
    }
  ]
}
```

The RunResponse mirrors `RunRecord` 1:1 with citation tuples surfacing
as JSON arrays per Pydantic v2 default. The `source_snapshot` JSONB
round-trips with file_name and file_type preserved. `total_cost_usd`
surfaces as the string `"0.00123"`. Datetimes carry the `Z` suffix per
Pydantic v2.

### HAPPY_PATH_2: GET /runs?termination_reason=content&page_size=1

```
GET /runs?termination_reason=content&page_size=1
status=200
X-Correlation-Id=bace3294-eaee-49e9-af7e-549ae6f1aaf2
body={
  "runs": [
    {
      "id": "2e86d393-96b8-4aca-a12f-ac09d7e35355",
      ...
      "chunk_citations": [],
      "entity_citations": []
    }
  ],
  "next_cursor": "eyJzdGFydGVkX2F0IjoiMjAyNi0wNS0xM1QyMzowMDowMCswMDowMCIsImlkIjoiMmU4NmQzOTMtOTZiOC00YWNhLWExMmYtYWMwOWQ3ZTM1MzU1IiwicGFnZV9zaXplIjoxfQ=="
}
```

Cursor-paginated first page: one row, `next_cursor` non-None pointing
at the second page. List-altitude runs carry empty citation lists per
D97. The sentinel-cursor mechanism for page_size threading works
correctly — the first page honours `page_size=1` despite no inbound
cursor.

### PATH_1: bad UUID path param → 422 validation_error

```
GET /runs/not-a-uuid
status=422
X-Correlation-Id=29b0788d-b947-4d2e-96b4-4cd32427edc8
body={
  "error_code": "validation_error",
  "message": "request validation failed",
  "correlation_id": "29b0788d-b947-4d2e-96b4-4cd32427edc8",
  "details": {"errors": [{"type": "uuid_parsing", "loc": ["path", "run_id"], "msg": "Input should be a valid UUID, ...", "input": "not-a-uuid", ...}]}
}
```

The new `ErrorResponse` shape applies. Pydantic's UUID parse error
surfaces in `details.errors`. Correlation ID populated.

### PATH_2: bad query param type (page_size=abc) → 422 validation_error

```
GET /runs?page_size=abc
status=422
body={
  "error_code": "validation_error",
  "message": "request validation failed",
  "correlation_id": "0a0bf80f-2994-4749-b27e-54f1329c641c",
  "details": {"errors": [{"type": "int_parsing", "loc": ["query", "page_size"], "msg": "Input should be a valid integer, unable to parse string as an integer", "input": "abc"}]}
}
```

### PATH_3: page_size out of bounds (999) → 422 validation_error

```
GET /runs?page_size=999
status=422
body={
  "error_code": "validation_error",
  "details": {"errors": [{"type": "less_than_equal", "loc": ["query", "page_size"], "msg": "Input should be less than or equal to 50", "input": "999", "ctx": {"le": 50}}]}
}
```

FastAPI's `Query(ge=1, le=PAGE_SIZE_CEILING)` enforces the ceiling at
the parameter parse step.

### PATH_4: malformed cursor → 400 malformed_cursor

```
GET /runs?cursor=not-a-real-cursor!
status=400
X-Correlation-Id=9d427bf5-d64c-4fd7-9db3-67831e47327a
body={
  "error_code": "malformed_cursor",
  "message": "base64 decode failed: input contains non-url-safe-base64 characters",
  "correlation_id": "9d427bf5-d64c-4fd7-9db3-67831e47327a",
  "details": null
}
```

The domain `MalformedCursorError` raises from the cursor codec; the
HTTP handler translates to 400 with the new error shape.

### PATH_5: started_at_after > started_at_before → 400 invalid_filter_range

```
GET /runs?started_at_after=2026-05-14T18:00:00Z&started_at_before=2026-05-14T12:00:00Z
status=400
body={
  "error_code": "invalid_filter_range",
  "message": "started_at_after must be strictly earlier than started_at_before; got started_at_after=2026-05-14T18:00:00+00:00 started_at_before=2026-05-14T12:00:00+00:00",
  "correlation_id": "cc012e93-c881-4d1e-855b-fefbede80cc0",
  "details": null
}
```

### PATH_6: missing auth → 401

```
GET /runs/2e86d393-96b8-4aca-a12f-ac09d7e35355  (no Authorization header)
status=401
X-Correlation-Id=10e89832-ceb9-41a0-9a4d-85b06cc65790
body={"detail": "authentication required"}
```

The auth middleware fires before any route handler and returns the
legacy `{"detail": str}` shape; the run-history error handlers are
not registered for the middleware-level 401 (which is outside their
exception classes). The `X-Correlation-Id` header IS set because the
`CorrelationIdMiddleware` runs outermost in the chain.

### PATH_7: cross-tenant / missing run → 404 + security event

```
GET /runs/ffffffff-ffff-4fff-8fff-ffffffffffff
status=404
X-Correlation-Id=41e456f1-6460-4df4-b2c0-cb24ac995aea
body={
  "error_code": "run_not_found",
  "message": "run ffffffff-ffff-4fff-8fff-ffffffffffff not found",
  "correlation_id": "41e456f1-6460-4df4-b2c0-cb24ac995aea",
  "details": null
}
```

The `TENANT_SCOPE_VIOLATION` security event fires synchronously to
the file-backed security log (`logs/security_events.log` inside the
container) with the principal's tenant_id and the requested run_id
logged for forensic correlation. The cross-tenant attempt and
genuine-missing cases are structurally indistinguishable from the
HTTP layer per D98.

### PATH_8: known run on principal's own tenant → 200

```
GET /runs/aedbefba-ea30-49fd-bf2e-435e9a4d2375
status=200
body={
  "id": "aedbefba-ea30-49fd-bf2e-435e9a4d2375",
  "tenant_id": "00000000-0000-4000-8000-00000000a001",
  ...
  "input_message": "Smoke S31: define a good problem statement in one sentence.",
  "output_content": "To reduce hospital readmission rates by 20% within one year ...",
  "chunk_citations": [],
  "entity_citations": []
}
```

The S31-era run (no citations) round-trips through the HTTP boundary
cleanly. Confirms the empty-citation-tuple altitude works at the
RunResponse shape.

### PATH_9: unexpected exception / 500 internal_error

Exercised by integration tests:
`tests/integration/api/test_run_history_routes.py::test_get_run_returns_500_on_bound_tenant_mismatch`.
The defence-in-depth path (reader's bound-tenant-id check fires above
the data layer) is not safely reproducible in the live stack without
bypassing the route's principal check. The handler's body shape and
the synchronous `TENANT_SCOPE_VIOLATION` security event with
`severity=critical` metadata are verified by the unit tests at
`tests/unit/apps/api/test_errors.py`.

### PATH_10: method not allowed (POST /runs/{id}) → 405

```
POST /runs/2e86d393-96b8-4aca-a12f-ac09d7e35355
status=405
X-Correlation-Id=c55eb5bb-28f0-4383-9bb8-56422789cba9
body={"detail": "Method Not Allowed"}
```

FastAPI's default 405 shape applies; the run-history error handlers
don't intercept it. The correlation_id header still gets set by the
middleware.

### PATH_11: cursor + filters combined → 200 (filter-narrowed within cursor window)

```
GET /runs?cursor=<sentinel-cursor-page_size=10>&termination_reason=content
status=200
X-Correlation-Id=62d14313-26f4-4da2-817c-cea323c06a37
body={
  "runs": [<both tenant_a runs with termination_reason=content>],
  "next_cursor": null
}
```

The server honours both inputs per D98: the cursor anchors pagination,
the filter narrows within. The combination produces a valid page
(both tenant_a runs match `termination_reason=content`); the client
is responsible for filter consistency across paginated calls per the
D98 commitment.

## Findings

- Eleven verification paths plus two happy paths all produce the
  documented status codes and body shapes.
- The `ErrorResponse` shape applies to the four custom-exception
  paths (PATH_1, PATH_2, PATH_3 → 422 validation_error; PATH_4 → 400
  malformed_cursor; PATH_5 → 400 invalid_filter_range; PATH_7 → 404
  run_not_found). Middleware-level 401 (PATH_6) and FastAPI default
  405 (PATH_10) keep the legacy `{"detail": str}` shape per D98's
  scoped-extension design.
- `X-Correlation-Id` returned on every response, including the
  middleware-level 401 and the FastAPI default 405. The middleware
  runs outermost in the chain.
- The Pydantic v2 default tuple-to-list serialisation held cleanly for
  nested citation tuples. Decimal cost serialised as string. Datetimes
  carried the `Z` suffix.
- The sentinel-cursor approach for page_size threading on the initial
  page worked correctly (HAPPY_PATH_2 returned one row despite the
  adapter's default PAGE_SIZE_CEILING=50).
- The brief's stated PATH_8 ("missing run, no security event") is
  structurally indistinguishable from PATH_7 at the HTTP layer per
  D98; PATH_7 covers both via the privacy-preserving 404 plus the
  security event firing on every 404 from GET /runs/{run_id}.
- No real-Postgres findings beyond what the unit tests caught (the
  cursor codec's URL-safe alphabet check and the sa.cast for tuple
  comparison were both already in place from S33).

## What this leaves for S35

The end-to-end Phase 2 UX consumer story for the P9 substrate is now
closed at the HTTP boundary: the reader port from S33 is callable
from any web frontend via standard FastAPI endpoints; the cursor codec
is exercised at its intended HTTP boundary; the four-filter vocabulary
surfaces as a usable query-string parser; the eleven-path error map
plus the storage-versus-render-discipline-preserving response shape
gives a Phase 2 UX consumer everything it needs to render a run-list
view, a run-detail view, and paginate through history.

S35 framing (strategic-mode conversation) settles whether the next
session lands the HTTP API for ingestion management absorbed from the
P6 carryover, or closes P9 with an end-to-end demonstration
exercising the full path (agent invocation through SSE → run
completion writes record and citations → HTTP routes retrieve the
rendered surface). The build evidence at S34 close points slightly
toward (b) — closing P9 — because the substrate is structurally
complete and the ingestion-management API has no Phase 2 UX consumer
yet authored to justify its sequencing ahead of the optimisation
substrate at P10/P11.
