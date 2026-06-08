// 0003_outcome_props_to_node.cypher — move goal-level properties from the
// LEVER_FOR edge to the :Outcome node (S63, D163 clarification, D165).
//
// The S62 schema (0002) placed mode + ladder + current_target_level on the
// LEVER_FOR edge. The D163 clarification (S63) specifies these are goal-level
// properties of the :Outcome node, not the edge: a goal has one mode and one
// target and may have many levers. This is the first graph *data* migration
// (0002 lands only constraints/indexes); it moves any existing instance —
// German, seeded at S62 — in place with no data loss, then strips the edge.
//
// Idempotency (D165): on the first run the edge carries the properties and the
// node does not, so `coalesce(o.x, r.x)` copies them up; `REMOVE` strips the
// edge. On a second run the edge no longer carries them and the WHERE guard
// (`r.mode IS NOT NULL`) matches nothing, so the statement is a no-op. The
// runner's `:_Migration` version node gates re-application a second way. The
// move is tenant-agnostic by design: it is a structural data move across every
// tenant's outcomes on the shared instance, mirroring 0001/0002's global DDL.
//
// Statements are separated by a trailing semicolon-newline; the runner splits
// on `;\n`. This is a write transaction under Neo4j auto-commit (not DDL).

MATCH (l:Lever)-[r:LEVER_FOR]->(o:Outcome)
WHERE r.mode IS NOT NULL
SET o.mode = coalesce(o.mode, r.mode),
    o.ladder = coalesce(o.ladder, r.ladder),
    o.current_target_level = coalesce(o.current_target_level, r.current_target_level)
REMOVE r.mode, r.ladder, r.current_target_level;
