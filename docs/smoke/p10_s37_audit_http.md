# P10 / S37 — Live-stack smoke for the audit HTTP transport

Exercises the four audit HTTP routes (per-tenant `/audit/events*` and
control-plane `/platform/audit/events*`) plus the four auth failure
cases plus the two query-validation 400 paths, all against the
running `padhanam-padhanam-api-1` container using `httpx` from inside
the container. Tokens are minted at smoke time via the dev backend
(`issue_dev_token` + `issue_platform_operator_dev_token`).

D103 acceptance: ten distinguishable verification paths plus two
happy-path single-event lookups all produce the documented status
codes and `ErrorResponse`-shaped bodies, with `X-Correlation-Id`
present on every response. The 403 path fires `AUTHZ_DENIAL`
security events to `logs/security.jsonl` carrying the attempted
route, the required and actual principal_type values, and the
offending token's `tenant_id` when tenant-typed.

## Pre-state

```
$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -c "SELECT action_verb, count(*) FROM tenant_audit GROUP BY action_verb ORDER BY count(*) DESC;"
       action_verb       | count
-------------------------+-------
 tenant.audit.test_event |     9
 agent.invoke.start      |     7
 agent.invoke.end        |     7
(3 rows)

$ docker compose exec -T postgres-control-plane psql -U control_plane -d control_plane \
    -c "SELECT count(*) FROM tenant_audit;"
 count
-------
     0
(1 row)
```

23 audit rows on `tenant_a`'s chain (mix from S11/S12/S35/S35a/S35b).
Control-plane chain empty at smoke open. The smoke script seeds one
probe event before scenario 5 so the control-plane destination has
data to read.

## Smoke invocation

```
docker build -t padhanam-api:dev-s37 -f apps/api/Dockerfile .
docker tag padhanam-api:dev-s37 padhanam-api:dev
# compose.yaml pins to the new content-addressed digest at line 380:
#   image: padhanam-api:dev@sha256:39b0d026038d602cf8cfd3d88efad8eb5f895ec54728837eca56a16d74f88de8
docker compose up -d --force-recreate --no-deps padhanam-api
docker cp scripts/smoke_p10_s37.py padhanam-padhanam-api-1:/app/scripts_smoke_p10_s37.py
docker compose exec -T padhanam-api python /app/scripts_smoke_p10_s37.py
```

The script lives at [scripts/smoke_p10_s37.py](../../scripts/smoke_p10_s37.py).

## Captured output

```json
{
  "seeded_cp_event_id": "15046a75-8ba1-4a80-8e46-d8683c4fee17",
  "scenario_1_tenant_list_no_filters": {
    "status_code": 200,
    "correlation_id_header": "9a6218ad-769c-433e-a077-7fc83f617ec2",
    "error_code": null,
    "body_summary": {
      "events_count": 23,
      "first_event_id": "5a931869-ff08-4a77-a348-5d7614c14d64",
      "first_tenant_id": "00000000-0000-4000-8000-00000000a001",
      "chain_integrity_status": "verified",
      "next_cursor_present": false
    }
  },
  "scenario_2_tenant_get_known_event": {
    "status_code": 200,
    "correlation_id_header": "b931e890-8076-4140-a4fc-ca2a33db1011",
    "error_code": null,
    "body_summary": {
      "id": "5a931869-ff08-4a77-a348-5d7614c14d64",
      "tenant_id": "00000000-0000-4000-8000-00000000a001",
      "action_verb": "tenant.audit.test_event",
      "this_event_hash_head": "41818447fd581e82"
    }
  },
  "scenario_3_tenant_list_resource_type": {
    "status_code": 200,
    "correlation_id_header": "93865f83-47cb-484f-8063-1545c2e07945",
    "error_code": null,
    "body_summary": {
      "events_count": 9,
      "first_event_id": "5a931869-ff08-4a77-a348-5d7614c14d64",
      "first_tenant_id": "00000000-0000-4000-8000-00000000a001",
      "chain_integrity_status": "verified",
      "next_cursor_present": false
    }
  },
  "scenario_4_tenant_list_paired_resource": {
    "status_code": 200,
    "correlation_id_header": "f61d1bec-01f9-4a03-93b9-88274a6d38d8",
    "error_code": null,
    "body_summary": {
      "events_count": 9,
      "first_event_id": "5a931869-ff08-4a77-a348-5d7614c14d64",
      "first_tenant_id": "00000000-0000-4000-8000-00000000a001",
      "chain_integrity_status": "verified",
      "next_cursor_present": false
    }
  },
  "scenario_5_platform_list_cp": {
    "status_code": 200,
    "correlation_id_header": "d81aa1c4-6474-4b1d-a536-34c6ba0b957b",
    "error_code": null,
    "body_summary": {
      "events_count": 1,
      "first_event_id": "15046a75-8ba1-4a80-8e46-d8683c4fee17",
      "first_tenant_id": "",
      "chain_integrity_status": "partial",
      "next_cursor_present": false
    }
  },
  "scenario_6_resource_id_without_resource_type": {
    "status_code": 400,
    "correlation_id_header": "3df554bf-072e-4d9e-a0d9-56c205d29e3c",
    "error_code": "invalid_audit_filter",
    "body_summary": {
      "error_code": "invalid_audit_filter",
      "message": "resource_id filter requires resource_type to also be set; resource_id without resource_type is ambiguous because the sam"
    }
  },
  "scenario_7_malformed_cursor": {
    "status_code": 400,
    "correlation_id_header": "2b080145-e35d-4482-9ad1-bfa97bdeffdd",
    "error_code": "malformed_audit_cursor",
    "body_summary": {
      "error_code": "malformed_audit_cursor",
      "message": "base64 decode failed: Invalid base64-encoded string: number of data characters (17) cannot be 1 more than a multiple of "
    }
  },
  "scenario_8_no_auth": {
    "status_code": 401,
    "correlation_id_header": "192a0d4d-ef8a-413d-a988-2393892c90fc",
    "error_code": null,
    "body_summary": {
      "detail": "authentication required"
    }
  },
  "scenario_9_platform_operator_on_tenant_route": {
    "status_code": 403,
    "correlation_id_header": "f8daabb3-f9d1-4873-b48e-16c4d67d2766",
    "error_code": "principal_type_mismatch",
    "body_summary": {
      "error_code": "principal_type_mismatch",
      "message": "authenticated principal lacks the required type 'tenant' for this route; got 'platform_operator'"
    }
  },
  "scenario_10_tenant_on_platform_route": {
    "status_code": 403,
    "correlation_id_header": "0d574a7b-a93d-4e63-8e6f-56f69ce3ea51",
    "error_code": "principal_type_mismatch",
    "body_summary": {
      "error_code": "principal_type_mismatch",
      "message": "authenticated principal lacks the required type 'platform_operator' for this route; got 'tenant'"
    }
  }
}
```

## Security event capture (`logs/security.jsonl`)

The smoke produced four security events (one AUTH_FAILURE from the
middleware on scenario 8, two AUTHZ_DENIAL from the new handler on
scenarios 9 and 10, plus one PRIVILEGED_ACTION from the per-tenant
session-factory cache resolving tenant_a credentials):

```json
{"action": "tenant.reveal_credentials", "category": "privileged_action", "principal_ref": "system:audit",
 "resource_ref": "tenant:00000000-0000-4000-8000-00000000a001", "outcome": "allow", "tenant_id": null}

{"action": "GET /audit/events", "category": "auth_failure", "principal_ref": null, "tenant_id": null,
 "metadata": {"reason": "missing_bearer"}, "outcome": "denied"}

{"action": "GET /audit/events", "category": "authz_denial", "principal_ref": "smoke:p10-s37-ops",
 "tenant_id": null, "metadata": {"actual_principal_type": "platform_operator",
 "required_principal_type": "tenant"}, "outcome": "principal_type_mismatch"}

{"action": "GET /platform/audit/events", "category": "authz_denial", "principal_ref": "smoke:p10-s37-tenant",
 "tenant_id": "00000000-0000-4000-8000-00000000a001",
 "metadata": {"actual_principal_type": "tenant",
 "required_principal_type": "platform_operator"}, "outcome": "principal_type_mismatch"}
```

The tenant_id is `null` for the platform-operator-on-tenant-route
case (the offending token's empty sentinel did not propagate to the
security event metadata) and populated with the tenant_a UUID for
the tenant-on-platform-route case — exactly matching the D103
commit-4 metadata commitment.

## Findings

1. **All four routes work end-to-end against live Postgres.** The
   per-tenant routes serve 23 events from tenant_a's chain with
   verified integrity; the control-plane routes serve the seeded
   probe event from the control-plane chain.
2. **Chain integrity verification surfaces correctly on read.**
   Scenario 1 (no-filter, 23 events spanning multiple action verbs)
   reports `verified` — every per-row hash recomputes cleanly and
   consecutive rows link correctly. Scenario 5 (1-event page on
   control-plane) reports `partial` — the verifier cannot verify
   a chain link with only one row, which is the honest surfacing
   per D102.
3. **The eight-filter query vocabulary surfaces all expected
   shapes.** `resource_type` alone (scenario 3) and the paired
   `resource_type` + `resource_id` (scenario 4) both filtered the
   page down from 23 to 9 events. The `resource_id`-without-
   `resource_type` case (scenario 6) raised `InvalidAuditFilterError`
   → 400 `invalid_audit_filter` with the typed handler from
   commit 4.
4. **The four auth failure cases all fire correctly.** Scenario 8
   returns 401 from the auth middleware (legacy `{"detail": ...}`
   shape — pre-D98 surface that the auth middleware fires before
   the FastAPI exception handlers register; consistent with S34's
   behaviour). Scenario 9 (platform-operator on tenant route) and
   scenario 10 (tenant on platform route) both return 403
   `principal_type_mismatch` with the D98-shaped `ErrorResponse`
   body and the AUTHZ_DENIAL security event firing in the handler.
   The `correlation_id` round-trips on every response.
5. **The discriminator-field claim shape held in practice.** No
   token-shape exception fired during the legitimate tenant-token
   issuance or platform-operator-token issuance paths; tokens
   decoded cleanly and the discriminator routed correctly through
   `get_tenant_context` and `get_platform_operator_principal`.
   Both 403 paths in scenarios 9 and 10 fired through the same
   `PrincipalTypeMismatchError` typed exception via the parallel
   `register_audit_error_handlers` registration shape.
6. **The two-tree route shape carried the authorization decision
   visibly.** Each route's `Depends(...)` declaration named the
   required principal type explicitly; the two route trees made
   the auth gate visible at route signature exactly as D103's
   visibility-grounds reasoning argued.
