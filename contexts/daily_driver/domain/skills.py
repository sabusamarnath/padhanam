"""The operator skills profile domain — the standing profile behind opportunity fit
(S103af, D238). Pure (D16, stdlib only).

A :SkillItem is one entry in the operator's standing skills profile, extracted from
their CV and read by every opportunity (not per-opportunity data). It follows the
extract-and-proof lifecycle (D215/D222): a CvExtractorPort drafts items
``suggested``; only the operator's confirm promotes an item to ``confirmed``. Leg 3
reads the confirmed profile against the D228 selection criteria to feed the D221 fit
tier — so the profile is evidence only once proofed, the same posture as :Contact.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

# The two kinds of profile entry (D238) — a named skill, or an experience line.
KINDS = ("skill", "experience")

# The proof lifecycle (D215/D222): drafted from the CV, then vouched by the operator.
PROOF_STATES = ("suggested", "confirmed")


@dataclass(frozen=True)
class SkillItemView:
    """One skill-profile entry as read for the surface + leg-3 fit read (D238).

    ``proof_state`` is ``suggested`` until the operator confirms (or edits, which is
    an authoring act) → ``confirmed``. ``provenance_origin`` is ``cv_extraction`` for
    a drafted item, ``user_authored`` for a hand-added one.
    """

    item_id: UUID
    kind: str
    text: str
    proof_state: str
    provenance_origin: str


def confirmed_only(
    items: tuple[SkillItemView, ...]
) -> tuple[SkillItemView, ...]:
    """The proofed profile — only ``confirmed`` items are evidence for the leg-3 fit
    read (D238), the same is-usable posture as a proofed :Contact (D222)."""
    return tuple(i for i in items if i.proof_state == "confirmed")


__all__ = ["KINDS", "PROOF_STATES", "SkillItemView", "confirmed_only"]
