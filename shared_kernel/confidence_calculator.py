"""ConfidenceCalculator port — confidence-aware composition primitive (D134, S47).

D134 commits confidence-aware response composition as a Phase 2-A
architectural primitive. ConversationFlow implementers operate on a
three-case discipline — high / medium / low confidence — over an
LLM-derived classification. ``ConfidenceCalculator`` is the pluggable
abstraction that produces the confidence value the discipline
consumes, mirroring D111's MetricCalculator pattern at the producer-
context altitude.

Adapter selection at the composition root is configuration, not
domain change. Phase 2-A: the ``SelfReportedConfidenceAdapter`` at
``contexts/inference/adapters/confidence_self_reported.py`` reads the
``confidence`` field the model populates in its structured output.
Future adapters consume token-level probabilities (where the provider
exposes them), run multi-sample agreement counts, or implement
operator-designed methodologies — each behind this same port. The
cell consumes confidence through the port and does not know which
adapter produced the value.

Per D16 shared_kernel cannot import Pydantic; this is a plain
Protocol over the StructuredOutputRequest / StructuredOutputResponse
primitives at ``shared_kernel/structured_output.py``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from shared_kernel.structured_output import (
    StructuredOutputRequest,
    StructuredOutputResponse,
)


@runtime_checkable
class ConfidenceCalculator(Protocol):
    """Pluggable confidence calculation behind D134's three-case discipline.

    Implementations return a float in [0.0, 1.0]; the calling cell
    compares against the high and medium cut-offs from
    ``padhanam/config/messaging.py`` to select Case 1 (proceed), Case
    2 (clarify with PendingClarification), or Case 3 (generic
    clarification).
    """

    def compute(
        self,
        *,
        request: StructuredOutputRequest,
        response: StructuredOutputResponse[Any],
    ) -> float:
        """Return the confidence of ``response`` for ``request``.

        Implementations return a float in ``[0.0, 1.0]``. Methodology
        differences between implementations sit entirely behind this
        signature; the caller treats the returned value as opaque
        evidence for the three-case decision.
        """
        ...


__all__ = ["ConfidenceCalculator"]
