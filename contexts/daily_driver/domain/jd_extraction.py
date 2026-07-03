"""Job-description extraction — the pure prompt + schema + parser (S103ad, D236).

Leg one of the matching engine: read a pasted job description and draft three D228
qualification fields — why the role is open, role success measures, selection
criteria. The apps adapter calls the ``StructuredOutputPort`` (the LiteLLM seam, the
``CddDrafterAdapter`` precedent) with this prompt + schema and parses the result;
the litellm SDK never enters this module or the daily-driver context (D4/D16).

Each drafted field is a *suggestion* written to a ``q_<key>_draft`` slot (D236),
never the field value — the operator Uses (and edits) then Saves, or Dismisses.
The prompt is instructed to return an empty string for a field the JD does not
state, so extraction never invents a fact (D200).

Pure (D16, stdlib only).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# The three JD-derivable qualification fields (a subset of D228's QUAL_FIELDS).
# interview_process is deferred (JDs describe rounds inconsistently — low yield).
JD_DRAFT_FIELDS: tuple[tuple[str, str], ...] = (
    ("role_open", "why the role is open"),
    ("success_measures", "what the hire must deliver in the first 6-12 months"),
    ("selection_criteria", "the must-have skills and experience they select on"),
)
JD_DRAFT_FIELD_KEYS: tuple[str, ...] = tuple(k for k, _ in JD_DRAFT_FIELDS)

# The JD text is capped before it reaches the prompt — a defensive bound so a
# pasted page (or an accidental whole-inbox paste) cannot blow the context window.
MAX_JD_CHARS = 12_000

JD_EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {k: {"type": "string"} for k, _ in JD_DRAFT_FIELDS},
    "required": list(JD_DRAFT_FIELD_KEYS),
    "additionalProperties": False,
}


@dataclass(frozen=True)
class ExtractedQualification:
    """The three drafted fields (each None when the JD does not state it). None means
    'no draft' — no suggestion is written for that field."""

    role_open: str | None
    success_measures: str | None
    selection_criteria: str | None

    def drafts(self) -> tuple[tuple[str, str], ...]:
        """The (field_key, draft_text) pairs that actually have a draft — the
        use case writes only these, so a field the JD omits stays blank."""
        pairs = (
            ("role_open", self.role_open),
            ("success_measures", self.success_measures),
            ("selection_criteria", self.selection_criteria),
        )
        return tuple((k, v) for k, v in pairs if v)


def build_jd_extract_prompt(jd_text: str) -> str:
    """Build the extraction prompt (S103ad, D236). Instructs the model to draft only
    the three fields, in the candidate's terms, and to return an empty string for a
    field the JD does not state (no invention — the operator proofs, D200)."""
    body = "\n".join(
        f"- {key}: {desc}" for key, desc in JD_DRAFT_FIELDS
    )
    return (
        "You read a job description and pull out three things a candidate uses to "
        "qualify a role. Draft ONLY these three, each one short (a sentence or a "
        "few bullet-like phrases), grounded in what the description actually says:\n"
        f"{body}\n\n"
        "Rules:\n"
        "- If the description does not state a field, return an EMPTY STRING for it. "
        "Do not guess or invent — a blank is better than a wrong draft.\n"
        "- Write for the candidate (what the role needs, what they select on), not a "
        "summary of the whole posting.\n\n"
        "Job description:\n"
        f'"""\n{jd_text[:MAX_JD_CHARS]}\n"""'
    )


def _field(value: Any) -> str | None:
    """A drafted field: a non-empty trimmed string, or None (no draft)."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def parse_jd_extract(value: dict[str, Any]) -> ExtractedQualification:
    """Map the model's output to ``ExtractedQualification`` (pure, defensive).
    Unknown shapes / missing fields degrade to None (no draft) rather than raising."""
    if not isinstance(value, dict):
        value = {}
    return ExtractedQualification(
        role_open=_field(value.get("role_open")),
        success_measures=_field(value.get("success_measures")),
        selection_criteria=_field(value.get("selection_criteria")),
    )


__all__ = [
    "ExtractedQualification",
    "JD_DRAFT_FIELDS",
    "JD_DRAFT_FIELD_KEYS",
    "JD_EXTRACT_SCHEMA",
    "MAX_JD_CHARS",
    "build_jd_extract_prompt",
    "parse_jd_extract",
]
