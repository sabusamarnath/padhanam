"""Public query interface for the methodology context (D17, D74).

Per D17, every context exposes a single api.py at its root with read-
only query methods other contexts may call. Methodology's read surface
is the use cases under ``contexts.methodology.application`` re-exported
here. Cross-context callers (the agent context at S24, the
create_agent_from_methodology flow at S25) consume methodology
templates and revisions through this facade.

The methodology context is control-plane-scoped per D33; the API
surface carries no TenantContext parameter because methodology data
is platform-managed and visible across tenants by design (the inverse
of agent isolation per the P7 epic note).

Use cases land at S23 commit 8; this file gains the re-export bindings
at that commit.
"""
