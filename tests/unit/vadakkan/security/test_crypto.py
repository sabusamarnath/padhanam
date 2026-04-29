from __future__ import annotations

import pytest

from vadakkan.security import decrypt_field, encrypt_field


def test_round_trip() -> None:
    plaintext = b"meridian-test-secret"
    context = {"tenant_id": "t1", "field_name": "credential.api_key"}
    enc = encrypt_field(plaintext, context)
    assert decrypt_field(enc, context) == plaintext


def test_context_binding_prevents_replay() -> None:
    plaintext = b"meridian-test-secret"
    context_a = {"tenant_id": "t1", "field_name": "credential.api_key"}
    context_b = {"tenant_id": "t2", "field_name": "credential.api_key"}
    enc = encrypt_field(plaintext, context_a)
    with pytest.raises(Exception):  # cryptography raises InvalidTag
        decrypt_field(enc, context_b)


def test_empty_context_rejected() -> None:
    with pytest.raises(ValueError, match="binding"):
        encrypt_field(b"x", {})


def test_each_call_uses_fresh_dek() -> None:
    plaintext = b"meridian-test-secret"
    context = {"tenant_id": "t1", "field_name": "credential.api_key"}
    a = encrypt_field(plaintext, context)
    b = encrypt_field(plaintext, context)
    # Same plaintext + context but different DEKs → different ciphertexts.
    assert a.ciphertext != b.ciphertext
    assert a.wrapped_dek != b.wrapped_dek
