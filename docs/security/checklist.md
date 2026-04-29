# Security review checklist

Run before every session-closing commit. The checklist gates commits the
same way the test suite does.

## Secrets and configuration
- [ ] No `os.getenv` calls outside `platform/config/` (verified by import-linter).
- [ ] No new `.env` reads outside `platform/config/`.
- [ ] No secret material in any tracked file (`git ls-files | xargs grep -l <known-secret-prefixes>`).
- [ ] `.env` is gitignored and `git log -- .env` returns empty.
- [ ] Any new secret has a placeholder in `.env.example`.

## Network exposure
- [ ] No service in `compose.yaml` binds a host port except Caddy on 443.
- [ ] All TLS-bearing services read TLS config through `platform/config/` (when applicable in this session).

## Supply chain
- [ ] All images in `compose.yaml` pinned to SHA256 digest.
- [ ] `make scan` passes with no CRITICAL or HIGH findings.
- [ ] If Python deps changed: `uv lock` ran clean and `pip-audit` passes.

## Architectural enforcement
- [ ] Import-linter passes (`make lint` or equivalent).
- [ ] If new tenant-scoped adapter shipped: corresponding `tests/contract/tenant_isolation/` test exists.
- [ ] If new endpoint shipped: authentication middleware is in front of it.
- [ ] If new UI-bearing service shipped: browser interactive verification ran (lesson from S4).

## Audit and security events
- [ ] If new state-changing operation on tenant-scoped data shipped: audit event emitted.
- [ ] If new auth/authz code shipped: security event emitted on failure paths.
