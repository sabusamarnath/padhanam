"""TenantId value object — the validated, UUID-shaped tenant identifier.

The tenancy context owns the canonical TenantId (it owns the Tenant
aggregate). `shared_kernel.TenantId` is the str-shaped typing primitive
used across contexts that carry tenant_id as a parameter. This rich
value object is the construction-and-validation point: the registry
adapter at S10 builds it from a UUID column, and the api facade returns
it via a Tenant.

UUID-shape is enforced at construction; an attempt to build TenantId
from a non-UUID string raises ValueError synchronously. Domain code is
framework-free per D16; UUID validation uses stdlib uuid.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class TenantId:
    value: str

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.value)
        except (ValueError, AttributeError, TypeError) as e:
            raise ValueError(
                f"TenantId must be a UUID string; got {self.value!r}"
            ) from e

    def __str__(self) -> str:
        return self.value
