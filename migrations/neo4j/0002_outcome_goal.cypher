// 0002_outcome_goal.cypher — goal-graph schema (S62, D163).
//
// The whole-life goal taxonomy's typed shape on the shared graph: an
// :Outcome node (the goal), a thin :Lever reference node (the Postgres
// commitment by id, never a copy of its row), and a LEVER_FOR edge
// carrying the mode + (for progressive) the level ladder and current
// target. Written behind the TenantScopedNeo4jSession wrapper; this file
// only lands the uniqueness constraints + tenant-scoped read indexes.
//
// Constraints make the wrapper's MERGE idempotent under re-seed: an
// Outcome is unique per (tenant_id, outcome_id); a Lever is unique per
// (tenant_id, commitment_id) so one commitment is one lever node within a
// tenant. Indexes accelerate the tenant-scoped read predicate every
// goal-graph query carries per D63.
//
// Statements are auto-committed by Neo4j (DDL cannot run inside a
// transaction); IF NOT EXISTS makes each idempotent, and the :_Migration
// node ops.migrate_neo4j writes after the file gives a second file-level
// idempotency check. Statements are separated by a trailing
// semicolon-newline; the runner splits on `;\n`.

CREATE CONSTRAINT outcome_unique_per_tenant IF NOT EXISTS
FOR (o:Outcome)
REQUIRE (o.tenant_id, o.outcome_id) IS UNIQUE;

CREATE CONSTRAINT lever_unique_per_tenant IF NOT EXISTS
FOR (l:Lever)
REQUIRE (l.tenant_id, l.commitment_id) IS UNIQUE;

CREATE INDEX outcome_tenant_id IF NOT EXISTS
FOR (o:Outcome)
ON (o.tenant_id);

CREATE INDEX lever_tenant_id IF NOT EXISTS
FOR (l:Lever)
ON (l.tenant_id);
