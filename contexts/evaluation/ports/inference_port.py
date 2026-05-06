"""InferencePort — evaluation's contract for cross-context inference.

The replay engine and the prompt applier both call into inference to
run a model against an input. Rather than reaching across into
``contexts.inference``'s ports directly (which would couple the
evaluation domain to inference's value-object shapes), evaluation
defines its own port. The adapter at
``contexts/evaluation/adapters/outbound/inference_adapter.py``
translates between evaluation's value objects (``ModelConfig``,
``ReplayResult``) and the inference context's public surface
(``contexts.inference.api.request_completion``).

The port is async because the evaluation use cases that consume it
(``apply_scoring_sheet``, ``replay_and_score``) are async. The
underlying inference path is currently sync (the LiteLLMAdapter's
``complete`` is sync); the adapter offloads via ``asyncio.to_thread``
so the event loop stays unblocked.

Cross-context dependency-direction note (D16): evaluation's adapter
imports ``contexts.inference.api`` (the published facade per D17),
not ``contexts.inference.application`` or ``contexts.inference.adapters``.
The import-linter ``contexts-independent-application`` and
``contexts-independent-adapters`` contracts both stay green; the
api facade is the single legitimate cross-context entry point.
"""

from __future__ import annotations

from typing import Protocol

from contexts.evaluation.domain.model_config import ModelConfig
from contexts.evaluation.domain.replay_result import ReplayResult
from shared_kernel import TenantContext


class InferencePort(Protocol):
    async def complete(
        self,
        *,
        model_config: ModelConfig,
        input: str,
        tenant_context: TenantContext,
    ) -> ReplayResult: ...
