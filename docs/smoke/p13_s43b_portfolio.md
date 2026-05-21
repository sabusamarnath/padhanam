# P13 S43b — Portfolio context live-stack smoke

Live-stack smoke for the portfolio context (D124, D125): the full
Case → DataPoint → Assertion chain exercised end-to-end via the CLI
write path and the HTTP read surface against tenant_a, on a
freshly-rebuilt `padhanam-api` image with the `0016` migration
freshly applied. Run 2026-05-21 at S43b commit 4.

## Image rebuild plus migration

```
make build-api
# -> docker build -t padhanam-api:dev -f apps/api/Dockerfile .
# -> new image digest sha256:5eaa287edad4bb5a8a56ebe99923f80d8c212ffae0d08d514456ef2a7eccd9d0
# -> compose.yaml padhanam-api digest pin rewritten

docker compose up -d --force-recreate padhanam-api
# -> padhanam-api recreated, healthy

make migrate
# -> phase 2: Running upgrade 0015_optimization_substrate ->
#    0016_portfolio_substrate, create cases, data_points, assertions
#    (D124) — applied to tenant_a AND tenant_b
```

The container-image-lag the structural-honesty discipline guards
against was real: at S43 close the `0016` file was committed to the
source tree but the `padhanam-api` image predated it, so the S43
`make migrate` applied only through `0015`. The S43b rebuild +
recreate + migrate deployed `0016` to both running tenant containers.

## Migration-deployed structural check

```
psql information_schema.tables WHERE table_name IN
  ('cases','data_points','assertions')   -- on each tenant DB

postgres-tenant-a: assertions, cases, data_points   ✓
postgres-tenant-b: assertions, cases, data_points   ✓
```

Durable check committed at
`tests/contract/tenant_isolation/test_portfolio_isolation.py`
(`test_per_tenant_db_has_all_three_portfolio_tables`,
`test_control_plane_db_has_no_portfolio_tables`).

## Stage 1-3 — CLI write path (tenant_a)

```
docker compose exec -T padhanam-api python -m apps.cli \
  portfolio create-case --tenant-id a \
  --title "S43b smoke portfolio item" --case-type PORTFOLIO_ITEM --status OPEN
-> case_id=d862e447-0d73-4758-b757-fa867d5e79d4

docker compose exec -T padhanam-api python -m apps.cli \
  portfolio create-data-point --tenant-id a \
  --case-id d862e447-0d73-4758-b757-fa867d5e79d4 \
  --data-point-type GOAL --value '{"goal": "ship S43b", "progress": 0}'
-> data_point_id=c531dd1d-785a-40bc-b2ac-de1fefffb6b0
-> initial_assertion_id=9bb9b260-e6cb-4e37-8f10-867f00acf1b6

docker compose exec -T padhanam-api python -m apps.cli \
  portfolio revise-data-point --tenant-id a \
  --data-point-id c531dd1d-785a-40bc-b2ac-de1fefffb6b0 \
  --value '{"goal": "ship S43b", "progress": 100}'
-> revision_count=2
-> latest_assertion_id=73c6e211-c07d-4eff-b250-d7d5e4802b54
-> current_value={'goal': 'ship S43b', 'progress': 100}
```

## Stage 4-5 — HTTP read surface (tenant_a)

Dev JWT issued via `padhanam.security.auth.issue_dev_token` for
tenant_a; httpx against `http://localhost:8000` inside the container.

```
GET /api/v1/portfolio/cases                      -> 200
  cases count: 1   titles: ['S43b smoke portfolio item']

GET /api/v1/portfolio/cases/d862e447-...          -> 200
  case d862e447-... status OPEN
  data_points count: 1
    data_point c531dd1d-... type GOAL
    current_value: {'goal': 'ship S43b', 'progress': 100}
    assertions: [
      ('INITIAL',  {'goal': 'ship S43b', 'progress': 0}),
      ('REVISION', {'goal': 'ship S43b', 'progress': 100}),
    ]
```

The HTTP detail surface returns the full Case → DataPoint →
Assertion chain with both assertions in revision-history order — the
Revisable Protocol (D125) holds at runtime end-to-end.

## Stage 6 — audit-event verification (tenant_a)

```
psql SELECT action_verb, resource_type, resource_id FROM tenant_audit
  WHERE action_verb LIKE 'portfolio.%' ORDER BY timestamp

portfolio.case.create        | case       | d862e447-0d73-4758-b757-fa867d5e79d4
portfolio.data_point.create  | data_point | c531dd1d-785a-40bc-b2ac-de1fefffb6b0
portfolio.data_point.revise  | data_point | c531dd1d-785a-40bc-b2ac-de1fefffb6b0
```

One audit event per write, on the per-tenant `tenant_audit` chain
per D110 commitment 7 — every portfolio write is tamper-evidenced by
the audit context's existing hash chain; no parallel chain on the
portfolio tables.

## Verdict

The portfolio context substrate plus HTTP transport is verified
end-to-end against the live container stack: a freshly-rebuilt image,
a freshly-applied per-tenant migration, the CLI write path, the HTTP
read surface, and the audit trail. The S43 commit-9 deployment-honesty
deferral is resolved.
