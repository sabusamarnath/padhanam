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

## Control-plane-shape inversion (D74)

Some bounded contexts are control-plane-scoped, not per-tenant: the tenant
registry (D33) and the methodology context (D74) live on
`postgres-control-plane` rather than per-tenant data planes. Their data
is platform-managed and visible across tenants by design (the inverse of
agent isolation per the P7 epic note). Their isolation tests exercise the
inversion pattern:

- Tenant-context callers can **read** templates and revisions across
  tenants (no policy gating; the read facade accepts any authenticated
  context).
- Tenant-context callers are **rejected at write paths** with
  `AuthorizationError` — only operator-context callers can mutate
  control-plane state.
- Operator-context callers can read and write.
- `tenant_id` has no semantic role in the data; the FK or scoping
  predicate that exists on per-tenant tables is absent here.

`test_methodology_isolation.py` is the second instance of this inversion
pattern (after the tenant registry's `test_registry_isolation.py`); future
control-plane contexts inherit the same shape.

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
