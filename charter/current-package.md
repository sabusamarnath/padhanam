# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P3: Tenancy primitives at enterprise grade

**Goal:** Per-tenant data is real. Architectural commitments inherited from P2 (database-per-tenant per D1, jurisdiction as a column per D12, tenant onboarding as configuration per D13, audit as a bounded context per D22, tenant-isolation tests per D24, configuration through `vadakkan/config/` per D19, envelope encryption per D21) move from charter commitments to running code enforced by tests.

**Scope expansion from `packages.md` original line:** "Tenancy primitives" includes the credential and migration machinery that makes per-tenant data real at enterprise grade. Settled at P3 framing in Claude.ai.

**Sessions in this package:**
- S9: Tenancy context scaffolding. `contexts/tenancy/` with the bounded-context structure. Domain model (Tenant, TenantId, EncryptedCredentials, TenantConnectionConfig). Registry port. Compose stack adds postgres-control-plane plus two per-tenant Postgres instances (postgres-tenant-a, postgres-tenant-b) for the test set. Vadkkan-to-Vadakkan directory housekeeping folded in. D32 (instance topology) and D33 (control-plane separation) appended.
- S10: Control-plane database and registry adapter. Alembic configured for control-plane track. Registry Postgres adapter implementing CRUD with credential encryption via `vadakkan/security/crypto.py`. Tenant-isolation tests for the registry adapter. Security events on credential operations, audit events on registry mutations. D-entry for credential encryption integration covering write/read path discipline plus three-control leak prevention. `ops/scheduled_checks.yaml` and runner deferred from S9 lands here.
- S11: Per-tenant connection resolution and migration runner. Routing layer in `vadakkan/config/` reads registry, decrypts credentials, returns per-tenant AsyncSession factory. Per-tenant Alembic track wired. `make migrate` runs both phases in order (control-plane first, per-tenant second). Per-tenant initial schema applied. D-entry for migration runner shape.
- S12: Audit context real adapter and end-to-end verification. Audit adapter replaces no-op (since S5) with real Postgres adapter writing hash-chained events to per-tenant audit tables. Integration test for the full slice: authenticated request → tenant-scoped endpoint → routing → tenant database → hash-chained audit write → Langfuse trace with tenant_id and jurisdiction attributes. Browser verification of trace structure mid-session per the standing rule.

**Status:** P3 in progress. Session breakdown committed at framing. S13 acknowledged as available pre-open if S11 splits.

**Notes:** Topology choice (Option A: two instances at P3 open for the test set, instance creation deferred until production deployment context arrives) breaches D13 ("tenant onboarding is configuration, not deployment") for P3 specifically: adding a third tenant in P3 requires editing Compose. The breach is acknowledged and recovered when instance creation lands. The honest framing in the P3 archive document at close is that P3 ships the registry-and-routing half of the principle and the instance-creation half is deferred.
