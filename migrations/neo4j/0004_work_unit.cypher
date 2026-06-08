// 0004_work_unit.cypher — the unit-of-work correlation graph baseline (S66, D168).
//
// Lands the uniqueness constraints that make the correlation MERGEs idempotent
// (the :Unit anchor and the thin :Facet reference node), plus tenant_id indexes
// to accelerate the tenant-scoped read + replace predicates every correlation
// query carries (D63). The SAME_WORK edge has no declarative constraint —
// Community Edition has no relationship-property uniqueness; its idempotency
// comes from the MERGE pattern keyed on (tenant_id, facet_type, facet_id,
// unit_id) plus the per-tenant replace-on-correlate.
//
// Statements are auto-committed by Neo4j (DDL cannot run inside a transaction);
// IF NOT EXISTS makes each statement idempotent so re-running the migration is a
// no-op. The :_Migration node that `ops.migrate_neo4j` writes after applying the
// file gives a second idempotency check at the file level.
//
// Statements are separated by a trailing semicolon-newline. The migration runner
// splits on `;\n` and skips empty statements.

CREATE CONSTRAINT unit_unique_per_tenant IF NOT EXISTS
FOR (u:Unit)
REQUIRE (u.tenant_id, u.unit_id) IS UNIQUE;

CREATE INDEX unit_tenant_id IF NOT EXISTS
FOR (u:Unit)
ON (u.tenant_id);

CREATE CONSTRAINT facet_unique_per_tenant IF NOT EXISTS
FOR (f:Facet)
REQUIRE (f.tenant_id, f.facet_type, f.facet_id) IS UNIQUE;

CREATE INDEX facet_tenant_id IF NOT EXISTS
FOR (f:Facet)
ON (f.tenant_id);
