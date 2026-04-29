# Tenant isolation contract tests

Cross-tenant access tests for every adapter that touches tenant-scoped data
(D24).

## Pattern

Each test:

1. Arranges two principals (one per tenant) using the `tenant_a_principal`
   and `tenant_b_principal` fixtures from `conftest.py`.
2. Attempts a cross-tenant operation as principal A targeting tenant B's
   resource (or vice versa).
3. Asserts the operation either fails authorization (DENY) or correctly
   scopes to A's own tenant (ALLOW for legitimate paths).

Tests are red-team shaped: they prove the path that is most likely to go
wrong in a multi-tenant system — unintended cross-tenant data flow through
poorly scoped queries.

## Coverage rule

Every module under `contexts/*/adapters/outbound/` that references
`tenant_id` must have a corresponding test in this directory. The S5 baseline
ships only the no-op audit adapter and its example test; P3 adds real
adapters (audit Postgres, tenant registry, retrieval clients) and the
isolation tests that go with them.

## Why "contract" tests, not "integration"

Each test in this directory is a contract that an adapter must satisfy
regardless of its underlying implementation. Tests should be parametrized
across adapter implementations once we have more than one (e.g. swapping
between database-per-tenant and schema-per-tenant for a future deployment
profile). The harness is structured so adding a parametrization later does
not rewrite individual test bodies.

## Layout

- `conftest.py` — shared two-principal fixtures.
- `test_<adapter>_isolation.py` — one file per adapter implementation that
  needs isolation coverage.
