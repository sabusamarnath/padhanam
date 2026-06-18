// 0006_element_evidence.cypher — the element-evidence edge (S103b, D202).
//
// D202 binds ingested work to the authored element it serves, not the goal as a
// whole: a (:Unit)-[:EVIDENCES]->(authored element) edge is the primary evidence
// write, replacing the goal-level (:Unit)-[:SERVES]->(:Outcome) write (which is
// retired — the goal level is derived on read from element evidence to prevent
// drift, D155). The edge target is a :Lever (lever_id), :Intermediary / :External
// (element_id), or the :Outcome goal node (outcome_id) — the authored-endpoint
// whitelist from 0005.
//
// Like SERVES / FEEDS / INFLUENCES, the edge carries no declarative uniqueness
// constraint (Community Edition has no relationship-property uniqueness); its
// idempotency comes from the MERGE pattern keyed on (tenant_id, unit, element),
// and the matcher replaces the tenant's EVIDENCES set each run (derived state).
// This migration adds only a relationship range index on EVIDENCES(tenant_id) so
// the tenant-scoped evidence reads stay indexed; IF NOT EXISTS makes it
// idempotent, and the :_Migration node the runner writes gives a file-level
// idempotency check. No direction property this session (S104, D203); no
// embedding tier (S100 empty corpus).

CREATE INDEX evidences_tenant_id IF NOT EXISTS
FOR ()-[r:EVIDENCES]-()
ON (r.tenant_id);
