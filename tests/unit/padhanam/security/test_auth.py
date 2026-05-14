from __future__ import annotations

import jwt
import pytest

from padhanam.config import SecuritySettings
from padhanam.security.auth import (
    ALGORITHM,
    AuthError,
    PlatformOperatorPrincipal,
    PrincipalType,
    issue_dev_token,
    issue_platform_operator_dev_token,
    verify_credential,
)
from shared_kernel import TenantId


def test_valid_token_yields_principal() -> None:
    token = issue_dev_token("alice", "tenant-a", ["audit.read", "audit.write"])
    principal = verify_credential(token)
    assert principal.subject == "alice"
    assert principal.tenant_id == "tenant-a"
    assert "audit.read" in principal.roles
    assert principal.credential_ref.endswith("...")
    assert principal.principal_type is PrincipalType.TENANT


def test_tampered_token_rejected() -> None:
    token = issue_dev_token("alice", "tenant-a", ["audit.read"])
    tampered = token[:-4] + "xxxx"
    with pytest.raises(AuthError, match="invalid"):
        verify_credential(tampered)


def test_missing_token_rejected() -> None:
    with pytest.raises(AuthError, match="invalid"):
        verify_credential("")


def test_legacy_token_without_principal_type_defaults_to_tenant() -> None:
    """D103: backward-compat — tokens minted before S37 have no
    ``principal_type`` claim; verify_credential defaults to TENANT."""
    settings = SecuritySettings()
    payload = {"sub": "alice", "tenant_id": "tenant-a", "roles": ["audit.read"]}
    legacy_token = jwt.encode(
        payload, settings.auth_token_signing_key, algorithm=ALGORITHM
    )
    principal = verify_credential(legacy_token)
    assert principal.principal_type is PrincipalType.TENANT
    assert principal.tenant_id == "tenant-a"


def test_platform_operator_token_yields_platform_operator_principal() -> None:
    token = issue_platform_operator_dev_token("ops-1")
    principal = verify_credential(token)
    assert principal.subject == "ops-1"
    assert principal.principal_type is PrincipalType.PLATFORM_OPERATOR
    assert principal.tenant_id == TenantId("")
    assert principal.roles == frozenset()


def test_platform_operator_token_omits_operator_role_by_default() -> None:
    """D103 alternative (j): the dev-mint helper omits OPERATOR_ROLE
    because platform-operator and tenant-scoped operator-context are
    distinct categories."""
    token = issue_platform_operator_dev_token("ops-1")
    principal = verify_credential(token)
    assert "padhanam.operator" not in principal.roles


def test_platform_operator_token_can_carry_explicit_roles() -> None:
    token = issue_platform_operator_dev_token("ops-1", roles=["audit.read"])
    principal = verify_credential(token)
    assert "audit.read" in principal.roles


def test_tenant_token_missing_tenant_id_rejected() -> None:
    """D103 conditional validation: tenant-typed tokens must carry
    a tenant_id claim."""
    settings = SecuritySettings()
    payload = {
        "sub": "alice",
        "roles": ["audit.read"],
        "principal_type": PrincipalType.TENANT.value,
    }
    bad_token = jwt.encode(
        payload, settings.auth_token_signing_key, algorithm=ALGORITHM
    )
    with pytest.raises(AuthError, match="principal_type='tenant'"):
        verify_credential(bad_token)


def test_platform_operator_token_with_tenant_id_rejected() -> None:
    """D103 conditional validation: platform-operator-typed tokens
    must not carry a tenant_id claim."""
    settings = SecuritySettings()
    payload = {
        "sub": "ops-1",
        "tenant_id": "tenant-a",
        "roles": [],
        "principal_type": PrincipalType.PLATFORM_OPERATOR.value,
    }
    bad_token = jwt.encode(
        payload, settings.auth_token_signing_key, algorithm=ALGORITHM
    )
    with pytest.raises(AuthError, match="principal_type='platform_operator'"):
        verify_credential(bad_token)


def test_unknown_principal_type_rejected() -> None:
    settings = SecuritySettings()
    payload = {
        "sub": "ops-1",
        "tenant_id": "tenant-a",
        "roles": [],
        "principal_type": "rogue",
    }
    bad_token = jwt.encode(
        payload, settings.auth_token_signing_key, algorithm=ALGORITHM
    )
    with pytest.raises(AuthError, match="rogue"):
        verify_credential(bad_token)


def test_platform_operator_principal_dataclass_carries_subject() -> None:
    """Shape check on the thin scope marker."""
    p = PlatformOperatorPrincipal(subject="ops-1", credential_ref="abc12345...")
    assert p.subject == "ops-1"
    assert p.credential_ref == "abc12345..."
