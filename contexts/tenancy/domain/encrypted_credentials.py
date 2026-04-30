"""EncryptedCredentials value object — wrapped DEK + ciphertext.

This is the persistent form of a tenant's database credentials, per D21
envelope encryption. The wrapped DEK is the per-row Data Encryption Key
encrypted by the KEK; the ciphertext is the credentials encrypted by
the DEK. Neither field is plaintext at rest or in this object.

Unwrapping happens at the routing layer in `vadakkan/security/crypto.py`
(lands S11) which returns a transient `TenantConnectionConfig` whose
plaintext does not persist beyond function-call scope.

Domain code is framework-free per D16. The bytes shape is the storage-
neutral representation; the registry adapter at S10 maps these to the
appropriate column types (LargeBinary in SQLAlchemy).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EncryptedCredentials:
    wrapped_dek: bytes
    ciphertext: bytes
    aad: bytes
