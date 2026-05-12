"""Tools bounded context (D68, D89).

New bounded context at Phase 1 / S28b. Houses the `Tool` and
`ToolRevision` aggregates with hash-chain audit per D26 and revision
shape per D31; the classification taxonomy with three-to-three
invariant mapping per D89; the schema-diff BC stub at revision
creation; and the public query surface for cross-context lookups.

Storage lives on the control-plane Postgres instance per D33 and D89's
storage-location resolution (alongside methodologies and roles).
Per-tenant tool authoring defers to Phase 2 per the deferred-decisions
entry on customer-deployment evidence.

The agent context consumes this context via two thin ports
(`ToolDefinitionsLookup`, `ToolInvoker`) at
`contexts/agent/application/ports/`; wiring adapters at
`apps/cli/_cross_context.py` implement those ports by calling into
the tools context's facade per D17.
"""
