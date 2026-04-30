from __future__ import annotations

from enum import StrEnum

from pydantic import field_validator

from vadakkan.config.base import VadakkanSettings


class AuthBackend(StrEnum):
    DEV_SIGNED_TOKEN = "dev_signed_token"
    KEYCLOAK = "keycloak"


class SecuritySettings(VadakkanSettings):
    """Crypto, auth, and policy configuration.

    Dev profile carries fixed material so the smoke tests run without .env
    edits. Production resolves the KEK to a KMS-managed key (D21) and the
    auth backend to Keycloak (D23, D3); the production swap is the profile
    selection plus SecretManagerSource (see base.py), not a code change.
    """

    # 32-byte KEK as 64 hex chars. Replaced in prod by KMS-resolved value (D21).
    kek_hex: str = (
        "00000000000000000000000000000000"
        "00000000000000000000000000000001"
    )
    # Symmetric key for dev-signed token verification (D23). Replaced in prod
    # by Keycloak public-key validation.
    auth_token_signing_key: str = (
        "dev-only-signing-key-not-for-production-use-32b"
    )
    auth_backend: AuthBackend = AuthBackend.DEV_SIGNED_TOKEN

    @field_validator("kek_hex")
    @classmethod
    def kek_must_be_32_bytes(cls, v: str) -> str:
        try:
            raw = bytes.fromhex(v)
        except ValueError as e:
            raise ValueError("kek_hex must be valid hex") from e
        if len(raw) != 32:
            raise ValueError("kek_hex must decode to 32 bytes (256 bits)")
        return v
