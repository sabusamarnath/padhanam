"""Self-reported confidence adapter — Phase 2-A placeholder (D134, S47).

Phase 2-A implementation of ``ConfidenceCalculator`` (per
``shared_kernel/confidence_calculator.py``). Reads the ``confidence``
field the model populates in its structured output (via the schema
itself when the schema carries a ``confidence`` property) and returns
that value.

When the schema does not carry a ``confidence`` field — or the model
omits it — the adapter falls back to a configured default. Phase 2-A
default is 0.5, deliberately middle-of-the-range: a missing
confidence is "no signal," not "high confidence" and not "low
confidence." The default value is configurable so the operator can
tune cell behaviour under missing-signal conditions without code
change.

Future adapters consume logprobs (where provider exposes them), run
multi-sample agreement, or implement operator-designed methodologies —
each behind the same ``ConfidenceCalculator`` port; the cell consumes
confidence opaquely.

Sits at ``contexts/inference/adapters/`` (sibling of ``outbound/``)
because the adapter takes no vendor dependency — its input is the
shared_kernel ``StructuredOutputResponse``, not a vendor SDK call.
The litellm adapter under ``outbound/`` is the structured-output
provider; this adapter is its methodology-of-trust-the-model-on-its-
confidence companion at the same architectural altitude.
"""

from __future__ import annotations

from typing import Any

from shared_kernel.structured_output import (
    StructuredOutputRequest,
    StructuredOutputResponse,
)


class SelfReportedConfidenceAdapter:
    """Confidence-as-self-report — read ``response.confidence`` directly."""

    def __init__(self, *, default_when_absent: float = 0.5) -> None:
        if not 0.0 <= default_when_absent <= 1.0:
            raise ValueError(
                "default_when_absent must be in [0.0, 1.0]"
            )
        self._default = default_when_absent

    def compute(
        self,
        *,
        request: StructuredOutputRequest,
        response: StructuredOutputResponse[Any],
    ) -> float:
        """Return the model's self-reported confidence, or the default."""
        del request  # Phase 2-A self-report reads only the response.
        if response.confidence is None:
            return self._default
        value = float(response.confidence)
        # Clamp into [0.0, 1.0] in case the model returns out-of-range.
        return max(0.0, min(1.0, value))


__all__ = ["SelfReportedConfidenceAdapter"]
