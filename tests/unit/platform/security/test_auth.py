from __future__ import annotations

import pytest

from platform.security.auth import AuthError, issue_dev_token, verify_credential


def test_valid_token_yields_principal() -> None:
    token = issue_dev_token("alice", "tenant-a", ["audit.read", "audit.write"])
    principal = verify_credential(token)
    assert principal.subject == "alice"
    assert principal.tenant_id == "tenant-a"
    assert "audit.read" in principal.roles
    assert principal.credential_ref.endswith("...")


def test_tampered_token_rejected() -> None:
    token = issue_dev_token("alice", "tenant-a", ["audit.read"])
    tampered = token[:-4] + "xxxx"
    with pytest.raises(AuthError, match="invalid"):
        verify_credential(tampered)


def test_missing_token_rejected() -> None:
    with pytest.raises(AuthError, match="invalid"):
        verify_credential("")
