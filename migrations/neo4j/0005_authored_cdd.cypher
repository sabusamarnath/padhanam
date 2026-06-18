// 0005_authored_cdd.cypher — the authored CDD element layer (S102, D200).
//
// D200 pivots the CDD from auto-derived to authored-per-goal: the LLM drafts each
// goal's levers, intermediaries, externals, and expected outcome, and the user
// proofs it. This migration lands the two new node types the authored layer needs
// (:Intermediary and :External — the intermediary layer is the uniformly-absent
// layer S101 rendered as a broken link; the external is the inbound the user did
// not initiate, D198) and extends the existing :Lever with a stable lever_id so an
// LLM-drafted lever can exist before it binds to a commitment.
//
// :Outcome is reused for the goal-and-outcome node (D199's two faces already sit on
// one node), so no new constraint for it. The authored FEEDS/INFLUENCES edges have
// no declarative constraint — Community Edition has no relationship-property
// uniqueness; their idempotency comes from the MERGE pattern keyed on
// (tenant_id, source, target) (the SERVES/LEVER_FOR precedent).
//
// Constraint reconciliation (brief-altitude per D200): the existing
// lever_unique_per_tenant on (tenant_id, commitment_id) stays and governs
// commitment-backed levers; lever_id_unique_per_tenant on (tenant_id, lever_id)
// carries authored identity. Neo4j node uniqueness constraints exempt nodes missing
// a constraint property, so an LLM-drafted lever with no commitment_id and a legacy
// matcher lever with no lever_id never collide. No constraint is dropped.
//
// Statements are auto-committed by Neo4j (DDL cannot run inside a transaction);
// IF NOT EXISTS makes each statement idempotent so re-running the migration is a
// no-op. The :_Migration node that `ops.migrate_neo4j` writes after applying the
// file gives a second idempotency check at the file level. Statements are separated
// by a trailing semicolon-newline; the runner splits on `;\n` and skips empties.

CREATE CONSTRAINT intermediary_unique_per_tenant IF NOT EXISTS
FOR (i:Intermediary)
REQUIRE (i.tenant_id, i.element_id) IS UNIQUE;

CREATE INDEX intermediary_tenant_id IF NOT EXISTS
FOR (i:Intermediary)
ON (i.tenant_id);

CREATE CONSTRAINT external_unique_per_tenant IF NOT EXISTS
FOR (x:External)
REQUIRE (x.tenant_id, x.element_id) IS UNIQUE;

CREATE INDEX external_tenant_id IF NOT EXISTS
FOR (x:External)
ON (x.tenant_id);

CREATE CONSTRAINT lever_id_unique_per_tenant IF NOT EXISTS
FOR (l:Lever)
REQUIRE (l.tenant_id, l.lever_id) IS UNIQUE;
