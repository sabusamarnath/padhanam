"""Hash-chain primitives for revision-shaped aggregates (D26, D75).

Platform-level security primitive consistent with where
``AuthorizationError``, ``check``, ``OPERATOR_ROLE``, and ``crypto.py``
live. Promoted from ``contexts/methodology/domain/hash_chain.py`` at
S24 commit 8 alongside the agent use cases per D75's hash-chain
helper promotion: cross-context import from
``contexts.methodology.domain`` into ``contexts.agent`` violates
D17's independence contracts; promotion is the structurally honest
resolution. This is the second instance of the second-consumer-
promotes pattern after S23's OPERATOR_ROLE promotion.

Per D75, the promoted helper exports field-set-agnostic primitives
only. Methodology-specific bits in the original helper (the
``CONTENT_FIELDS`` frozenset, the ``_normalise_list_fields``
function, the unused ``filter_content_fields`` defensive whitelist)
do not promote; list-sort responsibility for list-shaped fields
moves to the use case layer in both contexts. Each use case knows
which of its fields are list-shaped and sorts them before
constructing the content payload it passes to
``compute_revision_hash``. The API shape is field-set-agnostic so
future revision-shaped contexts inherit the primitive without re-
cleaning the helper's field-name coupling.

Mirrors the audit-chain pattern at
``contexts/audit/domain/events.py:67-81``: SHA-256 over canonical
JSON of the revision content payload, with the predecessor's hash
included as a key inside the payload (not byte-concatenated). The
chain-binding mechanism is payload inclusion; each aggregate has
its own chain rooted at ``GENESIS_REVISION_HASH``.

Canonical JSON convention per D74:
- ``json.dumps(payload, sort_keys=True, separators=(",", ":"))``
- UTF-8 encoded
- ``Decimal`` values via ``format(value.normalize(), "f")`` for
  fixed-point lexical determinism regardless of magnitude
- ``UUID`` values via ``str(uuid)`` so list-shaped UUID fields
  round-trip lexically

Pure functions: no I/O, no SDK dependencies. The primitive stays
portable to any adapter and any consuming context.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID

GENESIS_REVISION_HASH = "0" * 64


class _CanonicalJSONEncoder(json.JSONEncoder):
    """Canonical-JSON encoder for hash determinism (D74).

    ``Decimal`` → ``format(value.normalize(), "f")``: fixed-point
    lexical form regardless of magnitude. ``Decimal("0.50")`` and
    ``Decimal("0.5")`` both yield ``"0.5"``; ``Decimal("100")`` yields
    ``"100"`` rather than the ``str(...)``-form ``"1E+2"``.

    ``UUID`` → ``str(uuid)``: hyphenated lower-case canonical form.
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return format(o.normalize(), "f")
        if isinstance(o, UUID):
            return str(o)
        return super().default(o)


def canonical_json(payload: Mapping[str, Any]) -> bytes:
    """UTF-8 canonical-JSON serialisation of a payload."""
    return json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        cls=_CanonicalJSONEncoder,
    ).encode("utf-8")


def compute_revision_hash(
    *,
    content_payload: Mapping[str, Any],
    previous_hash: str,
) -> str:
    """SHA-256 hex digest of the canonical-JSON revision payload (D75).

    The previous hash is included as the ``previous_revision_hash``
    key inside the canonical-JSON payload, mirroring the audit-chain
    pattern at ``contexts/audit/domain/events.py:67-81``. The caller
    is responsible for normalising any list-shaped fields (sorting,
    UUID-to-string conversion) before passing the payload; the
    promoted helper does not assume any particular field shape per
    D75's field-set-agnostic API contract.
    """
    payload = {**content_payload, "previous_revision_hash": previous_hash}
    return hashlib.sha256(canonical_json(payload)).hexdigest()
