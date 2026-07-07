"""The match — per-criterion coverage of the confirmed skills profile against a
role's selection criteria (S103ag, D239). Matching-engine leg 3 of 3. Pure (D16,
stdlib only).

Leg 1 (D236) extracted what a role wants (``selection_criteria``); leg 2 (D238)
extracted what the operator offers (the confirmed ``:SkillItem`` profile). This
matches them: for each criterion it reads the confirmed profile and marks the
criterion a **strength** (well covered), **partial** (half covered), or **gap**
(not covered), with **evidence** from the profile.

Two disciplines are enforced here, in pure domain, not left to the prompt:

- **Grounded-strict, no invented coverage.** ``parse_match`` maps every returned
  assessment back to an *input* criterion; a criterion the model omits defaults to
  a **gap**, an assessment whose criterion is not one of the inputs is **dropped**
  (no invented criteria), and a ``gap`` band carries no evidence. So an uncovered
  criterion is a gap even if the model tried to argue coverage (D200, D239).
- **The fit-tier suggestion is computed from the coverage mix**, deterministically
  (``suggest_fit_tier``), not opined by the LLM — more grounded and testable.

The apps adapter (``MatchPort``) calls the ``StructuredOutputPort`` with the prompt
+ schema built here and parses the result through ``parse_match``; the litellm SDK
never enters this module or the daily-driver context (D4/D16).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID

# The three coverage bands (D239). ``partial`` carries the tailoring signal (leg 4):
# a half-covered criterion is one to strengthen, which a binary would flatten.
BAND_STRENGTH = "strength"
BAND_PARTIAL = "partial"
BAND_GAP = "gap"
BANDS: tuple[str, ...] = (BAND_STRENGTH, BAND_PARTIAL, BAND_GAP)

# The fit tiers (D221) — the vocabulary the suggestion lands in. Mirrors
# create_lead.FIT_TIERS / pipeline_stats._FIT_ORDER; a domain-local copy keeps this
# pure module free of an application import.
FIT_BULLSEYE = "bullseye"
FIT_STRONG = "strong"
FIT_OPPORTUNISTIC = "opportunistic"

# The selection-criteria blob is capped before it reaches the prompt — a defensive
# bound (the JD-extraction MAX_JD_CHARS precedent).
MAX_CRITERIA_CHARS = 8_000
MAX_PROFILE_CHARS = 12_000

# Coverage-score thresholds mapping the band mix → a fit tier (D239). A domain-level
# default this session (operator-tunable is deferred); score = (strengths +
# 0.5·partials) / n, so a fully-covered role is 1.0 and a fully-uncovered one is 0.0.
_BULLSEYE_AT = 0.75
_STRONG_AT = 0.40

MATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "band": {"type": "string", "enum": list(BANDS)},
                    "evidence": {"type": "string"},
                },
                "required": ["criterion", "band", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["assessments"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class CriterionCoverage:
    """One selection criterion's coverage verdict (D239). ``evidence`` is the profile
    item(s) that support a strength/partial; empty for a gap. Structured so leg 4
    (tailoring) can read the band + evidence per criterion."""

    criterion: str
    band: str
    evidence: str


@dataclass(frozen=True)
class MatchResult:
    """The assembled match (D239): per-criterion coverage + the coverage-computed
    fit-tier suggestion. ``suggested_fit_tier`` is None when there are no criteria to
    match (no suggestion rather than a false one)."""

    coverages: tuple[CriterionCoverage, ...]
    suggested_fit_tier: str | None

    def band_counts(self) -> dict[str, int]:
        counts = {b: 0 for b in BANDS}
        for c in self.coverages:
            counts[c.band] = counts.get(c.band, 0) + 1
        return counts


def _normalize(text: str) -> str:
    """Whitespace-collapsed, lower-cased — the comparison + fingerprint key."""
    return " ".join((text or "").split()).lower()


def split_criteria(criteria_text: str | None) -> tuple[str, ...]:
    """Split the free-text ``selection_criteria`` blob (D228/D236) into discrete
    criteria. Splits on newlines and semicolons, strips leading bullet/number
    markers, drops empties, and de-duplicates on the normalized form (preserving the
    first occurrence's text)."""
    raw = (criteria_text or "")[:MAX_CRITERIA_CHARS]
    pieces: list[str] = []
    for line in raw.replace(";", "\n").splitlines():
        for part in line.split("•"):  # split inline bullets too
            item = _strip_marker(part)
            if item:
                pieces.append(item)
    seen: set[str] = set()
    out: list[str] = []
    for p in pieces:
        key = _normalize(p)
        if key and key not in seen:
            seen.add(key)
            out.append(p)
    return tuple(out)


def _strip_marker(text: str) -> str:
    """Strip a leading bullet or list-number marker (``- ``, ``* ``, ``1. ``, ``1) ``)."""
    s = text.strip().lstrip("-*•–— \t")
    # a leading enumerator like "1." / "2)" — drop it
    i = 0
    while i < len(s) and s[i].isdigit():
        i += 1
    if i > 0 and i < len(s) and s[i] in ".)":
        s = s[i + 1:].strip()
    return s.strip()


def build_match_prompt(
    *, criteria: tuple[str, ...], skills: tuple[str, ...],
    experiences: tuple[str, ...],
) -> str:
    """Build the grounded-strict match prompt (D239). Instructs the model to judge
    each criterion ONLY on what the profile states, to quote profile evidence for a
    strength/partial, and to mark an unsupported criterion a gap (never invent
    coverage). One assessment per criterion, the criterion text verbatim."""
    skills_block = "\n".join(f"- {s}" for s in skills) or "- (none)"
    exp_block = "\n".join(f"- {e}" for e in experiences) or "- (none)"
    crit_block = "\n".join(f"{i}. {c}" for i, c in enumerate(criteria, 1))
    return (
        "You compare a candidate's confirmed skills profile against a role's "
        "selection criteria. For EACH criterion, decide how well the profile covers "
        "it, using exactly one of these bands:\n"
        f"- {BAND_STRENGTH}: the profile clearly covers the criterion.\n"
        f"- {BAND_PARTIAL}: the profile covers the criterion only in part.\n"
        f"- {BAND_GAP}: the profile does not cover the criterion.\n\n"
        "Rules:\n"
        "- Judge ONLY on what the profile states. Do NOT assume, infer, or invent a "
        "skill the profile does not mention. If nothing in the profile supports a "
        "criterion, it is a GAP — an honest gap is better than an invented strength.\n"
        "- For a strength or partial, put the specific profile item(s) that evidence "
        "it in the evidence field (quote them). For a gap, leave evidence EMPTY.\n"
        "- Return exactly one assessment per criterion, using the criterion text "
        "verbatim. Do not add criteria of your own.\n\n"
        "Profile — skills:\n"
        f"{skills_block[:MAX_PROFILE_CHARS]}\n\n"
        "Profile — experience:\n"
        f"{exp_block[:MAX_PROFILE_CHARS]}\n\n"
        "Selection criteria:\n"
        f"{crit_block}"
    )


def _band(value: Any) -> str:
    """Coerce a returned band to the vocabulary; anything unknown is a gap (the
    grounded-strict default — never silently a strength)."""
    if isinstance(value, str) and value.strip().lower() in BANDS:
        return value.strip().lower()
    return BAND_GAP


def parse_match(
    criteria: tuple[str, ...], value: dict[str, Any]
) -> tuple[CriterionCoverage, ...]:
    """Map the model output to one ``CriterionCoverage`` per INPUT criterion,
    grounded-strict (D239). Defensive + pure:

    - every input criterion appears exactly once, in input order;
    - a criterion the model omitted → ``gap`` (never silently covered);
    - an assessment whose criterion is not an input is DROPPED (no invented criteria);
    - a ``gap`` carries no evidence.
    """
    by_norm: dict[str, tuple[str, str]] = {}  # normalized criterion -> (band, evidence)
    raw = value.get("assessments") if isinstance(value, dict) else None
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            crit = entry.get("criterion")
            if not isinstance(crit, str):
                continue
            key = _normalize(crit)
            if not key:
                continue
            band = _band(entry.get("band"))
            evidence = entry.get("evidence")
            evidence = evidence.strip() if isinstance(evidence, str) else ""
            if band == BAND_GAP:
                evidence = ""
            by_norm[key] = (band, evidence)  # last write wins for a repeated criterion
    out: list[CriterionCoverage] = []
    for criterion in criteria:
        band, evidence = by_norm.get(_normalize(criterion), (BAND_GAP, ""))
        out.append(CriterionCoverage(
            criterion=criterion, band=band, evidence=evidence,
        ))
    return tuple(out)


def suggest_fit_tier(
    coverages: tuple[CriterionCoverage, ...]
) -> str | None:
    """Compute the fit-tier suggestion deterministically from the coverage mix
    (D239). score = (strengths + 0.5·partials) / n. ``None`` when there are no
    criteria — no suggestion rather than a false one."""
    n = len(coverages)
    if n == 0:
        return None
    strengths = sum(1 for c in coverages if c.band == BAND_STRENGTH)
    partials = sum(1 for c in coverages if c.band == BAND_PARTIAL)
    score = (strengths + 0.5 * partials) / n
    if score >= _BULLSEYE_AT:
        return FIT_BULLSEYE
    if score >= _STRONG_AT:
        return FIT_STRONG
    return FIT_OPPORTUNISTIC


def build_match(
    criteria: tuple[str, ...], value: dict[str, Any]
) -> MatchResult:
    """The pure assembler: parse (grounded-strict) + compute the tier suggestion."""
    coverages = parse_match(criteria, value)
    return MatchResult(
        coverages=coverages, suggested_fit_tier=suggest_fit_tier(coverages),
    )


def match_inputs_fingerprint(
    *, criteria_text: str | None, confirmed_items: tuple[tuple[UUID, str], ...]
) -> str:
    """A stable hash over the match's inputs (D239) — the staleness signal. Combines
    the normalized selection-criteria text with the sorted confirmed ``(item_id,
    text)`` pairs, so it changes on any criteria edit or profile add/confirm/edit/
    delete. A fingerprint, not a timestamp, because the profile carries no usable
    change timestamp and a timestamp would miss a skill deletion (Step-0, D239)."""
    parts = [_normalize(criteria_text or "")]
    for item_id, text in sorted(
        (str(i), _normalize(t)) for i, t in confirmed_items
    ):
        parts.append(f"{item_id}={text}")
    joined = "".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


__all__ = [
    "BAND_GAP", "BAND_PARTIAL", "BAND_STRENGTH", "BANDS",
    "FIT_BULLSEYE", "FIT_OPPORTUNISTIC", "FIT_STRONG",
    "MATCH_SCHEMA", "CriterionCoverage", "MatchResult",
    "build_match", "build_match_prompt", "match_inputs_fingerprint",
    "parse_match", "split_criteria", "suggest_fit_tier",
]
