"""Hash-chain wrapper tests for the gold-set revision (D109 commitment 4).

The wrapper delegates canonical-JSON-plus-SHA-256 to
``padhanam.security.hash_chain.compute_revision_hash``; these tests
pin (a) the canonical-payload shape (entries sorted by entry_index,
UUIDs lower-cased), (b) that two payload constructions with the same
content but different in-memory entry ordering produce the same
hash, and (c) a golden vector so any future change to the canonical
serialisation rule surfaces as a test failure.
"""

from __future__ import annotations

from uuid import UUID

from contexts.retrieval_evaluation.domain import (
    GENESIS_REVISION_HASH,
    GoldSetEntry,
    compute_revision_hash,
    revision_canonical_payload,
)


_CHUNK_A = UUID("11111111-1111-1111-1111-111111111111")
_CHUNK_B = UUID("22222222-2222-2222-2222-222222222222")
_CHUNK_C = UUID("33333333-3333-3333-3333-333333333333")


def _entry(index: int, query: str, *chunks: UUID) -> GoldSetEntry:
    return GoldSetEntry(
        id=UUID(int=index + 1),
        gold_set_revision_id=UUID(int=100),
        entry_index=index,
        query=query,
        expected_chunk_ids=chunks,
    )


def test_canonical_payload_sorts_entries_by_index() -> None:
    e0 = _entry(0, "first query", _CHUNK_A, _CHUNK_B)
    e1 = _entry(1, "second query", _CHUNK_C)
    payload_asc = revision_canonical_payload(
        revision_number=1, entries=(e0, e1)
    )
    payload_desc = revision_canonical_payload(
        revision_number=1, entries=(e1, e0)
    )
    assert payload_asc == payload_desc
    assert [e["entry_index"] for e in payload_asc["entries"]] == [0, 1]


def test_canonical_payload_renders_chunk_ids_as_strings_in_array_order() -> None:
    entry = _entry(0, "q", _CHUNK_A, _CHUNK_B, _CHUNK_C)
    payload = revision_canonical_payload(revision_number=1, entries=(entry,))
    rendered = payload["entries"][0]["expected_chunk_ids"]
    assert rendered == [str(_CHUNK_A), str(_CHUNK_B), str(_CHUNK_C)]


def test_genesis_revision_hash_is_64_zeros() -> None:
    assert GENESIS_REVISION_HASH == "0" * 64


def test_hash_is_stable_across_different_in_memory_entry_ordering() -> None:
    e0 = _entry(0, "alpha", _CHUNK_A)
    e1 = _entry(1, "beta", _CHUNK_B, _CHUNK_C)
    h_asc = compute_revision_hash(
        revision_number=1,
        entries=(e0, e1),
        previous_event_hash=GENESIS_REVISION_HASH,
    )
    h_desc = compute_revision_hash(
        revision_number=1,
        entries=(e1, e0),
        previous_event_hash=GENESIS_REVISION_HASH,
    )
    assert h_asc == h_desc


def test_hash_changes_when_previous_event_hash_changes() -> None:
    entry = _entry(0, "alpha", _CHUNK_A)
    h_genesis = compute_revision_hash(
        revision_number=1,
        entries=(entry,),
        previous_event_hash=GENESIS_REVISION_HASH,
    )
    h_other = compute_revision_hash(
        revision_number=1,
        entries=(entry,),
        previous_event_hash="f" * 64,
    )
    assert h_genesis != h_other


def test_golden_vector_pins_canonical_serialisation() -> None:
    """Golden vector — change this only if the canonical-payload spec changes.

    Any divergence here signals that the canonical serialisation
    contract drifted; persisted hashes from prior gold-set revisions
    would no longer recompute identically.
    """
    e0 = _entry(0, "alpha", _CHUNK_A)
    e1 = _entry(1, "beta", _CHUNK_B, _CHUNK_C)
    h = compute_revision_hash(
        revision_number=1,
        entries=(e0, e1),
        previous_event_hash=GENESIS_REVISION_HASH,
    )
    assert h == (
        "14c4149ad35cc3ad0f85044b298f74363d4a64260eacd4cffc32acac04926d94"
    )
