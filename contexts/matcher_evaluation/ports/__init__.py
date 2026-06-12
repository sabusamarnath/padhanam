"""matcher_evaluation ports — the legal cross-context surface (D17, D185).

``MatcherQualityRunReader`` is the port the optimization EvidenceContext consumes
(S91); ``MatcherQualityRunRepository`` is the producer's write side.
"""

from __future__ import annotations

from contexts.matcher_evaluation.ports.matcher_quality_run_reader import (
    MatcherQualityRunReader,
)
from contexts.matcher_evaluation.ports.matcher_quality_run_repository import (
    MatcherQualityRunRepository,
)

__all__ = ["MatcherQualityRunReader", "MatcherQualityRunRepository"]
