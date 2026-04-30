"""Tenant aggregate.

Composes the validated TenantId, the Jurisdiction (reused from
shared_kernel/ per D16), the EncryptedCredentials, and tenant-level
metadata (display name, created_at, status). The aggregate is the unit
the registry returns; routing reads its EncryptedCredentials and decrypts
through `vadakkan/security/crypto.py` (S11).

Domain code is framework-free (D16). Status is a stdlib StrEnum, not a
Pydantic Literal; created_at is a stdlib datetime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from shared_kernel import Jurisdiction

from contexts.tenancy.domain.encrypted_credentials import EncryptedCredentials
from contexts.tenancy.domain.tenant_id import TenantId


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPROVISIONED = "deprovisioned"


@dataclass(frozen=True)
class Tenant:
    id: TenantId
    jurisdiction: Jurisdiction
    display_name: str
    credentials: EncryptedCredentials
    status: TenantStatus
    created_at: datetime
