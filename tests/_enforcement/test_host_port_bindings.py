"""Parser test enforcing the host-port-binding allowlist (S11).

The S5 rule "only Caddy binds host ports" was a comment in
``compose.yaml`` until S10 added a deliberate dev-only exception for
``postgres-control-plane`` so the host pytest process could reach the
control-plane integration tests on loopback. Comment-enforced rules
drift; the S5 reflection's "checklists drift, AST tests do not"
directly motivates this promotion.

This test parses ``compose.yaml`` as YAML, walks ``services``, and for
each service that declares a ``ports:`` mapping asserts the binding
matches an explicit allowlist. Any service with a ``ports:`` mapping
not in the allowlist fails the test; any change to an allowlisted
binding (e.g. removing the loopback prefix from
``postgres-control-plane``) fails the test.

Adding a new allowlisted binding requires editing this file in the
same commit as the compose.yaml change, which forces the operator to
articulate the reason inline (the comment by each entry).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "compose.yaml"


# Each entry maps service name → tuple of port strings exactly as they
# must appear in compose.yaml. Comments document why each binding is
# allowlisted; review the comment before editing the value.
_ALLOWLIST: dict[str, tuple[str, ...]] = {
    # Caddy is the public edge for the dev stack: HTTPS via mkcert at
    # the laptop boundary, reverse-proxy onto the Compose network for
    # everything internal. Host port 443 → container 443 is the only
    # production-shaped binding in the dev stack.
    "caddy": ("443:443",),
    # Loopback-only host port for the postgres-control-plane instance
    # (S10 deliberate dev-only exception). The host pytest process
    # reaches the control-plane Postgres instance for the registry
    # integration tests via 127.0.0.1:5433. Loopback prefix
    # (127.0.0.1) keeps the binding off the LAN. Production manifests
    # remove the binding entirely.
    "postgres-control-plane": ("127.0.0.1:5433:5432",),
}


def _parse_compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def _service_port_bindings(compose: dict) -> dict[str, tuple[str, ...]]:
    """Return service_name → (port_string, ...) for every ports mapping."""
    services = compose.get("services", {}) or {}
    bindings: dict[str, tuple[str, ...]] = {}
    for service_name, service_spec in services.items():
        if not isinstance(service_spec, dict):
            continue
        ports = service_spec.get("ports")
        if not ports:
            continue
        # Compose's short-form ports list is a list of strings; long-
        # form is a list of dicts. Both round-trip through YAML; we
        # surface both shapes verbatim so a long-form sneak-in does
        # not slip past the comparator.
        normalised = []
        for entry in ports:
            if isinstance(entry, str):
                normalised.append(entry)
            elif isinstance(entry, dict):
                # Long-form. Render as `host_ip:published:target` for
                # comparison against the allowlist string.
                host_ip = entry.get("host_ip", "")
                published = entry.get("published", "")
                target = entry.get("target", "")
                if host_ip:
                    normalised.append(f"{host_ip}:{published}:{target}")
                else:
                    normalised.append(f"{published}:{target}")
            else:
                normalised.append(str(entry))
        bindings[service_name] = tuple(normalised)
    return bindings


def test_long_form_port_mapping_normalises_for_allowlist_comparison() -> None:
    """Long-form ports (list of dicts with host_ip/published/target) round-
    trip through the same comparator. Catches the failure mode where a
    drive-by edit replaces a short-form string with the structurally
    equivalent long-form, intending to evade a string-only allowlist."""
    fake_compose = {
        "services": {
            "redis": {
                "image": "redis:7",
                "ports": [
                    {"host_ip": "127.0.0.1", "published": 6379, "target": 6379},
                ],
            },
            "caddy": {
                "image": "caddy:2",
                "ports": ["443:443"],
            },
        }
    }
    bindings = _service_port_bindings(fake_compose)
    assert bindings["redis"] == ("127.0.0.1:6379:6379",)
    assert bindings["caddy"] == ("443:443",)


def test_host_port_bindings_match_allowlist() -> None:
    compose = _parse_compose()
    actual = _service_port_bindings(compose)

    extras = {
        name: bindings
        for name, bindings in actual.items()
        if name not in _ALLOWLIST
    }
    assert extras == {}, (
        "Service has host port binding outside the allowlist "
        "(S5 rule: only allowlisted bindings permitted; "
        "review tests/_enforcement/test_host_port_bindings.py "
        "before adding a new entry): " + repr(extras)
    )

    mismatches = {
        name: (actual.get(name), expected)
        for name, expected in _ALLOWLIST.items()
        if name in actual and actual[name] != expected
    }
    assert mismatches == {}, (
        "Allowlisted service has unexpected port binding "
        "(loopback prefix removed? port changed? long-form sneaked in?): "
        + repr(mismatches)
    )

    missing = [name for name in _ALLOWLIST if name not in actual]
    assert missing == [], (
        "Allowlist references services not defined in compose.yaml: "
        + repr(missing)
    )
