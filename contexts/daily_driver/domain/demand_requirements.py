"""Demand requirements — the config-driven discrete requirement field set (S103ah, D240).

A demand requirement is one discrete thing a role wants, extracted from the demand-spec
(the JD): a ``text`` and a three-level ``importance``. The extractor produces N of them,
conforming to the ``REQUIREMENT_FIELDS`` config table, replacing the compressing single
``selection_criteria`` blob (the retired ``ExtractedQualification`` anti-pattern — a fixed
dataclass field structurally cannot hold N discrete criteria). Adding a requirement
attribute later (criticality, seniority) is a **row in ``REQUIREMENT_FIELDS``**, read by
the generic extractor + schema builder — never a new fixed dataclass field or a code
branch (the generic-bones principle; job hunt is the proof, the generic engine is the bet).

Each requirement is a **draft-as-suggestion** (D236): extraction writes items
``proof_state='draft'``; the operator proofs each (Use / edit / Dismiss) and can add
missed ones; only **confirmed** requirements are matched (no silent fact, D200).
Requirements store as a schemaless JSON list on ``:Opportunity`` (D214, no migration),
each stably id'd by a **content hash** so re-extraction is idempotent and never clobbers
a confirmed item (invariant 4, the S103af idempotent-write law).

Pure (D16, stdlib only).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# The three importance levels (D240) — drawn from the JD's framing.
IMPORTANCE_ESSENTIAL = "essential"
IMPORTANCE_PREFERRED = "preferred"
IMPORTANCE_NICE_TO_HAVE = "nice_to_have"
IMPORTANCE_LEVELS: tuple[str, ...] = (
    IMPORTANCE_ESSENTIAL,
    IMPORTANCE_PREFERRED,
    IMPORTANCE_NICE_TO_HAVE,
)
# An unstated / unrecognised importance defaults to essential — a requirement the JD
# lists but does not grade is treated as a must, not silently downgraded to a bonus.
DEFAULT_IMPORTANCE = IMPORTANCE_ESSENTIAL

# The proof states (D236): a draft is a suggestion; only a confirmed requirement is a
# fact (matched, D200). No third state — Dismiss removes the item.
PROOF_DRAFT = "draft"
PROOF_CONFIRMED = "confirmed"

# The config-driven requirement field set (D240). Each row is an attribute the extractor
# pulls per requirement, read by the generic schema builder + prompt below. Adding an
# attribute (criticality, seniority) is a row here — never a new fixed dataclass field or
# a literal branch. (key, json_type, enum_values_or_None, prompt_description)
REQUIREMENT_FIELDS: tuple[tuple[str, str, tuple[str, ...] | None, str], ...] = (
    ("text", "string", None, "the requirement in one clause, in the candidate's terms"),
    (
        "importance",
        "string",
        IMPORTANCE_LEVELS,
        "how strongly the role weights it: essential (a must-have), preferred (a strong "
        "plus), or nice_to_have (a bonus)",
    ),
)

# A defensive cap — a JD that lists more discrete requirements than this is degenerate
# (a whole-page paste), and the bound protects the store and the surface.
MAX_REQUIREMENTS = 40


def requirement_item_schema() -> dict[str, Any]:
    """The per-requirement JSON schema, built from ``REQUIREMENT_FIELDS`` (config-driven —
    adding a field row extends the schema with no code change)."""
    props: dict[str, Any] = {}
    for key, json_type, enum_values, _desc in REQUIREMENT_FIELDS:
        spec: dict[str, Any] = {"type": json_type}
        if enum_values is not None:
            spec["enum"] = list(enum_values)
        props[key] = spec
    return {
        "type": "object",
        "properties": props,
        "required": [key for key, *_ in REQUIREMENT_FIELDS],
        "additionalProperties": False,
    }


def _normalize(text: str) -> str:
    return " ".join((text or "").split()).lower()


def requirement_id(text: str) -> str:
    """A stable content-hash id for a requirement (D240). Same normalized text → same
    id, so re-extraction is idempotent and merge dedups for free; editing the text
    re-derives the id (identity tracks content — single-operator dogfood-acceptable, and
    the surface re-reads after each op so it always targets the current id)."""
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()[:16]


def coerce_importance(value: Any) -> str:
    """Coerce a returned/stored importance to the config vocabulary; anything else →
    the default (essential), never silently a bonus."""
    if isinstance(value, str) and value.strip().lower() in IMPORTANCE_LEVELS:
        return value.strip().lower()
    return DEFAULT_IMPORTANCE


def make_requirement(
    *, text: Any, importance: Any, proof_state: Any
) -> dict[str, Any] | None:
    """One requirement item as stored — ``{id, text, importance, proof_state}`` — or
    ``None`` for an empty text (no requirement). ``id`` is the content hash;
    ``importance`` is coerced to the config vocabulary; ``proof_state`` is draft unless
    explicitly confirmed."""
    clean = (text or "").strip() if isinstance(text, str) else ""
    if not clean:
        return None
    return {
        "id": requirement_id(clean),
        "text": clean,
        "importance": coerce_importance(importance),
        "proof_state": PROOF_CONFIRMED if proof_state == PROOF_CONFIRMED else PROOF_DRAFT,
    }


def _collect(entries: Any, *, proof_state: str | None) -> tuple[dict, ...]:
    """Map a list of raw dicts to validated items, dedup on id (== normalized text),
    capped. ``proof_state=None`` reads each entry's own state (stored read); a fixed
    value forces it (fresh extraction → draft)."""
    out: list[dict] = []
    seen: set[str] = set()
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            state = proof_state if proof_state is not None else entry.get("proof_state")
            req = make_requirement(
                text=entry.get("text"),
                importance=entry.get("importance"),
                proof_state=state,
            )
            if req is None or req["id"] in seen:
                continue
            seen.add(req["id"])
            out.append(req)
            if len(out) >= MAX_REQUIREMENTS:
                break
    return tuple(out)


def parse_extracted(items: Any) -> tuple[dict, ...]:
    """Map the model's ``requirements`` array to fresh **draft** items (D240),
    config-driven + defensive: unknown shapes / empties dropped, dedup on id, capped."""
    return _collect(items, proof_state=PROOF_DRAFT)


def deserialize(stored: str | None) -> tuple[dict, ...]:
    """Read the stored ``demand_requirements`` JSON list (D214) → validated items,
    preserving each item's proof_state. Defensive: bad JSON / bad shapes degrade to
    ``()`` (never raise on read)."""
    if not stored:
        return ()
    try:
        raw = json.loads(stored)
    except (ValueError, TypeError):
        return ()
    return _collect(raw, proof_state=None)


def serialize(items: tuple[dict, ...]) -> str:
    """The stored JSON shape (D214) — id/text/importance/proof_state per item."""
    return json.dumps(
        [
            {
                "id": r["id"],
                "text": r["text"],
                "importance": r["importance"],
                "proof_state": r["proof_state"],
            }
            for r in items
        ]
    )


def merge_extracted(
    existing: tuple[dict, ...], fresh_drafts: tuple[dict, ...]
) -> tuple[dict, ...]:
    """Re-extraction merge (D240): keep every **confirmed** requirement (invariant 4, no
    clobber), replace the draft set with the fresh drafts, and drop a fresh draft that
    duplicates a confirmed one. Idempotent — re-extracting the same JD keeps confirmed
    items and re-produces the same drafts (stable content-hash ids), so it converges
    (the S103af idempotent-write law)."""
    confirmed = tuple(r for r in existing if r["proof_state"] == PROOF_CONFIRMED)
    confirmed_ids = {r["id"] for r in confirmed}
    drafts = tuple(r for r in fresh_drafts if r["id"] not in confirmed_ids)
    return confirmed + drafts


def confirm(items: tuple[dict, ...], req_id: str) -> tuple[dict, ...]:
    """Use a draft as-is: flip it to confirmed (D236). Unknown id → no-op."""
    return tuple(
        {**r, "proof_state": PROOF_CONFIRMED} if r["id"] == req_id else r
        for r in items
    )


def dismiss(items: tuple[dict, ...], req_id: str) -> tuple[dict, ...]:
    """Dismiss a requirement: remove it (D236). Unknown id → no-op."""
    return tuple(r for r in items if r["id"] != req_id)


def edit(
    items: tuple[dict, ...], req_id: str, *, text: Any, importance: Any
) -> tuple[dict, ...]:
    """Edit a requirement's text/importance and confirm it (D236). An empty text is a
    no-op (Dismiss is the removal path); an unknown id is a no-op; an edit that collides
    with another item's id dedups (the survivor is the edited one)."""
    new = make_requirement(
        text=text, importance=importance, proof_state=PROOF_CONFIRMED
    )
    if new is None or not any(r["id"] == req_id for r in items):
        return items
    out: list[dict] = [new]
    seen: set[str] = {new["id"]}
    for r in items:
        if r["id"] == req_id or r["id"] in seen:
            continue
        out.append(r)
        seen.add(r["id"])
    # Preserve original order except the edited item lands where it was.
    edited_pos = next(i for i, r in enumerate(items) if r["id"] == req_id)
    rest = [r for r in out if r["id"] != new["id"]]
    rest.insert(min(edited_pos, len(rest)), new)
    return tuple(rest)


def add(items: tuple[dict, ...], *, text: Any, importance: Any) -> tuple[dict, ...]:
    """Add an operator-authored requirement, confirmed (D236). An empty text is a no-op;
    adding one that duplicates an existing item confirms the existing item instead."""
    new = make_requirement(
        text=text, importance=importance, proof_state=PROOF_CONFIRMED
    )
    if new is None:
        return items
    if any(r["id"] == new["id"] for r in items):
        return confirm(items, new["id"])
    return items + (new,)


def confirmed_texts(items: tuple[dict, ...]) -> tuple[str, ...]:
    """The confirmed requirements' texts — the match's criteria (D239/D240)."""
    return tuple(r["text"] for r in items if r["proof_state"] == PROOF_CONFIRMED)


__all__ = [
    "DEFAULT_IMPORTANCE",
    "IMPORTANCE_ESSENTIAL",
    "IMPORTANCE_LEVELS",
    "IMPORTANCE_NICE_TO_HAVE",
    "IMPORTANCE_PREFERRED",
    "MAX_REQUIREMENTS",
    "PROOF_CONFIRMED",
    "PROOF_DRAFT",
    "REQUIREMENT_FIELDS",
    "add",
    "coerce_importance",
    "confirm",
    "confirmed_texts",
    "deserialize",
    "dismiss",
    "edit",
    "make_requirement",
    "merge_extracted",
    "parse_extracted",
    "requirement_id",
    "requirement_item_schema",
    "serialize",
]
