// 0001_base_constraints.cypher — graph schema baseline (S21, D63, D64).
//
// Lands the entity uniqueness constraint that makes Cypher MERGE
// idempotent under re-extraction (the GraphRepository adapter writes
// entities via MERGE keyed on the same composite). Lands a tenant_id
// index on :Entity to accelerate the tenant-scoped read predicate
// every routing-layer query carries per D63.
//
// Statements are auto-committed by Neo4j (DDL cannot run inside a
// transaction); IF NOT EXISTS makes each statement idempotent so
// re-running the migration is a no-op. The :_Migration node that
// `ops.migrate_neo4j` writes after applying the file gives a second
// idempotency check at the file level.
//
// Statements are separated by a trailing semicolon-newline. The
// migration runner splits on `;\n` and skips empty statements.

CREATE CONSTRAINT entity_unique_per_tenant IF NOT EXISTS
FOR (e:Entity)
REQUIRE (e.tenant_id, e.name, e.entity_type) IS UNIQUE;

CREATE INDEX entity_tenant_id IF NOT EXISTS
FOR (e:Entity)
ON (e.tenant_id);
