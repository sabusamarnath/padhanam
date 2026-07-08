"""Job-description extraction — the pure prompt + schema + parser (S103ad, D236; deepened
S103ah, D240).

Leg one of the matching engine: read a pasted job description and extract two **context
fields** (why the role is open, what the hire must deliver) plus a **list of discrete,
typed demand requirements** (each ``text`` + three-level ``importance``). The requirements
replace the retired ``selection_criteria`` blob (the ``ExtractedQualification`` 3-field
anti-pattern that compressed N discrete criteria into one sentence); they are produced
config-driven from ``demand_requirements.REQUIREMENT_FIELDS`` — adding a requirement
attribute is a config row, never a code change (the generic-bones principle, D240).

The apps adapter calls the ``StructuredOutputPort`` (the LiteLLM seam, the
``CddDrafterAdapter`` precedent) with this prompt + schema and parses the result; the
litellm SDK never enters this module or the daily-driver context (D4/D16).

Each context field is a *suggestion* written to a ``q_<key>_draft`` slot (D236); each
requirement is a draft item in the ``demand_requirements`` list (D240). Neither is a fact
until the operator proofs it (D200). The prompt is instructed to return an empty string
for a context field the JD does not state and to draw importance from the JD's own
framing, so extraction never invents.

Pure (D16, stdlib only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contexts.daily_driver.domain.demand_requirements import (
    IMPORTANCE_LEVELS,
    parse_extracted,
    requirement_item_schema,
)

# The two JD-derivable context fields, retained as before (D236) — singular context, not
# per-requirement-type fields, so legitimately fixed (not the retired anti-pattern).
JD_CONTEXT_FIELDS: tuple[tuple[str, str], ...] = (
    ("role_open", "why the role is open"),
    ("success_measures", "what the hire must deliver in the first 6-12 months"),
)
JD_CONTEXT_FIELD_KEYS: tuple[str, ...] = tuple(k for k, _ in JD_CONTEXT_FIELDS)

# The JD text is capped before it reaches the prompt — a defensive bound so a pasted
# page (or an accidental whole-inbox paste) cannot blow the context window.
MAX_JD_CHARS = 12_000

# The extraction schema: the two context fields + the discrete requirements array (whose
# item schema is built config-driven from REQUIREMENT_FIELDS, D240).
JD_EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        **{k: {"type": "string"} for k, _ in JD_CONTEXT_FIELDS},
        "requirements": {"type": "array", "items": requirement_item_schema()},
    },
    "required": [*JD_CONTEXT_FIELD_KEYS, "requirements"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class ExtractedDemand:
    """The extracted demand (S103ah, D240): the two context fields (each ``None`` when the
    JD does not state it) + the list of discrete requirement draft items (each a
    ``{id, text, importance, proof_state}`` dict, config-shaped per REQUIREMENT_FIELDS)."""

    role_open: str | None
    success_measures: str | None
    requirements: tuple[dict, ...]

    def context_drafts(self) -> tuple[tuple[str, str], ...]:
        """The (field_key, draft_text) pairs that actually have a draft — the use case
        writes only these, so a context field the JD omits stays blank."""
        pairs = (
            ("role_open", self.role_open),
            ("success_measures", self.success_measures),
        )
        return tuple((k, v) for k, v in pairs if v)


def build_jd_extract_prompt(jd_text: str) -> str:
    """Build the extraction prompt (S103ad/D236, deepened S103ah/D240). Instructs the
    model to draft the two context fields and to pull **every discrete requirement** the
    JD states as its own item (never compressed into a sentence), grading each by the
    JD's framing into essential / preferred / nice_to_have."""
    context = "\n".join(f"- {key}: {desc}" for key, desc in JD_CONTEXT_FIELDS)
    levels = " / ".join(IMPORTANCE_LEVELS)
    return (
        "You read a job description and pull out what a candidate uses to qualify a "
        "role. Return three things:\n\n"
        "Two short CONTEXT fields (a sentence or a few bullet-like phrases each), "
        "grounded in what the description says:\n"
        f"{context}\n\n"
        "And a LIST of the role's discrete REQUIREMENTS — every distinct skill, "
        "experience, or attribute the role selects on. Rules for the requirements:\n"
        "- One requirement per item. Do NOT bundle several requirements into one "
        "sentence — if the description lists seven essential criteria, return seven "
        "items. Nothing dropped, nothing merged.\n"
        f"- Grade each by the description's own framing, using exactly one of: {levels}. "
        "Essential = a must-have (required, essential, expected); preferred = a strong "
        "plus (desirable, preferred, advantage); nice_to_have = a bonus. If the "
        "description does not grade it, treat it as essential.\n"
        "- Write each in the candidate's terms (what they must have / show), grounded in "
        "the description — do not invent a requirement it does not state.\n\n"
        "Rules for the context fields:\n"
        "- If the description does not state a context field, return an EMPTY STRING for "
        "it. Do not guess — a blank is better than a wrong draft.\n\n"
        "Job description:\n"
        f'"""\n{jd_text[:MAX_JD_CHARS]}\n"""'
    )


def _field(value: Any) -> str | None:
    """A drafted context field: a non-empty trimmed string, or None (no draft)."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def parse_jd_extract(value: dict[str, Any]) -> ExtractedDemand:
    """Map the model's output to ``ExtractedDemand`` (pure, defensive). Unknown shapes /
    missing context fields degrade to None (no draft); the requirements array is parsed
    config-driven into discrete draft items (bad entries dropped, deduped, capped)."""
    if not isinstance(value, dict):
        value = {}
    return ExtractedDemand(
        role_open=_field(value.get("role_open")),
        success_measures=_field(value.get("success_measures")),
        requirements=parse_extracted(value.get("requirements")),
    )


__all__ = [
    "ExtractedDemand",
    "JD_CONTEXT_FIELDS",
    "JD_CONTEXT_FIELD_KEYS",
    "JD_EXTRACT_SCHEMA",
    "MAX_JD_CHARS",
    "build_jd_extract_prompt",
    "parse_jd_extract",
]
