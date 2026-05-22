# P13 S44b — Intake substrate and intake-canonical orchestration live-stack smoke

Live-stack smoke for the S44b intake substrate (D127, D128): the
full intake-canonical propagation path exercised end-to-end against
tenant_a on a freshly-rebuilt `padhanam-api` image — the standalone
intake surface, the three write-side orchestrations, the CLI write
path, cross-tenant isolation, and the audit chain. Run 2026-05-22
at S44b commit 11.

## Stage 1 — image rebuild plus migration verification

```
make build-api
# -> docker build -t padhanam-api:dev -f apps/api/Dockerfile .
# -> new image digest sha256:19bb59c3ca62938ff28a89c3e23711f7728413473108b9e68678dc77a0b6e44e
# -> compose.yaml padhanam-api digest pin rewritten

docker compose up -d --force-recreate padhanam-api   # -> healthy

make migrate
# -> Running upgrade 0016_portfolio_substrate -> 0017_intake_substrate
# -> Running upgrade 0017_intake_substrate -> 0018_intake_id_columns
#    applied to tenant_a AND tenant_b

alembic head, postgres-tenant-a: 0018_intake_id_columns   ✓
alembic head, postgres-tenant-b: 0018_intake_id_columns   ✓
information_schema: intakes table present on tenant_a       ✓
information_schema: intake_id column on cases, assertions   ✓
```

## Stage 2 — standalone intake (HTTP POST /api/v1/intakes)

Dev JWT issued via `padhanam.security.auth.issue_dev_token` for
tenant_a's operator; httpx against `http://localhost:8000` inside
the container.

```
POST /api/v1/intakes  {"raw_text": "...", "intent_hint": "note"}  -> 201
  intake id=2090ee60-...  intake_source=MANUAL_ENTRY
```

The operator-records-without-acting path: an IntakeRecord persists
with no downstream portfolio write.

## Stage 3 — intake-and-case orchestration (POST /api/v1/portfolio/cases)

```
POST /api/v1/portfolio/cases  {"title": "...", "raw_text": "..."}  -> 201
  case_id=1829b013-...  intake_id=79cd2757-...
```

`record_intake_and_create_case` recorded an IntakeRecord first,
then created the Case through the `PortfolioWriter` consumer port
with `intake_id` propagated — the response carries it. The Case row
on tenant_a verifies `intake_id IS NOT NULL`.

## Stage 4 — intake-and-data-point orchestrations

```
POST /api/v1/portfolio/data_points
  {"case_id": "...", "data_point_type": "GOAL", "value": {...}}     -> 201
  data_point_id=8697e021-...  intake_id=0b0b816d-...

PATCH /api/v1/portfolio/data_points/8697e021-...
  {"value": {"progress": 100}, "raw_text": "mark it done"}          -> 200
  revision_count=2  intake_id=fa8ab6c6-...
```

`record_intake_and_create_data_point` stamps the intake_id on the
INITIAL assertion; `record_intake_and_revise_data_point` stamps it
on the appended REVISION assertion. Each carries its own
IntakeRecord.

## Stage 5 — CLI write path via the orchestration

```
docker compose exec -T padhanam-api python -m apps.cli \
  portfolio create-case --tenant-id a \
  --title "S44b CLI smoke case" --actor cli-smoke-operator
-> case_id=25a2d270-...
-> intake_id=13dc9ff2-...
-> status=OPEN
```

The CLI synthesises the ActorContext and a ManualEntryPayload,
drives `record_intake_and_create_case` through the CLI-local
`_CliPortfolioWriter`, and prints the intake_id the case traces to.

## Stage 6 — cross-tenant probe (isolation holds)

```
# tenant_b's JWT PATCHes tenant_a's data_point_id
PATCH /api/v1/portfolio/data_points/8697e021-...  (Bearer tenant_b)
  -> 404  error_code=data_point_not_found

# the auth middleware still fronts every write route
POST /api/v1/portfolio/cases  (no credential)   -> 401
```

A tenant_b request resolves to tenant_b's data plane; tenant_a's
data point is not found there — 404. The intake-canonical write
path does not weaken tenant isolation. (Per the D128 two-transaction
intake-first ordering, the tenant_b request did record an intake on
tenant_b's plane before the downstream lookup failed — the honest
record-of-attempt.)

## Stage 7 — audit-chain verification

```
psql SELECT action_verb, resource_type, actor FROM tenant_audit
     WHERE action_verb LIKE 'intake.%' OR action_verb LIKE 'portfolio.%'
     ORDER BY timestamp DESC

portfolio.case.create        | case       | cli-smoke-operator
intake.record.create         | intake     | cli-smoke-operator
portfolio.data_point.revise  | data_point | smoke-operator
intake.record.create         | intake     | smoke-operator
portfolio.data_point.create  | data_point | smoke-operator
intake.record.create         | intake     | smoke-operator
portfolio.case.create        | case       | smoke-operator
intake.record.create         | intake     | smoke-operator
...
```

Every orchestration emits **two** audit events on the per-tenant
`tenant_audit` chain — the `intake.record.create` first, then the
downstream `portfolio.*` event — both stamped with the actor_id.
The standalone POST /intakes emits the single `intake.record.create`.
The smoke Case row carries a non-null `intake_id`: every persisted
portfolio state change at the platform's write surfaces traces to an
IntakeRecord per D128.

## Stage 8 — intake read routes

```
GET /api/v1/intakes/{intake_id}                  -> 200
GET /api/v1/intakes                              -> 200  count=4
GET /api/v1/intakes?source=MANUAL_ENTRY          -> 200  count=4
```

The four intakes are the standalone record plus the three the
write orchestrations recorded; the source filter returns all four
(MANUAL_ENTRY is the single Phase 2-A source).

## Verdict

The S44b intake substrate is verified end-to-end against the live
container stack on a freshly-rebuilt image with migrations 0017 and
0018 freshly applied to both tenant data planes. The intake-canonical
propagation path holds: standalone intake recording, the three
write-side orchestrations (case, data-point, revise) through the
consumer-defined `PortfolioWriter` port, the CLI write path, and the
intake read routes. Every write traces to an IntakeRecord via
`intake_id` and emits paired audit events. Tenant isolation is
unweakened by the write surface. D128's intake-canonical commitment
is operational for the portfolio context's write surfaces.
