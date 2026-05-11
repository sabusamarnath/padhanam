"""Public query interface for the methodology context (D17, D74, D86).

Per D17, every context exposes a single api.py at its root with read-
only query methods other contexts may call. The methodology context's
read surface comprises both the methodology aggregate's use cases
(D74) and the role aggregate's use cases (D86; co-located with
methodology per D86's Y2 sub-choice).

Cross-context callers consume through this facade:

- Agent context's ``create_agent_from_methodology`` flow at S25
  (D79) calls ``get_methodology_template`` via the
  ``MethodologyLookup`` Protocol port.
- Agent context's S26a-2 ``create_agent_from_role`` flow will call
  ``get_role_template`` via the new ``RoleLookup`` Protocol port.
- Agent's ``MethodologyView`` adapter at ``apps/cli/_runtime.py``
  resolves ``role_refs`` by calling ``get_role_template`` per role
  reference.

The methodology context is control-plane-scoped per D33; the API
surface carries no TenantContext parameter because both aggregates
are platform-managed and visible across tenants by design (the
inverse of agent isolation per the P7 epic note).
"""

from __future__ import annotations

from contexts.methodology.application import (
    RoleRef,
    create_methodology_template,
    create_role_template,
    get_methodology_template,
    get_role_template,
    list_methodology_templates,
    list_role_templates,
    retire_methodology_template,
    retire_role_template,
    update_methodology_template,
    update_role_template,
)

__all__ = [
    "RoleRef",
    "create_methodology_template",
    "create_role_template",
    "get_methodology_template",
    "get_role_template",
    "list_methodology_templates",
    "list_role_templates",
    "retire_methodology_template",
    "retire_role_template",
    "update_methodology_template",
    "update_role_template",
]
