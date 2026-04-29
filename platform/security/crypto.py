"""Field-level encryption via envelope encryption (D21).

A KEK wraps per-row DEKs; only DEKs touch field data. Dev profile uses a
fixed KEK from SecuritySettings; prod profile resolves the KEK to a KMS-
managed key via the SecretManagerSource hook in platform/config/.

The associated_data parameter binds ciphertext to its context (tenant_id,
field_name) so the same ciphertext cannot be replayed across fields.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from platform.config import SecuritySettings

DEK_LEN = 32
NONCE_LEN = 12
KEY_VERSION = 1


@dataclass(frozen=True)
class EncryptedField:
    """Wire format for an encrypted field.

    wrapped_dek: DEK encrypted under the KEK (with its own nonce + AEAD tag).
    ciphertext: field plaintext encrypted under the DEK.
    nonce: nonce used for the field encryption.
    key_version: KEK version, for future rotation.
    """

    wrapped_dek: bytes
    dek_wrap_nonce: bytes
    ciphertext: bytes
    nonce: bytes
    key_version: int


def _kek() -> bytes:
    return bytes.fromhex(SecuritySettings().kek_hex)


def _serialize_aad(context: dict[str, str]) -> bytes:
    """Stable JSON serialization of associated data."""
    return json.dumps(context, sort_keys=True, separators=(",", ":")).encode()


def encrypt_field(plaintext: bytes, context: dict[str, str]) -> EncryptedField:
    """Encrypt a field under a fresh DEK wrapped by the KEK.

    context must include enough binding information that misuse is detectable
    on decrypt (e.g. tenant_id, field_name).
    """
    if not context:
        raise ValueError("context must include at least one binding key")

    aad = _serialize_aad(context)
    dek = os.urandom(DEK_LEN)
    nonce = os.urandom(NONCE_LEN)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, aad)

    dek_wrap_nonce = os.urandom(NONCE_LEN)
    wrapped_dek = AESGCM(_kek()).encrypt(dek_wrap_nonce, dek, aad)

    return EncryptedField(
        wrapped_dek=wrapped_dek,
        dek_wrap_nonce=dek_wrap_nonce,
        ciphertext=ciphertext,
        nonce=nonce,
        key_version=KEY_VERSION,
    )


def decrypt_field(field: EncryptedField, context: dict[str, str]) -> bytes:
    """Decrypt a field. Mismatched context raises (AAD binding)."""
    if field.key_version != KEY_VERSION:
        raise ValueError(
            f"unknown KEK version {field.key_version}; rotation logic lands "
            "with the production KMS adapter"
        )
    aad = _serialize_aad(context)
    dek = AESGCM(_kek()).decrypt(field.dek_wrap_nonce, field.wrapped_dek, aad)
    return AESGCM(dek).decrypt(field.nonce, field.ciphertext, aad)
