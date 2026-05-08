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
"""

from __future__ import annotations

from contexts.methodology.application import (
    create_methodology_template,
    get_methodology_template,
    list_methodology_templates,
    retire_methodology_template,
    update_methodology_template,
)

__all__ = [
    "create_methodology_template",
    "get_methodology_template",
    "list_methodology_templates",
    "retire_methodology_template",
    "update_methodology_template",
]
