"""Methodology revision hash-chain helpers (D26, D74).

Mirrors the audit-chain pattern at ``contexts/audit/domain/events.py:67-81``:
SHA-256 over canonical JSON of the revision content payload, with the
predecessor's hash included as a key inside the payload (not byte-
concatenated). The chain-binding mechanism is payload inclusion;
each template has its own chain rooted at ``GENESIS_REVISION_HASH``.

Canonical JSON convention per D74:
- ``json.dumps(payload, sort_keys=True, separators=(",", ":"))``
- UTF-8 encoded
- ``Decimal`` values via ``format(value.normalize(), "f")`` for
  fixed-point lexical determinism regardless of magnitude
- ``UUID`` values via ``str(uuid)`` so list-shaped UUID fields
  (source_ids) round-trip lexically

The list-shaped fields ``source_ids`` and ``tool_allowlist`` are
internally sorted before serialisation per D74 (json.dumps
sort_keys does not recurse into list contents). The normalisation
happens inside ``compute_revision_hash`` so callers cannot
accidentally produce hash drift by varying list order.

Pure functions: no I/O, no SDK dependencies. The domain stays
portable to any adapter.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID

GENESIS_REVISION_HASH = "0" * 64

CONTENT_FIELDS: frozenset[str] = frozenset({
    "name",
    "description",
    "system_prompt",
    "source_ids",
    "tool_allowlist",
    "retrieval_strategy",
    "filter_tree",
    "top_k",
    "min_score",
    "model_selection",
})


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


def filter_content_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Restrict an input mapping to D74's content-surface fields.

    Defensive whitelist: chain metadata
    (``methodology_template_id``, ``version``, ``created_by_user_id``,
    ``created_at``, ``this_revision_hash``, ``previous_revision_hash``)
    is filtered out so callers can pass a superset dict without
    silently polluting the hash.
    """
    return {k: v for k, v in payload.items() if k in CONTENT_FIELDS}


def _normalise_list_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Apply D74's canonical normalisation to list-shaped fields.

    ``source_ids`` and ``tool_allowlist`` are internally sorted as
    lexicographic strings. UUIDs convert via ``str(uuid)`` to
    lexicographic form before the sort.
    """
    out = dict(payload)
    if "source_ids" in out and isinstance(out["source_ids"], (list, tuple)):
        out["source_ids"] = sorted(str(s) for s in out["source_ids"])
    if "tool_allowlist" in out and isinstance(out["tool_allowlist"], (list, tuple)):
        out["tool_allowlist"] = sorted(str(t) for t in out["tool_allowlist"])
    return out


def compute_revision_hash(
    *,
    content_payload: Mapping[str, Any],
    previous_hash: str,
) -> str:
    """SHA-256 hex digest of the canonical-JSON revision payload (D74).

    The previous hash is included as the ``previous_revision_hash``
    key inside the canonical-JSON payload, mirroring the audit-chain
    pattern at ``contexts/audit/domain/events.py:67-81``. List-shaped
    fields are internally sorted before serialisation. The hash
    spans the content fields per D74; chain metadata is excluded by
    the caller through ``filter_content_fields`` (or by constructing
    the content payload narrowly in the use case layer).
    """
    normalised = _normalise_list_fields(content_payload)
    payload = {**normalised, "previous_revision_hash": previous_hash}
    return hashlib.sha256(canonical_json(payload)).hexdigest()
