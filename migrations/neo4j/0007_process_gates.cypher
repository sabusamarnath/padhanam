// 0007_process_gates.cypher — the process flow as first-class gates (S103g, D207).
//
// D198/D207: the framework's process layer becomes first-class :Gate nodes — a
// new flow sequenced by gate_order, scoped to the goal by outcome_id, referencing
// the D163 lever-steps where one corresponds (the gates do not replace the steps;
// the steps stay as the goal's sequence-status, D163). Each gate is a portal into
// its local CDD; the gate node is the local-outcome endpoint (parallel to
// :Outcome for the goal), so an intermediary FEEDS the gate. Gate-scoped authored
// elements gain a gate_id property (the dual rollup: outcome_id for goal coverage,
// gate_id for the gate); goal-level elements simply lack gate_id.
//
// This migration adds the :Gate node's uniqueness constraint — the same pattern
// 0005 used for :Intermediary / :External (REQUIRE (tenant_id, <id>) IS UNIQUE).
// The gate_id property on elements is schemaless (no constraint), like outcome_id
// on elements. The intra-gate FEEDS/INFLUENCES edges reuse the existing authored
// edge types (already present since 0005); no new edge type, no new index beyond
// the constraint's backing index. IF NOT EXISTS makes it idempotent.

CREATE CONSTRAINT gate_unique_per_tenant IF NOT EXISTS
FOR (g:Gate)
REQUIRE (g.tenant_id, g.gate_id) IS UNIQUE;
