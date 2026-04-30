"""TenantConnectionConfig — transient plaintext credentials.

This type carries plaintext credentials. It exists only at the boundaries
where credentials must be plaintext: at `register_tenant` time, the caller
constructs one and hands it to the registry port (which encrypts before
persisting); at routing time post-S11, `vadakkan/security/crypto.py`
returns one from the unwrap path so the AsyncSession factory can open a
real connection.

THIS TYPE HOLDS PLAINTEXT AND MUST NOT PERSIST BEYOND FUNCTION-CALL SCOPE.
The leak-prevention controls (logging filter, AST test that forbids
keeping references in instance state, isolation test) land at S10 with
the registry adapter that first writes plaintext through this surface.
S9 ships the type without those controls because S9 has no write path
that touches plaintext; the type exists so the S10 port contract has a
target to type against.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantConnectionConfig:
    host: str
    port: int
    username: str
    password: str
    database: str
