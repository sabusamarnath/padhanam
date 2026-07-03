"""CV extraction — the pure prompt + schema + parser (S103af, D238).

Leg two of the matching engine: read the parsed text of the operator's CV and draft
their standing skills profile — named skills and experience lines. The apps adapter
calls the ``StructuredOutputPort`` (the LiteLLM seam, the ``JdExtractorAdapter``
precedent) with this prompt + schema and parses the result; the litellm SDK never
enters this module or the daily-driver context (D4/D16).

Each drafted item is a *suggestion* (``:SkillItem`` proof_state='suggested', D238),
never a confirmed fact — the operator confirms, edits, or rejects (the extract-and-
proof lifecycle, D215/D222). The prompt is instructed to draw only from the CV and
not to invent, so extraction never fabricates a skill (D200).

Item ids are **deterministic** (``skill_item_id``): a uuid5 over (kind, normalized
text), so re-uploading a CV MERGEs onto the same node instead of duplicating — and,
paired with the ON-CREATE-only proof_state write, never un-confirms a proofed item.

Pure (D16, stdlib only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid5

# The two kinds the profile carries (mirrors domain.skills.KINDS).
KINDS = ("skill", "experience")

# Defensive bounds — a CV is a page or two; cap the text before the prompt, and cap
# the item counts so a pathological parse cannot flood the profile.
MAX_CV_CHARS = 20_000
MAX_SKILLS = 40
MAX_EXPERIENCES = 25

# Stable namespace for deterministic :SkillItem ids (S103af). A fixed UUID, so the
# derivation is reproducible across processes (uuid5 is deterministic; no Math.random).
_SKILL_ITEM_NS = UUID("a7e3b1c4-6f52-4d8a-9b0e-2c1d3e4f5a6b")

CV_EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "skills": {"type": "array", "items": {"type": "string"}},
        "experiences": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["skills", "experiences"],
    "additionalProperties": False,
}


def normalize_item(text: str) -> str:
    """The dedup / id key for a profile item — lower-cased, whitespace-collapsed."""
    return " ".join((text or "").split()).lower()


def skill_item_id(kind: str, text: str) -> UUID:
    """A deterministic :SkillItem id (S103af): uuid5 over (kind, normalized text), so
    a re-upload MERGEs onto the same node rather than duplicating the item."""
    return uuid5(_SKILL_ITEM_NS, f"{kind}:{normalize_item(text)}")


@dataclass(frozen=True)
class ExtractedProfile:
    """The drafted skills profile — deduped, capped, ready to seed as suggestions."""

    skills: tuple[str, ...] = field(default_factory=tuple)
    experiences: tuple[str, ...] = field(default_factory=tuple)

    def items(self) -> tuple[tuple[str, str], ...]:
        """The (kind, text) pairs to seed (D238) — skills first, then experiences."""
        return (
            tuple(("skill", s) for s in self.skills)
            + tuple(("experience", e) for e in self.experiences)
        )


def build_cv_extract_prompt(cv_text: str) -> str:
    """Build the extraction prompt (S103af, D238). Instructs the model to pull the
    operator's skills and experience lines from the CV in their own terms, drawing
    only from what the CV states (no invention — the operator proofs, D200)."""
    return (
        "You read a person's CV and pull out their standing skills profile — the "
        "things that describe what they can do and what they have done. Return two "
        "lists, grounded only in what the CV actually says:\n"
        "- skills: named capabilities, tools, methods, or domains (short phrases, "
        "e.g. 'product strategy', 'SQL', 'stakeholder management').\n"
        "- experiences: notable experience lines — a role's scope or a concrete "
        "achievement, one short line each (e.g. 'Led a 12-person product org', "
        "'Scaled a marketplace to 1M users').\n\n"
        "Rules:\n"
        "- Draw ONLY from the CV. Do not guess, generalise, or invent — a shorter, "
        "accurate list is better than a padded one.\n"
        "- Each entry is short and standalone. No duplicates.\n"
        "- If the CV is empty or unreadable, return two empty lists.\n\n"
        "CV:\n"
        f'"""\n{cv_text[:MAX_CV_CHARS]}\n"""'
    )


def _clean_list(value: Any, cap: int) -> tuple[str, ...]:
    """A drafted list: trimmed non-empty strings, deduped (case-insensitive), capped.
    Unknown shapes degrade to empty rather than raising (defensive, pure)."""
    if not isinstance(value, list):
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, str):
            continue
        text = " ".join(raw.split())
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= cap:
            break
    return tuple(out)


def parse_cv_extract(value: dict[str, Any]) -> ExtractedProfile:
    """Map the model's output to ``ExtractedProfile`` (pure, defensive). Missing or
    malformed lists degrade to empty rather than raising."""
    if not isinstance(value, dict):
        value = {}
    return ExtractedProfile(
        skills=_clean_list(value.get("skills"), MAX_SKILLS),
        experiences=_clean_list(value.get("experiences"), MAX_EXPERIENCES),
    )


__all__ = [
    "CV_EXTRACT_SCHEMA",
    "ExtractedProfile",
    "KINDS",
    "MAX_CV_CHARS",
    "MAX_EXPERIENCES",
    "MAX_SKILLS",
    "build_cv_extract_prompt",
    "normalize_item",
    "parse_cv_extract",
    "skill_item_id",
]
