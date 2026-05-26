"""GoldSetReader consumer port (D137, S48b Option B).

The gold set lives in a YAML fixture at Phase 2-A; the adapter at
``contexts.intent_classification_evaluation.adapters.outbound.fixture``
reads the YAML and returns the in-memory ``IntentClassificationGoldSet``.
The port is defined so future per-tenant gold-set authoring (D137
alternative (c) activation) can swap a Postgres-backed adapter
without runner-side change.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contexts.intent_classification_evaluation.domain.gold_set import (
    IntentClassificationGoldSet,
)


@runtime_checkable
class GoldSetReader(Protocol):
    """Read-side port returning gold sets by name."""

    def get_gold_set(self, name: str) -> IntentClassificationGoldSet:
        """Return the gold set with this name, or raise KeyError."""
        ...


__all__ = ["GoldSetReader"]
