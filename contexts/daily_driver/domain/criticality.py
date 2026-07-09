"""Requirement criticality — a reasoned, evidence-linked claim, not a score (S103ai, D241).

For each discrete demand requirement (D240), criticality is a **reasoned explanation** of
how load-bearing it is, a **hard-gate** flag (pass-fail bars — a minimum-years threshold,
a required certification), and **coarse span references** into the addressable demand spec
(``demand_spec``) that back the claim. It is deliberately **not a score**: a number is
opaque false-precision; a claim with its evidence shown is what the LLM does well and what
the operator can verify.

Two disciplines, enforced here in the domain (not trusted to the prompt), mirroring the
grounded-strict ``parse_match`` (D239):

- **Grounded-strict on references.** Every span reference must **resolve** against the
  addressable spec; a non-resolving (hallucinated or stale) reference is **dropped**. A
  claim left with no resolving span **collapses to low-confidence** with no shown evidence
  — reasoning from general knowledge has no span to point at.
- **Honest low-confidence.** When the spec does not signal importance, the assessment says
  ``low`` rather than inventing a ranking. Unknown/absent confidence defaults **low**
  (conservative — never overclaim).

Criticality attributes are **config rows** (``CRITICALITY_FIELDS``, the D240
``REQUIREMENT_FIELDS`` pattern), not hardcoded fields; the assessment rides on the
requirement item as a nested dict. Pure (D16, stdlib only).
"""

from __future__ import annotations

import json
from typing import Any

from contexts.daily_driver.domain.demand_requirements import IMPORTANCE_ESSENTIAL
from contexts.daily_driver.domain.demand_spec import (
    DemandSpecIndex,
    index_demand_spec,
    resolve_spans,
)

CONFIDENCE_HIGH = "high"
CONFIDENCE_LOW = "low"
CONFIDENCE_LEVELS: tuple[str, ...] = (CONFIDENCE_HIGH, CONFIDENCE_LOW)
# Unknown / absent confidence is conservative — never overclaim (D241 honest low-confidence).
DEFAULT_CONFIDENCE = CONFIDENCE_LOW

# The coverage bands (D239) that count as a gap for critical-gap flagging.
_BAND_GAP = "gap"
_BAND_PARTIAL = "partial"

# The config-driven criticality attribute set (D241, the REQUIREMENT_FIELDS pattern). Each
# row drives the assessment sub-schema + the prompt; adding an attribute is a row here.
# (key, json_type, enum_or_None, prompt_description)
CRITICALITY_FIELDS: tuple[tuple[str, str, tuple[str, ...] | None, str], ...] = (
    ("explanation", "string", None,
     "one or two sentences on how load-bearing this requirement is, grounded in what the "
     "spec says — not general knowledge"),
    ("hard_gate", "boolean", None,
     "true only if it is a pass-fail bar (a minimum-years threshold, a required "
     "certification, a mandatory clearance); false for a graded preference"),
    ("spans", "array", None,
     "the ids of the spec spans (sections/sentences, e.g. sec-1 or sent-3) that back this "
     "claim — cite only ids you can see in the spec above"),
    ("confidence", "string", CONFIDENCE_LEVELS,
     "high if the spec clearly signals this requirement's importance; low if the spec is a "
     "flat, unweighted list and you cannot honestly rank it"),
)


def _normalize(text: str) -> str:
    return " ".join((text or "").split()).lower()


def criticality_batch_schema(requirement_texts: tuple[str, ...]) -> dict[str, Any]:
    """The batch assessment schema (D241) — one object per requirement carrying the
    requirement text (to map back) + the config-driven CRITICALITY_FIELDS. Config-driven:
    adding a CRITICALITY_FIELDS row extends every assessment with no code change."""
    props: dict[str, Any] = {"requirement": {"type": "string"}}
    for key, json_type, enum_values, _desc in CRITICALITY_FIELDS:
        spec: dict[str, Any] = {"type": json_type}
        if json_type == "array":
            spec["items"] = {"type": "string"}
        if enum_values is not None:
            spec["enum"] = list(enum_values)
        props[key] = spec
    return {
        "type": "object",
        "properties": {
            "assessments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": props,
                    "required": ["requirement", *(k for k, *_ in CRITICALITY_FIELDS)],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["assessments"],
        "additionalProperties": False,
    }


def build_criticality_prompt(
    *, requirement_texts: tuple[str, ...], spec_prompt: str
) -> str:
    """Build the grounded-strict criticality prompt (D241). Instructs the model to assess
    each requirement's load-bearingness from the spec, cite resolvable span ids, flag
    hard gates, and say low-confidence when the spec does not signal importance."""
    fields = "\n".join(f"- {key}: {desc}" for key, _t, _e, desc in CRITICALITY_FIELDS)
    reqs = "\n".join(f"{i}. {t}" for i, t in enumerate(requirement_texts, 1))
    return (
        "You assess how CRITICAL each requirement is to a role, using ONLY the demand "
        "spec below. The spec is split into addressable spans, each with an id "
        "([sec-N] a section, [sent-N] a sentence).\n\n"
        "For EACH requirement, return an assessment with these fields:\n"
        f"{fields}\n\n"
        "Rules:\n"
        "- Ground every claim in the spec. Cite the span ids that back it in `spans`. "
        "Cite ONLY ids you can see above — never invent an id.\n"
        "- If the spec does not clearly signal a requirement's importance (a flat, "
        "unweighted list), set confidence `low` and say so — do NOT invent a ranking.\n"
        "- Do not reason from general knowledge about what senior roles usually need; if "
        "there is no span to point at, the confidence is low.\n"
        "- Return exactly one assessment per requirement, using the requirement text "
        "verbatim in `requirement`.\n\n"
        "Demand spec (addressable spans):\n"
        f"{spec_prompt}\n\n"
        "Requirements:\n"
        f"{reqs}"
    )


def _confidence(value: Any) -> str:
    if isinstance(value, str) and value.strip().lower() in CONFIDENCE_LEVELS:
        return value.strip().lower()
    return DEFAULT_CONFIDENCE


def parse_criticality(
    requirement_texts: tuple[str, ...], index: DemandSpecIndex, value: dict[str, Any]
) -> dict[str, dict]:
    """Map the model output to one criticality assessment per INPUT requirement, keyed by
    normalized requirement text (D241), grounded-strict:

    - an assessment whose requirement is not an input is **dropped** (no invented
      requirements);
    - each span reference is **validated to resolve** against ``index``; a non-resolving
      reference is dropped;
    - a claim left with **no resolving span** is forced to **low-confidence**, evidence
      empty (ungrounded);
    - an empty explanation → no assessment (dropped);
    - confidence coerced to the vocabulary, defaulting low.
    """
    valid = {_normalize(t) for t in requirement_texts}
    out: dict[str, dict] = {}
    raw = value.get("assessments") if isinstance(value, dict) else None
    if not isinstance(raw, list):
        return out
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        req = entry.get("requirement")
        if not isinstance(req, str):
            continue
        key = _normalize(req)
        if key not in valid or key in out:
            continue
        explanation = entry.get("explanation")
        explanation = explanation.strip() if isinstance(explanation, str) else ""
        if not explanation:
            continue
        raw_spans = entry.get("spans")
        span_ids = (
            tuple(s for s in raw_spans if isinstance(s, str))
            if isinstance(raw_spans, list) else ()
        )
        resolved = tuple(s.id for s in resolve_spans(index, span_ids))
        confidence = _confidence(entry.get("confidence"))
        if not resolved:
            # ungrounded — no span to point at, so honest low-confidence (D241)
            confidence = CONFIDENCE_LOW
        hard_gate = entry.get("hard_gate") is True
        out[key] = {
            "explanation": explanation,
            "hard_gate": hard_gate,
            "spans": list(resolved),
            "confidence": confidence,
        }
    return out


def attach_criticality(
    items: tuple[dict, ...], crit_by_norm: dict[str, dict]
) -> tuple[dict, ...]:
    """Attach the parsed criticality to each requirement item by normalized text (D241).
    Items without an assessment keep their prior criticality (if any) untouched."""
    out: list[dict] = []
    for item in items:
        crit = crit_by_norm.get(_normalize(item["text"]))
        if crit is not None:
            out.append({**item, "criticality": crit})
        else:
            out.append(item)
    return tuple(out)


def is_high_criticality(item: dict) -> bool:
    """A requirement is high-criticality when it is a hard gate or an essential (D241) —
    the class whose uncovered gap is a critical gap."""
    crit = item.get("criticality") or {}
    return bool(crit.get("hard_gate")) or item.get("importance") == IMPORTANCE_ESSENTIAL


def critical_gap(item: dict, coverage_band: str | None) -> bool:
    """A gap (or a thin partial on a hard gate) on a high-criticality requirement (D241).
    ``coverage_band`` is the D239 match band for this requirement, or None (no match →
    no critical-gap flag; criticality stands alone)."""
    if coverage_band is None:
        return False
    crit = item.get("criticality") or {}
    hard = bool(crit.get("hard_gate"))
    if coverage_band == _BAND_GAP:
        return hard or item.get("importance") == IMPORTANCE_ESSENTIAL
    if coverage_band == _BAND_PARTIAL:
        return hard   # a hard gate only half-covered is still a critical risk
    return False


def build_requirement_view(
    item: dict, index: DemandSpecIndex, coverage_band: str | None
) -> dict:
    """The enriched requirement for the surface (D241): the item + its criticality with
    **spans resolved to text** (a stored span that no longer resolves is dropped — the
    grounded-strict guard applied on read too) + the coverage band + the critical-gap
    flag. Verdict-first (D233): the explanation is the verdict, the resolved spans the
    evidence one glance away."""
    crit = item.get("criticality") or {}
    spans = resolve_spans(index, tuple(crit.get("spans") or ()))
    return {
        "id": item["id"],
        "text": item["text"],
        "importance": item["importance"],
        "proof_state": item["proof_state"],
        "criticality": crit.get("explanation") or None,
        "hard_gate": bool(crit.get("hard_gate")),
        "criticality_confidence": crit.get("confidence") if crit else None,
        "criticality_spans": [
            {"id": s.id, "kind": s.kind, "text": s.text} for s in spans
        ],
        "coverage_band": coverage_band,
        "critical_gap": critical_gap(item, coverage_band),
    }


def _coverage_by_norm(match_result_json: str | None) -> dict[str, str]:
    """Parse the stored D239 match result (``[{criterion, band, evidence}]`` JSON) into
    ``{normalized criterion: band}``. Defensive: bad JSON → empty (no critical gaps)."""
    if not match_result_json:
        return {}
    try:
        raw = json.loads(match_result_json)
    except (ValueError, TypeError):
        return {}
    out: dict[str, str] = {}
    if isinstance(raw, list):
        for c in raw:
            if (
                isinstance(c, dict)
                and isinstance(c.get("criterion"), str)
                and isinstance(c.get("band"), str)
            ):
                out[_normalize(c["criterion"])] = c["band"]
    return out


def build_requirement_views(
    items: tuple[dict, ...], jd_text: str | None, match_result_json: str | None
) -> tuple[dict, ...]:
    """The enriched requirement views for the surface (D241) — each item with its
    criticality resolved (spans → text, coverage band, critical-gap flag), against the
    addressable spec (indexed from the JD) and the D239 match. A missing match → no
    coverage band and no critical-gap flag (criticality stands alone)."""
    index = index_demand_spec(jd_text)
    cov = _coverage_by_norm(match_result_json)
    return tuple(
        build_requirement_view(item, index, cov.get(_normalize(item["text"])))
        for item in items
    )


__all__ = [
    "CONFIDENCE_HIGH",
    "CONFIDENCE_LEVELS",
    "CONFIDENCE_LOW",
    "CRITICALITY_FIELDS",
    "DEFAULT_CONFIDENCE",
    "attach_criticality",
    "build_criticality_prompt",
    "build_requirement_view",
    "build_requirement_views",
    "criticality_batch_schema",
    "critical_gap",
    "is_high_criticality",
    "parse_criticality",
]
