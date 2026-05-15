"""Gold-set revision hash-chain wrapper (D109 commitment 4).

Thin wrapper over ``padhanam.security.hash_chain.compute_revision_hash``
(the field-set-agnostic platform primitive promoted at S24 per D75).
The gold-set context becomes the third consumer of this primitive
after ``contexts/methodology/`` and ``contexts/agent/``, strengthening
D75's second-consumer-promotes pattern observation (now third-
consumer-confirms).

Per D109 commitment 4, the gold-set-revision content payload follows
this canonical shape:

    {
      "revision_number": int,
      "entries": [
        {
          "entry_index": int,
          "query": str,
          "expected_chunk_ids": [
            UUID strings in lowercase canonical form, in array order
          ]
        },
        ...
      ]
    }

The entries array is sorted by ``entry_index`` ascending so the
canonical encoding is stable regardless of the order the application
layer assembled the entries in memory.

The platform helper handles JSON canonicalization (sorted keys,
compact separators, UTF-8), UUID-to-string lexical conversion, and
SHA-256-of-canonical-bytes. The wrapper here owns only the gold-set-
specific payload shape; it does not duplicate the canonicalization
mechanism.

Pre-write reconciliation note (S39): the original D109 commitment 4
named ``compute_event_hash`` from ``contexts/audit/domain/events.py``
as the reuse target and proposed extracting a thin helper inside the
audit context (planned as commit 2.5). Mid-build reading of migration
0010 surfaced that ``padhanam/security/hash_chain.py`` already
exposes the structurally honest field-set-agnostic primitive used by
methodology and role aggregates; the audit refactor was dropped as
unnecessary. The session log entry captures this as a mid-build
Finding-3 correction; the audit context's ``compute_event_hash`` may
land its own refactor to call the platform primitive at some future
hygiene moment but is out of scope for S39.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from collections.abc import Iterable

from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash as _platform_compute_revision_hash,
)

from contexts.retrieval_evaluation.domain.gold_set_entry import GoldSetEntry

__all__ = [
    "GENESIS_REVISION_HASH",
    "compute_revision_hash",
    "revision_canonical_payload",
]


def revision_canonical_payload(
    *,
    revision_number: int,
    entries: Iterable[GoldSetEntry],
) -> dict[str, object]:
    """Construct the canonical payload shape for revision hashing.

    Mirrors D109 commitment 4's spec. Entries are sorted by
    ``entry_index`` ascending; ``expected_chunk_ids`` UUIDs are
    converted to lowercase canonical strings via ``str(uuid)``.
    """
    sorted_entries = sorted(entries, key=lambda e: e.entry_index)
    return {
        "revision_number": revision_number,
        "entries": [
            {
                "entry_index": entry.entry_index,
                "query": entry.query,
                "expected_chunk_ids": [
                    str(chunk_id) for chunk_id in entry.expected_chunk_ids
                ],
            }
            for entry in sorted_entries
        ],
    }


def compute_revision_hash(
    *,
    revision_number: int,
    entries: Iterable[GoldSetEntry],
    previous_event_hash: str,
) -> str:
    """SHA-256 hex digest of the canonical revision payload.

    The platform primitive owns the canonical-JSON-plus-SHA-256
    mechanism; this wrapper owns the gold-set-specific payload shape.
    The previous hash is included as ``previous_revision_hash`` in
    the payload encoded by the platform helper (the field name on the
    GoldSetRevision dataclass is ``previous_event_hash`` per D109
    commitment 2; the payload-encoding key inside the platform helper
    is independent of that surface).
    """
    payload = revision_canonical_payload(
        revision_number=revision_number,
        entries=entries,
    )
    return _platform_compute_revision_hash(
        content_payload=payload,
        previous_hash=previous_event_hash,
    )
