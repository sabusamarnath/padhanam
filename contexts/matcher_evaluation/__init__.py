"""contexts/matcher_evaluation/ — the matcher-quality producer (D185).

Mirrors the ``retrieval_evaluation`` producer pattern (D108/D111): a producer
context computes structural quality metrics on a subject's output, persists them
on a run aggregate, and exposes them behind a reader port the optimization
``EvidenceContext`` reads. Here the subject is the moat's matcher
(``correlate_goal_facets``, D169) and the metrics are label-free structural
proxies — single-signal share, candidate-to-confirmed ratio, orphan rate.

Self-contained per the cross-context independence contracts (D17): this context
never imports ``daily_driver``. The matcher's edges are projected to the neutral
``MatcherQualitySample`` at the composition root (``apps/``); this context only
sees the sample. Its ``.ports`` are the legal cross-context surface — optimization
will depend on ``MatcherQualityRunReader`` (S91), not on this context's internals.

S90 ships the producer + the baseline; S91 wires the reader port into the
EvidenceContext and adds the first matcher RecommendationRule (single-signal
demotion). Hexagonal layout per D16.
"""
