"""Public query interface for the agent context (D17, D75).

Per D17, every context exposes a single api.py at its root with the
read-only query methods other contexts may call. The agent context's
read surface is the five CRUD use cases under
``contexts.agent.application`` re-exported here. The cross-context
``create_agent_from_methodology`` flow at S25 consumes methodology
templates through ``contexts.methodology.api``; the inverse direction
(agent → methodology) is the only cross-context edge at P7.

The agent context is per-tenant-scoped per D32; every API method
carries a ``TenantContext`` parameter, mirroring the per-tenant
adapters at ``contexts/audit/``, ``contexts/evaluation/``,
``contexts/ingestion/`` and inverting the methodology context's
control-plane-scoped facade per D75.

Use cases land at S24 commit 8; this file gains the re-export
bindings at that commit.
"""
