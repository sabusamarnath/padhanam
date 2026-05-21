# P13 S44a — ActorContext and authorisation decorator live-stack smoke

Live-stack smoke for the S44a identity-and-permissions substrate
(D126): the full ActorContext propagation path exercised end-to-end
against tenant_a on a freshly-rebuilt `padhanam-api` image — HTTP
request resolves to an ActorContext at `get_actor_context`, the
use-case-boundary decorator enforces the `authorisation_set` check,
the use case extracts `tenant_context` for adapter calls, the audit
event records the actor identity, and the `AuthorisationDenied` →
403 translation holds. Run 2026-05-22 at S44a commit 7.

## Stage 1 — image rebuild plus migration verification

```
make build-api
# -> docker build -t padhanam-api:dev -f apps/api/Dockerfile .
# -> new image digest sha256:118aaaa5d615729d8ac23ad9a2d6c758487575bf8264fc66eded8b769203c059
# -> compose.yaml padhanam-api digest pin rewritten

docker compose up -d --force-recreate padhanam-api
# -> padhanam-api recreated, healthy

# S44a ships NO migration — the actor-identity substrate is a
# shared_kernel value object plus a decorator, no DB schema change.
# 0016 (the S43 portfolio migration) is already the head on both
# tenant containers per the S43b deploy.
alembic head, postgres-tenant-a: 0016_portfolio_substrate   ✓
alembic head, postgres-tenant-b: 0016_portfolio_substrate   ✓
information_schema.tables on tenant_a: assertions, cases, data_points   ✓
```

## Stage 3 — CLI write path (tenant_a)

The CLI does not pass through HTTP auth middleware; it synthesises
the ActorContext directly via `_actor_context` (D126), resolving
`authorisation_set` through the same `shared_kernel/authorisation.py`
policy the HTTP path uses. The use-case-boundary decorator passes on
each write; the use case persists and emits an audit event.

```
docker compose exec -T padhanam-api python -m apps.cli \
  portfolio create-case --tenant-id a \
  --title "S44a smoke — ActorContext propagation" \
  --case-type PORTFOLIO_ITEM --status OPEN
-> case_id=36be04a4-3ca7-428b-baa3-6ab93571fe1e

docker compose exec -T padhanam-api python -m apps.cli \
  portfolio create-data-point --tenant-id a \
  --case-id 36be04a4-3ca7-428b-baa3-6ab93571fe1e \
  --data-point-type GOAL --value '{"goal": "ship S44a", "progress": 0}'
-> data_point_id=526908d3-7146-4310-8ce3-c2f0a5ec9a4e
-> initial_assertion_id=8c7da501-4334-4675-9b5c-11a34be101bd

docker compose exec -T padhanam-api python -m apps.cli \
  portfolio revise-data-point --tenant-id a \
  --data-point-id 526908d3-7146-4310-8ce3-c2f0a5ec9a4e \
  --value '{"goal": "ship S44a", "progress": 100}' --actor smoke-operator
-> revision_count=2
-> latest_assertion_id=47d12c77-aa32-43f1-afbc-3e026042d77b
-> current_value={'goal': 'ship S44a', 'progress': 100}
```

## Stage 2 — HTTP read surface through ActorContext (tenant_a)

A dev JWT is issued via `padhanam.security.auth.issue_dev_token` for
tenant_a's operator; httpx against `http://localhost:8000` inside
the container. The `get_actor_context` dependency resolves the
registry-backed TenantContext, derives `actor_id` from the
Principal, and resolves the operator `authorisation_set`; the
use-case decorator passes; the adapter returns the rows.

```
GET /api/v1/portfolio/cases                       -> 200
  cases: 2
    36be04a4-... [OPEN]  S44a smoke — ActorContext propagation
    d862e447-... [OPEN]  S43b smoke portfolio item

GET /api/v1/portfolio/cases/36be04a4-...          -> 200
  case 36be04a4-... status OPEN
  data_point 526908d3-... type GOAL  authored_by=operator
    current_value: {'goal': 'ship S44a', 'progress': 100}
    assertion INITIAL  authored_by=operator        {'goal': 'ship S44a', 'progress': 0}
    assertion REVISION authored_by=smoke-operator  {'goal': 'ship S44a', 'progress': 100}
```

The `authored_by` field is the persisted `ActorReference` derived
from `ActorContext.actor_id` (D126 sub-commitment 3): the INITIAL
assertion and DataPoint carry `operator` (the create-data-point
default `--actor`), the REVISION carries `smoke-operator` (the
revise-data-point `--actor`). Different actors stamp different
assertions — `actor.actor_id` propagates through the use case into
the persisted authoring identity end-to-end, and the wire shape
(`authored_by_user_id`) is unchanged from S43b.

## Stage 5 — cross-tenant probe (tenant isolation holds)

```
# tenant_b operator JWT requests tenant_a's case_id
GET /api/v1/portfolio/cases/36be04a4-...  (Bearer tenant_b)  -> 404  error_code=case_not_found

# the auth middleware still fronts every route
GET /api/v1/portfolio/cases  (no credential)                -> 401
```

The tenant_b ActorContext is fully authorised — the decorator
passes — yet the cross-tenant case lookup still returns 404.
Authorisation (the `authorisation_set` check) and tenant isolation
(the `TenantContext` carried inside the ActorContext) are orthogonal
dimensions; the ActorContext supersession does not weaken tenant
isolation.

## Stage 4 — authorisation-denied path (decorator plus 403 translation)

**Structural-honesty note.** The `AuthorisationDenied` → 403 path is
**not reachable through the Phase 2-A HTTP routing surface**:
`get_actor_context` hardcodes `role_list={"operator"}` and resolves
the full operator `authorisation_set`, so every tenant principal
that authenticates is fully authorised for all five portfolio
permissions. This is the expected Phase 2-A state — the p13-epic
flag-for-future-testing table records "Authorisation paths beyond
operator-role check ... No Phase 2-A scenario trips authorisation
rejection paths." A real HTTP request cannot produce an
under-authorised ActorContext until a second role lands at the
role-hierarchy deferred-decisions trigger.

The decorator and the 403 translation are therefore exercised
directly against the **deployed S44a code** in the rebuilt image —
not faked — with an under-authorised ActorContext:

```
ActorContext(actor_id="under-authorised", authorisation_set=frozenset())
@requires_authorisation("portfolio.case.list") wrapped call
-> AuthorisationDenied  permission=portfolio.case.list  actor_id=under-authorised

apps.api._auth_errors._handle_authorisation_denied(...)
-> 403  body={"error_code":"authorisation_denied",
              "message":"the authenticated actor lacks the required
                         authorisation 'portfolio.case.list' for this
                         operation",
              "correlation_id":"smoke-corr-id","details":null}
```

The decorator raises `AuthorisationDenied` carrying the required
permission and the actor_id; the handler at `apps/api/_auth_errors.py`
translates it to a 403 `ErrorResponse` whose message names the
required permission only — never the actor's full set. The
deny path is additionally covered by the unit tests
(`test_authorisation.py`, `test_auth_errors.py`) and the use-case
deny-path tests (`test_use_cases.py`).

## Stage 6 — audit-chain verification (tenant_a)

```
psql SELECT action_verb, resource_type, actor, resource_id
     FROM tenant_audit WHERE resource_id IN (<smoke case>, <smoke dp>)
     ORDER BY timestamp

portfolio.case.create        | case       | operator       | 36be04a4-...
portfolio.data_point.create  | data_point | operator       | 526908d3-...
portfolio.data_point.revise  | data_point | smoke-operator | 526908d3-...
```

One audit event per write on the per-tenant `tenant_audit` chain per
D110 commitment 7; the `actor` column is populated from
`ActorContext.actor_id` via the derived `ActorReference`. The
revise event carries `smoke-operator` and the two create events
carry `operator` — the actor identity threads from the ActorContext
through the use case into the audit trail.

## Verdict

The S44a identity-and-permissions substrate is verified end-to-end
against the live container stack on a freshly-rebuilt image. The
ActorContext propagation path holds: HTTP requests resolve to an
ActorContext at `get_actor_context`, the CLI synthesises an
equivalent ActorContext directly, the use-case-boundary decorator
enforces the `authorisation_set` check, use cases extract
`tenant_context` for adapters, `actor.actor_id` reaches the
persisted `authored_by` and the audit trail, and the
`AuthorisationDenied` → 403 translation holds against the deployed
code. Tenant isolation is unweakened by the supersession. The 403
HTTP routing path is structurally unreachable at Phase 2-A by
design — recorded honestly here and covered by the test layer.
