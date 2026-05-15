"""Optimization context ports (D17, D111).

Four consumer-defined ports — two write-side, two read-side — per
D111 commitment 2 and commitment 3:

- ``OptimizationRunRepository`` and ``OptimizationRunReader`` for the
  engine-invocation aggregate.
- ``RecommendationRepository`` and ``RecommendationReader`` for the
  recommendation aggregate plus status-transition rows.

Ports are pure per D16 — no SQLAlchemy, no asyncpg.
"""

from contexts.optimization.ports.optimization_run_reader import (
    OptimizationRunListPage,
    OptimizationRunReader,
    OptimizationRunSnapshot,
)
from contexts.optimization.ports.optimization_run_repository import (
    OptimizationRunRepository,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationListPage,
    RecommendationReader,
)
from contexts.optimization.ports.recommendation_repository import (
    RecommendationRepository,
)

__all__ = [
    "OptimizationRunListPage",
    "OptimizationRunReader",
    "OptimizationRunRepository",
    "OptimizationRunSnapshot",
    "RecommendationListPage",
    "RecommendationReader",
    "RecommendationRepository",
]
