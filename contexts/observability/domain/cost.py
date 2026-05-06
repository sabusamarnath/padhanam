"""Cost value objects for the observability read path (D49, D57).

``CostBreakdown`` carries the per-trace cost rollup the recommendation
engine and the evaluation harness consume: input USD, output USD, and
total USD as ``Decimal`` so monetary precision is not surrendered to
binary floating point. The shape mirrors D49's three ``gen_ai.cost.*``
attributes the LiteLLMAdapter emits per completion span; aggregation
across observations on a single trace is the adapter's responsibility,
which keeps cost-shaped consumers (cost-per-successful-task at S17b,
recommendation surface at P11) free of vendor-specific summation logic.

Domain code is framework-free per D16 — stdlib dataclasses, no
Pydantic, no SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CostBreakdown:
    total_usd: Decimal
    input_usd: Decimal
    output_usd: Decimal
