"""The addressable demand spec — a coarse index over the stored JD (S103ai, D241).

The raw job description (D236) is made **coarse-addressable**: split deterministically
into sections (blank-line blocks) and sentences, each with a **stable identifier**
(``sec-N`` / ``sent-N``) that a criticality span reference (D241) points to. This is an
**index over stored text**, re-derived on demand — no new document, no storage. Because
derivation is deterministic, a stored span reference resolves against the same JD text on
any later read; if the JD text changes, a reference may stop resolving (the read simply
drops it, the grounded-strict guard).

Coarse spans only (the operator's ruling): section or sentence, never the exact phrase —
the verification value without the fragility of exact-match against LLM output. Precise
spans are deferred to real need (D184/D186, coarse-then-precise).

Pure (D16, stdlib only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SECTION_PREFIX = "sec-"
SENTENCE_PREFIX = "sent-"

# A defensive cap on how much of a pasted JD is indexed (the extraction MAX_JD_CHARS
# precedent) — a whole-page paste cannot blow up the index or the prompt.
MAX_SPEC_CHARS = 12_000

# Coarse sentence split: a terminator (. ! ?) followed by whitespace, or a newline.
# Deliberately simple (coarse spans, D241 — not a linguistic tokenizer).
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Span:
    """One addressable coarse span of the demand spec (D241). ``id`` is the stable
    identifier a criticality reference points to (``sec-N`` / ``sent-N``); ``kind`` is
    ``section`` or ``sentence``; ``text`` is the span's text."""

    id: str
    kind: str
    text: str


@dataclass(frozen=True)
class DemandSpecIndex:
    """The addressable demand spec (D241) — its sections and sentences, each a ``Span``
    with a stable id. Derived deterministically from the stored JD text."""

    spans: tuple[Span, ...]

    def ids(self) -> frozenset[str]:
        return frozenset(s.id for s in self.spans)

    def resolve(self, span_id: str) -> str | None:
        """The text for a span id, or ``None`` when it does not resolve (a hallucinated
        or stale reference — the grounded-strict guard, D241)."""
        for s in self.spans:
            if s.id == span_id:
                return s.text
        return None

    def is_empty(self) -> bool:
        return not self.spans


def _sentences(block: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(block)]
    return [p for p in parts if p]


def index_demand_spec(jd_text: str | None) -> DemandSpecIndex:
    """Index the stored JD into coarse addressable sections + sentences (D241),
    deterministically. Sections are blank-line-separated blocks (``sec-N``); sentences
    are the coarse sentence split within each block (``sent-N``, globally numbered).
    Empty/blank text yields an empty index."""
    text = (jd_text or "")[:MAX_SPEC_CHARS].strip()
    if not text:
        return DemandSpecIndex(spans=())
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    spans: list[Span] = []
    sent_n = 0
    for sec_n, block in enumerate(blocks):
        # collapse intra-block newlines so a section reads as one coherent text
        block_text = " ".join(block.split())
        spans.append(Span(id=f"{SECTION_PREFIX}{sec_n}", kind="section", text=block_text))
        for sentence in _sentences(block_text):
            spans.append(
                Span(id=f"{SENTENCE_PREFIX}{sent_n}", kind="sentence", text=sentence)
            )
            sent_n += 1
    return DemandSpecIndex(spans=tuple(spans))


def spans_for_prompt(index: DemandSpecIndex) -> str:
    """Render the addressable spec for the criticality prompt (D241): each section with
    its id, then its sentences with ids, so the model cites a real id it can see."""
    lines: list[str] = []
    current_section: str | None = None
    for s in index.spans:
        if s.kind == "section":
            current_section = s.id
            lines.append(f"[{s.id}] {s.text}")
        else:
            lines.append(f"    [{s.id}] {s.text}")
    return "\n".join(lines)


def resolve_spans(
    index: DemandSpecIndex, span_ids: tuple[str, ...]
) -> tuple[Span, ...]:
    """Resolve a list of span ids to their ``Span`` objects, dropping any that do not
    resolve (the grounded-strict reference guard, D241). Order-preserving, deduped."""
    out: list[Span] = []
    seen: set[str] = set()
    for sid in span_ids:
        if sid in seen:
            continue
        text = index.resolve(sid)
        if text is None:
            continue
        seen.add(sid)
        out.append(Span(id=sid, kind=_kind_of(sid), text=text))
    return tuple(out)


def _kind_of(span_id: str) -> str:
    return "section" if span_id.startswith(SECTION_PREFIX) else "sentence"


__all__ = [
    "DemandSpecIndex",
    "MAX_SPEC_CHARS",
    "SECTION_PREFIX",
    "SENTENCE_PREFIX",
    "Span",
    "index_demand_spec",
    "resolve_spans",
    "spans_for_prompt",
]
