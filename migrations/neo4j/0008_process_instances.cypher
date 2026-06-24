// 0008_process_instances.cypher — opportunities as Flow items (S103h, D208).
//
// D198/D208: an opportunity (one company/role) is a first-class process instance,
// a :Opportunity Flow item belonging to the goal by outcome_id, positioned at its
// furthest-evidenced gate by current_gate_id, grouping its units by a
// (:Unit)-[:BELONGS_TO]->(:Opportunity) edge. A clustered unit's gate-element
// binds read per opportunity (the unit's BELONGS_TO attributes them), so the gate
// pile distributes across opportunities plus an honest unclustered residual (D171).
//
// This migration adds the :Opportunity uniqueness constraint (the 0005/0007
// authored-node pattern, REQUIRE (tenant_id, <id>) IS UNIQUE) and a range index on
// BELONGS_TO(tenant_id) so the tenant-scoped membership reads stay indexed. The
// BELONGS_TO edge carries no declarative uniqueness (Community Edition has none for
// relationship properties); its idempotency comes from the MERGE pattern keyed on
// (tenant_id, unit, opportunity). IF NOT EXISTS makes both idempotent.

CREATE CONSTRAINT opportunity_unique_per_tenant IF NOT EXISTS
FOR (o:Opportunity)
REQUIRE (o.tenant_id, o.opportunity_id) IS UNIQUE;

CREATE INDEX belongs_to_tenant_id IF NOT EXISTS
FOR ()-[r:BELONGS_TO]-()
ON (r.tenant_id);
