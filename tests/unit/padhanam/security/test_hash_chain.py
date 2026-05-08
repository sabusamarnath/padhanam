"""Unit tests for padhanam.security.hash_chain (D26, D75).

Promoted from contexts/methodology/domain/hash_chain.py at S24
commit 8 with field-set-agnostic API per D75. Tests of the
field-set-agnostic primitives stay here; tests that exercised the
removed methodology-specific helpers (filter_content_fields and
the implicit list-sort behaviour) relocate to the methodology /
agent use case test suites where list-sort responsibility now
lives.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from uuid import UUID

from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    canonical_json,
    compute_revision_hash,
)


def _content_payload(**overrides) -> dict:
    defaults = {
        "name": "LVT",
        "description": "Local-volume thinking baseline",
        "system_prompt": "You are a careful analyst.",
        "source_ids": [],
        "tool_allowlist": [],
        "retrieval_strategy": {"strategy": "vector_only", "params": {}},
        "filter_tree": {"node": {}},
        "top_k": 5,
        "min_score": Decimal("0.7"),
        "model_selection": "qwen2.5:7b",
    }
    defaults.update(overrides)
    return defaults


def test_genesis_revision_hash_is_64_zero_chars() -> None:
    assert GENESIS_REVISION_HASH == "0" * 64
    assert len(GENESIS_REVISION_HASH) == 64


def test_canonical_json_is_deterministic_under_key_reordering() -> None:
    payload_a = {"alpha": 1, "beta": 2, "gamma": 3}
    payload_b = {"gamma": 3, "alpha": 1, "beta": 2}
    assert canonical_json(payload_a) == canonical_json(payload_b)


def test_canonical_json_uses_no_whitespace_separators() -> None:
    payload = {"a": 1, "b": 2}
    serialised = canonical_json(payload)
    assert b" " not in serialised
    assert serialised == b'{"a":1,"b":2}'


def test_canonical_json_recurses_into_nested_dict_keys() -> None:
    """sort_keys=True recurses into nested dict keys per Python's json behaviour."""
    payload_a = {"outer": {"a": 1, "b": 2}}
    payload_b = {"outer": {"b": 2, "a": 1}}
    assert canonical_json(payload_a) == canonical_json(payload_b)


def test_compute_revision_hash_is_reproducible() -> None:
    payload = _content_payload()
    h1 = compute_revision_hash(
        content_payload=payload, previous_hash=GENESIS_REVISION_HASH
    )
    h2 = compute_revision_hash(
        content_payload=payload, previous_hash=GENESIS_REVISION_HASH
    )
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_compute_revision_hash_includes_previous_hash_in_payload() -> None:
    """Mirrors audit-chain pattern: previous_hash is a key inside the payload."""
    payload = _content_payload()
    h_genesis = compute_revision_hash(
        content_payload=payload, previous_hash=GENESIS_REVISION_HASH
    )
    h_other = compute_revision_hash(
        content_payload=payload, previous_hash="ab" * 32
    )
    assert h_genesis != h_other


def test_compute_revision_hash_decimal_canonical_form() -> None:
    """Decimal('0.50') and Decimal('0.5') normalize to the same canonical form."""
    h_a = compute_revision_hash(
        content_payload=_content_payload(min_score=Decimal("0.50")),
        previous_hash=GENESIS_REVISION_HASH,
    )
    h_b = compute_revision_hash(
        content_payload=_content_payload(min_score=Decimal("0.5")),
        previous_hash=GENESIS_REVISION_HASH,
    )
    assert h_a == h_b


def test_canonical_json_decimal_format_f_pinning() -> None:
    """format-f handling per D74: pin the four edge cases explicitly."""
    assert canonical_json({"v": Decimal("0")}) == b'{"v":"0"}'
    assert canonical_json({"v": Decimal("-0.5")}) == b'{"v":"-0.5"}'
    # format(Decimal("100").normalize(), "f") = "100", NOT "1E+2"
    assert canonical_json({"v": Decimal("100")}) == b'{"v":"100"}'
    # format(Decimal("1.5E+10").normalize(), "f") = "15000000000"
    assert canonical_json({"v": Decimal("1.5E+10")}) == b'{"v":"15000000000"}'


def test_canonical_json_float_serialises_differently_from_decimal() -> None:
    """Defensive: a float input does not silently substitute for a Decimal.

    Float serialisation uses json's default path (bare number), not
    the custom encoder. The produced bytes differ from the Decimal
    canonical form. Hash compatibility depends on callers passing
    the correct types — this test pins that the encoder makes the
    type mismatch visible rather than silent.
    """
    decimal_form = canonical_json({"v": Decimal("0.5")})
    float_form = canonical_json({"v": 0.5})
    assert decimal_form != float_form
    assert decimal_form == b'{"v":"0.5"}'
    assert float_form == b'{"v":0.5}'


def test_canonical_json_uuid_serialises_as_string() -> None:
    """UUID round-trips through str(uuid) for lexical determinism."""
    u = UUID("00000000-0000-4000-8000-000000000001")
    assert canonical_json({"v": u}) == b'{"v":"00000000-0000-4000-8000-000000000001"}'


def test_compute_revision_hash_chain_of_revisions_integrity() -> None:
    """Multi-revision chain: each binds to its predecessor; tampering breaks the chain."""
    payload_v1 = _content_payload()
    h1 = compute_revision_hash(
        content_payload=payload_v1, previous_hash=GENESIS_REVISION_HASH
    )

    payload_v2 = _content_payload(min_score=Decimal("0.8"))
    h2 = compute_revision_hash(content_payload=payload_v2, previous_hash=h1)

    payload_v3 = _content_payload(min_score=Decimal("0.9"))
    h3 = compute_revision_hash(content_payload=payload_v3, previous_hash=h2)

    assert h1 != h2
    assert h2 != h3

    # Recomputing v2 with the wrong previous_hash breaks the chain
    h2_tampered = compute_revision_hash(
        content_payload=payload_v2, previous_hash=GENESIS_REVISION_HASH
    )
    assert h2 != h2_tampered


def test_compute_revision_hash_audit_chain_structural_equivalence() -> None:
    """Hash mirrors audit-chain shape: SHA-256 of canonical-JSON of content + previous_hash key.

    Reconstruct the same hash by hand using the same primitive,
    confirm equivalence — pins that compute_revision_hash is
    structurally the audit_chain_hash applied to the content
    payload, not a divergent variant. This is the field-set-
    agnostic primitive shape per D75: any caller's payload plus a
    previous_hash key produces a SHA-256 of the canonical-JSON form.
    """
    payload = _content_payload(source_ids=["a", "b"], tool_allowlist=["t1", "t2"])
    revision_hash = compute_revision_hash(
        content_payload=payload, previous_hash=GENESIS_REVISION_HASH
    )
    expected_payload = {**payload, "previous_revision_hash": GENESIS_REVISION_HASH}
    expected_hash = hashlib.sha256(canonical_json(expected_payload)).hexdigest()
    assert revision_hash == expected_hash


def test_compute_revision_hash_content_changes_change_hash() -> None:
    """Any content field flip must change the hash."""
    base = _content_payload()
    h_base = compute_revision_hash(content_payload=base, previous_hash=GENESIS_REVISION_HASH)
    for field in ("name", "description", "system_prompt", "model_selection"):
        flipped = dict(base)
        flipped[field] = base[field] + " (modified)"
        h_flipped = compute_revision_hash(
            content_payload=flipped, previous_hash=GENESIS_REVISION_HASH
        )
        assert h_flipped != h_base, f"hash unchanged when {field} flipped"


def test_field_set_agnostic_hash_payload_does_not_sort_lists() -> None:
    """D75 contract: list-sort responsibility lives in the use case layer.

    The promoted helper does NOT sort list-shaped fields. Two payloads
    differing only in list ordering produce different hashes.
    Use cases must apply canonical sort before passing the payload.
    """
    h_abc = compute_revision_hash(
        content_payload={"items": ["a", "b", "c"]},
        previous_hash=GENESIS_REVISION_HASH,
    )
    h_cba = compute_revision_hash(
        content_payload={"items": ["c", "b", "a"]},
        previous_hash=GENESIS_REVISION_HASH,
    )
    assert h_abc != h_cba
