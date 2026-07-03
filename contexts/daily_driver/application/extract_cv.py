"""extract_cv_profile — parse a CV PDF and seed the operator's skills profile
(S103af, D238). Matching-engine leg two.

Parses the uploaded PDF behind ``CvParserPort`` (pdfplumber; text-layer + multi-
column, OCR deferred), extracts a skills profile behind ``CvExtractorPort`` (the
LiteLLM seam), and seeds each drafted item as a *suggestion* (:SkillItem
proof_state='suggested', D238) on a deterministic id — so a re-upload MERGEs onto the
same nodes instead of duplicating, and never un-confirms an already-proofed item.
Only the operator's confirm/edit promotes an item to 'confirmed' (D200/D215).

A scanned PDF (no text layer) seeds nothing and reports ``needs_text_layer`` so the
surface can flag a re-export (OCR deferred).
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.daily_driver.domain.cv_extraction import skill_item_id
from contexts.daily_driver.ports.cv_extractor import CvExtractorPort
from contexts.daily_driver.ports.cv_parser import CvParserPort
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)


@dataclass(frozen=True)
class CvExtractionResult:
    """The outcome of a CV upload (D238): how many items were seeded, and whether the
    PDF lacked a text layer (a scanned image → flagged for re-export, nothing seeded)."""

    seeded: int
    needs_text_layer: bool
    page_count: int


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def extract_cv_profile(
    *, goal_graph: GoalGraphPort, cv_parser: CvParserPort,
    cv_extractor: CvExtractorPort, actor: ActorContext, pdf_bytes: bytes,
) -> CvExtractionResult:
    """Parse the CV and seed the drafted profile as suggestions (D238). Returns how
    many items were seeded. A no-text-layer PDF seeds nothing and sets
    ``needs_text_layer`` (re-export flagged, OCR deferred); a non-conforming model
    response seeds nothing (the caller reloads the profile either way)."""
    parsed = await cv_parser.parse(pdf_bytes=pdf_bytes)
    if not parsed.has_text_layer:
        return CvExtractionResult(
            seeded=0, needs_text_layer=True, page_count=parsed.page_count,
        )
    extracted = await cv_extractor.extract(cv_text=parsed.text)
    if extracted is None:
        return CvExtractionResult(
            seeded=0, needs_text_layer=False, page_count=parsed.page_count,
        )
    seeded = 0
    for kind, text in extracted.items():
        await goal_graph.seed_skill_item(
            tenant_context=actor.tenant_context,
            item_id=skill_item_id(kind, text), kind=kind, text=text,
        )
        seeded += 1
    return CvExtractionResult(
        seeded=seeded, needs_text_layer=False, page_count=parsed.page_count,
    )


__all__ = ["CvExtractionResult", "extract_cv_profile"]
