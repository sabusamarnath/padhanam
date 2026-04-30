from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from contexts.tenancy.domain import EncryptedCredentials


def test_constructs_with_bytes_fields() -> None:
    ec = EncryptedCredentials(
        wrapped_dek=b"\x01\x02",
        ciphertext=b"\x03\x04",
        aad=b"\x05",
    )
    assert ec.wrapped_dek == b"\x01\x02"
    assert ec.ciphertext == b"\x03\x04"
    assert ec.aad == b"\x05"


def test_is_immutable() -> None:
    ec = EncryptedCredentials(wrapped_dek=b"a", ciphertext=b"b", aad=b"c")
    with pytest.raises(FrozenInstanceError):
        ec.wrapped_dek = b"x"  # type: ignore[misc]


def test_equality_by_byte_content() -> None:
    a = EncryptedCredentials(wrapped_dek=b"a", ciphertext=b"b", aad=b"c")
    b = EncryptedCredentials(wrapped_dek=b"a", ciphertext=b"b", aad=b"c")
    other = EncryptedCredentials(wrapped_dek=b"a", ciphertext=b"b", aad=b"d")
    assert a == b
    assert a != other
    assert hash(a) == hash(b)
