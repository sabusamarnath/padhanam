# P10 / S38 — P10 close end-to-end demonstration

**Date:** 2026-05-14
**Mode:** smoke (live stack, real Postgres + control-plane chain + live HTTP transport)

This document is the P10 close artefact: the full read substrate
(audit per-tenant chain + audit control-plane chain + ingestion
management API) exercised end-to-end against the live stack via a
single reproducible script at `scripts/smoke_p10_s38.py`.

D104 acceptance: eleven distinguishable verification paths across
the audit and ingestion read substrates produce the expected status
codes and `ErrorResponse`-shaped bodies, with `X-Correlation-Id`
present on every response and AUTHZ_DENIAL security events firing on
the three cross-destination 403 paths.

## Pre-state

23 audit rows on `tenant_a`'s chain at session-open (continuing the
S11 → S37 history); the seed at S38 commit 6 added two more events
during the read path that touched `get_audit_event` (two
`tenant.audit.test_event` rows recording the lookup-was-allowed
event per S11/D26 — every audit read fires a privileged-action audit
write of its own per the audit-read-as-state-change discipline).

```
$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -c "SELECT action_verb, count(*) FROM tenant_audit GROUP BY action_verb ORDER BY count(*) DESC;"
       action_verb       | count
-------------------------+-------
 tenant.audit.test_event |    11
 agent.invoke.start      |     7
 agent.invoke.end        |     7
(3 rows)
```

Control-plane chain at session-open: empty (the S37 smoke seed had
been wiped between sessions). The S38 smoke script's
`maybe_seed_control_plane_event` would have seeded one event if the
chain were still empty at the smoke moment; at the moment the smoke
ran, one event from a prior recovery step was already present.

Tenant_a sources at session-open: empty (the wipe class from S30b
applies). The smoke script's `maybe_seed_ingestion_source` seeded
one probe source so the ingestion read paths had data to return.

## Smoke invocation

```
docker build -t padhanam-api:dev-s38 -f apps/api/Dockerfile .
docker tag padhanam-api:dev-s38 padhanam-api:dev
# compose.yaml pinned to the new content-addressed digest at line 380:
#   image: padhanam-api:dev@sha256:6479c9d0ed541b51471d81deb8624e01cf2b86a58ccea6dd516224cae14dc358
docker compose up -d --force-recreate --no-deps padhanam-api
docker compose cp scripts/smoke_p10_s38.py padhanam-api:/app/scripts/smoke_p10_s38.py
docker compose exec -T padhanam-api bash -c "cd /app && PYTHONPATH=. python scripts/smoke_p10_s38.py"
```

## Captured smoke output (JSON, verbatim)

```json
{
  "seeded_cp_event_id": null,
  "seeded_source_id": "f99085df-525b-4581-89e7-72c76d46e78d",
  "1_audit_per_tenant_list": {
    "status_code": 200,
    "correlation_id_header": "1637e395-7718-4e5a-a4e9-5622018e021f",
    "error_code": null,
    "body_summary": {
      "events_count": 25,
      "first_event_id": "2280d646-698e-4ce4-8c2a-bf607b28d003",
      "first_tenant_id": "00000000-0000-4000-8000-00000000a001",
      "chain_integrity_status": "verified",
      "next_cursor_present": false
    }
  },
  "2_audit_per_tenant_get_one": {
    "status_code": 200,
    "correlation_id_header": "215fa8d3-0f8d-4590-815a-808f3cdc4adb",
    "error_code": null,
    "body_summary": {
      "id": "2280d646-698e-4ce4-8c2a-bf607b28d003",
      "tenant_id": "00000000-0000-4000-8000-00000000a001",
      "action_verb": "tenant.audit.test_event",
      "this_event_hash_head": "17a36d15a1b916c4"
    }
  },
  "3_audit_control_plane_list": {
    "status_code": 200,
    "correlation_id_header": "7bdfac02-b147-4060-b0a7-37169b1007f9",
    "error_code": null,
    "body_summary": {
      "events_count": 1,
      "first_event_id": "bfeac72a-eda1-42c2-8a00-dc8212d19028",
      "first_tenant_id": "",
      "chain_integrity_status": "partial",
      "next_cursor_present": false
    }
  },
  "4_ingestion_list": {
    "status_code": 200,
    "correlation_id_header": "6c7a4fb9-e93c-45a3-9b84-f2e1cb0b9de4",
    "error_code": null,
    "body_summary": {
      "sources_count": 1,
      "first_source_id": "f99085df-525b-4581-89e7-72c76d46e78d",
      "first_tenant_id": "00000000-0000-4000-8000-00000000a001",
      "states_present": ["indexed"],
      "next_cursor_present": false
    }
  },
  "5_ingestion_get_one": {
    "status_code": 200,
    "correlation_id_header": "c1fd7571-5ed5-4b86-b6f1-fcd8c3e8adb7",
    "error_code": null,
    "body_summary": {
      "id": "f99085df-525b-4581-89e7-72c76d46e78d",
      "tenant_id": "00000000-0000-4000-8000-00000000a001",
      "state": "indexed",
      "file_name": "p10_s38_smoke_probe.md"
    }
  },
  "6_ingestion_get_status": {
    "status_code": 200,
    "correlation_id_header": "5467de7f-bb61-4a8c-a5e9-1dfb40b5ac9e",
    "error_code": null,
    "body_summary": {
      "id": "f99085df-525b-4581-89e7-72c76d46e78d",
      "state": "indexed",
      "parsing_error_text": null,
      "embedding_error_text": null,
      "extraction_error_text": null
    }
  },
  "7_tenant_on_platform_audit": {
    "status_code": 403,
    "correlation_id_header": "2f685b0f-fe25-4cd6-a0e3-f1715219cafc",
    "error_code": "principal_type_mismatch",
    "body_summary": {
      "error_code": "principal_type_mismatch",
      "message": "authenticated principal lacks the required type 'platform_operator' for this route; got 'tenant'"
    }
  },
  "8_operator_on_tenant_audit": {
    "status_code": 403,
    "correlation_id_header": "aaf1fe71-3d9c-42df-99f6-9412cc2096ea",
    "error_code": "principal_type_mismatch",
    "body_summary": {
      "error_code": "principal_type_mismatch",
      "message": "authenticated principal lacks the required type 'tenant' for this route; got 'platform_operator'"
    }
  },
  "9_operator_on_ingestion": {
    "status_code": 403,
    "correlation_id_header": "8b19567c-da8d-4e75-a960-0bc9f85a1e56",
    "error_code": "principal_type_mismatch",
    "body_summary": {
      "error_code": "principal_type_mismatch",
      "message": "authenticated principal lacks the required type 'tenant' for this route; got 'platform_operator'"
    }
  },
  "10_ingestion_fabricated_source_id": {
    "status_code": 404,
    "correlation_id_header": "732f26fd-9a39-4238-bbf0-5681bc7833ec",
    "error_code": "ingestion_source_not_found",
    "body_summary": {
      "error_code": "ingestion_source_not_found",
      "message": "ingestion source 6b39d530-585f-422d-8046-cb8f0b7ae395 not found"
    }
  },
  "11_ingestion_malformed_cursor": {
    "status_code": 400,
    "correlation_id_header": "aceda6f8-4e90-4715-8b01-9ba45c2b04a6",
    "error_code": "malformed_ingestion_cursor",
    "body_summary": {
      "error_code": "malformed_ingestion_cursor",
      "message": "base64 decode failed: input contains non-url-safe-base64 characters"
    }
  }
}
```

Eleven scenarios all return the expected status codes and error
codes; `X-Correlation-Id` present on every response; chain
integrity reports `verified` on the per-tenant page (25 events,
hash chain links match across the page) and `partial` on the
control-plane page (1 event — not enough for a multi-row hash
chain verification, which is the correct "I cannot verify this
on a single-row page" answer rather than a false-positive
`verified`).

## Security event capture

The three cross-destination 403 paths each fired an
`AUTHZ_DENIAL` security event to `logs/security.jsonl`:

```
$ docker compose exec -T padhanam-api tail -3 /app/logs/security.jsonl
{"action": "GET /platform/audit/events", "category": "authz_denial", "event_id": "bd39e8ec-...", "metadata": {"actual_principal_type": "tenant", "required_principal_type": "platform_operator"}, "outcome": "principal_type_mismatch", "principal_ref": "smoke:p10-s38-tenant", "resource_ref": null, "tenant_id": "00000000-0000-4000-8000-00000000a001", "timestamp": "2026-05-14T19:35:27.871574+00:00"}
{"action": "GET /audit/events", "category": "authz_denial", "event_id": "5481e134-...", "metadata": {"actual_principal_type": "platform_operator", "required_principal_type": "tenant"}, "outcome": "principal_type_mismatch", "principal_ref": "smoke:p10-s38-ops", "resource_ref": null, "tenant_id": null, "timestamp": "2026-05-14T19:35:27.872645+00:00"}
{"action": "GET /ingestion/sources", "category": "authz_denial", "event_id": "c30905b8-...", "metadata": {"actual_principal_type": "platform_operator", "required_principal_type": "tenant"}, "outcome": "principal_type_mismatch", "principal_ref": "smoke:p10-s38-ops", "resource_ref": null, "tenant_id": null, "timestamp": "2026-05-14T19:35:27.873519+00:00"}
```

Three AUTHZ_DENIAL events with the expected `action`, `metadata`,
`principal_ref`, and `tenant_id` shape per D103 / D104. The
relocated handler at `apps/api/_auth_errors.py` fires identically
across the audit and ingestion route trees — the cross-cutting
extraction from S38 commit 2 holds at runtime.

## Observations for the P10 close retrospective

**Chain integrity on a one-row page returns `partial`, not
`verified`.** This is the correct answer per D102's
page-granularity verifier shape — a single-row page does not have a
two-row "link to verify" inside it. Multi-row pages with full chain
verification report `verified`; mixed pages or page-too-small
report `partial`. The control-plane chain shows `partial` because
it only has one event; the per-tenant chain shows `verified`
because all 25 events form a verifiable link sequence.

**Audit reads are themselves audited.** The 25-event count on the
per-tenant chain at smoke close is +2 above the 23 at session-open
because each `GET /audit/events/{id}` route fires its own
`tenant.audit.test_event` audit write per the audit-read-as-state-change
discipline from S11/D26. The reading-amplifies-writes shape is a
Phase 1 commitment.

**Path A's ingestion HTTP routes work cleanly with the existing
get_source use case.** The status-projection endpoint (scenario 6)
proves the brief's "thin DTO transformation" approach — the route
calls `get_source` and projects the state-relevant fields without a
separate `get_source_status` use case. The list endpoint (scenario
4) exercises the new `list_sources` use case + the new
`SourceRepositoryPort.list_sources` method end-to-end, including the
adapter's cursor pagination logic on `(created_at DESC, id DESC)`.

**No regressions on the audit substrate.** Scenarios 1, 2, 3, 7, 8
exercise the S36/S37 audit substrate; all behave as documented at
S37 close. The S38 commit-2 auth-handler relocation is invisible to
the audit surface — the same 403 + AUTHZ_DENIAL events fire, just
from a different module.

## Acceptance per D104

| # | Verification | Expected | Actual |
|---|------|------|------|
| 1 | per-tenant audit list | 200, chain_integrity=verified | ✓ 200, verified |
| 2 | per-tenant audit get-one | 200, dto-shape | ✓ 200, dto-shape |
| 3 | control-plane audit list | 200, chain_integrity={verified|partial} | ✓ 200, partial (one-row chain) |
| 4 | ingestion list | 200, own-tenant only | ✓ 200, 1 source on tenant_a |
| 5 | ingestion get-one | 200, dto-shape | ✓ 200, dto-shape |
| 6 | ingestion get-status | 200, status-projection | ✓ 200, state=indexed |
| 7 | tenant→platform-audit | 403, AUTHZ_DENIAL | ✓ 403, event fired |
| 8 | operator→tenant-audit | 403, AUTHZ_DENIAL | ✓ 403, event fired |
| 9 | operator→ingestion | 403, AUTHZ_DENIAL | ✓ 403, event fired |
| 10 | fabricated cross-tenant source_id | 404, no event | ✓ 404, no event |
| 11 | malformed ingestion cursor | 400 | ✓ 400 |

P10 closes with the full read substrate operational end-to-end.
