"""TenantContext value object — the per-request tenant identity payload.

Carries the three attributes that flow from registry resolution into the
inference path: ``tenant_id`` (UUID-shaped), ``jurisdiction``, and
``cost_attribution_id`` (D41). The object is referentially equal across
contexts (the inference adapter and the audit adapter both consume
TenantContext-shaped values), which is why it lives in shared_kernel/
rather than in any single context.

Shape choice (S15 D-entry): ``dataclass(frozen=True)`` with
``__post_init__`` validation. Pydantic is forbidden in shared_kernel by
the import-linter ``shared-kernel-policed`` contract per D16, so the
choice between Pydantic and dataclass is structurally pre-empted; the
``Tenant`` aggregate's ``frozen=True`` precedent makes the shape
consistent with the rest of the domain.

Classification field deferred per S15 framing decision option C: no
``classification`` column exists on ``tenant_registry`` and no tenant-
configuration table exists at P4. Classification lands at whichever
package genuinely consumes it (P7 or P8 per ``charter/packages/
p4-epic.md`` out-of-scope). Adding the field here without a column or
consumer would be paper architecture.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    jurisdiction: str
    cost_attribution_id: str

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("TenantContext.tenant_id must be non-empty")
        if not self.jurisdiction:
            raise ValueError("TenantContext.jurisdiction must be non-empty")
        if not self.cost_attribution_id:
            raise ValueError(
                "TenantContext.cost_attribution_id must be non-empty"
            )
