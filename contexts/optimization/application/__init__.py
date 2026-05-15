"""Optimization application layer (D108, D111).

EvidenceContext wraps the four consumer-defined reader ports per
D111 commitment 5; rules at ``rules/`` consume the context and
produce ``RecommendationCandidate`` instances.

Use cases land at commit 5 (engine orchestration, get/list,
lifecycle transitions) per the S41 sequence.
"""

from contexts.optimization.application.evidence_context import EvidenceContext

__all__ = ["EvidenceContext"]
