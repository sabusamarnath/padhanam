"""Recommendation category enum (D108, D111 commitment 3).

Four committed categories at P11 close per D108: retrieval_strategy,
model_choice, prompt_revision, cost_optimization. The category
discriminator drives the evidence_citations union shape per D111
commitment 7.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from enum import Enum


class RecommendationCategory(str, Enum):
    """Recommendation category discriminator (D108).

    The first four are the inference categories (D108). ``MATCHER_SUPPRESSION``
    (D185/S91) is the first non-inference category — the moat's matcher as an
    optimization target; its first rule is single-signal suppression.
    """

    RETRIEVAL_STRATEGY = "retrieval_strategy"
    MODEL_CHOICE = "model_choice"
    PROMPT_REVISION = "prompt_revision"
    COST_OPTIMIZATION = "cost_optimization"
    MATCHER_SUPPRESSION = "matcher_suppression"


__all__ = ["RecommendationCategory"]
