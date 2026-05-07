"""Public read-only query interface for the ingestion context (D17).

Cross-context callers (the agent runtime at P8 reading retrieved
chunks; the recommendation engine at P11 reading source-level
metrics) call through here. The api facade is the single import
target for cross-context consumers; D17 forbids reaching into
``contexts.ingestion.{domain,application,adapters}`` directly.

S19 lands the bounded-context skeleton; the api surface stays
empty until the first cross-context consumer arrives. The file
exists as the structural commitment: every context exposes its
public surface here, and the import-linter contract recognises
the facade pattern through the ignore_imports clauses on
api.py → its own application/domain edges (per the S17b refinement).

Surface forecast: a ``RetrievalClient`` port and a corresponding
read use case land at S22 (or absorbed at S21) per D5; cross-
context consumers at P8 and P11 import retrieval-shaped
read functions through here once they exist.
"""

from __future__ import annotations

__all__: list[str] = []
