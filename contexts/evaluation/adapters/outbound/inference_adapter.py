"""Inference adapter implementing evaluation's InferencePort.

Translates evaluation's value objects (``ModelConfig``, ``ReplayResult``)
into the inference context's published surface
(``contexts.inference.api.request_completion``). The cross-context
import goes through the api facade per D17 — never into inference's
application or adapter directories. The api facade re-exports
``Message`` and ``request_completion``; this adapter constructs a
single-user-message ``Message`` from the input text and threads
through the tenant context unchanged.

Async-over-sync bridge: ``contexts.inference.api.request_completion``
and the LiteLLMAdapter's ``complete`` are sync; the FastAPI router at
``apps/api/routers/inference.py`` calls them with a sync ``def``
endpoint. Evaluation's use cases are async, so the adapter offloads
the sync call into a thread via ``asyncio.to_thread`` to avoid
blocking the event loop. This is the only place evaluation's async
contract and inference's sync contract meet.

trace_id surfacing: the inference adapter (LiteLLMAdapter) captures
the trace_id from the OTel span it opened around the LiteLLM call
and attaches it to the ``Completion`` it returns. Evaluation reads
``completion.trace_id`` directly. If trace_id is absent (no active
span context, or the OTel pipeline is not set up at test time), the
adapter returns an empty string — the empty case is honest about
the absence rather than fabricating an id, and downstream cost
queries skip rows where trace_id is empty.

ModelConfig.temperature and ModelConfig.max_tokens are not surfaced
through the inference port at S17a. The current InferencePort shape
(``messages``, ``model``, ``tenant_context``) does not accept
sampling parameters; the adapter routes ``model_config.model_name``
through and discards the rest. The fields exist on ModelConfig as
forward-affordance for when the inference port grows sampling
parameters; landing them through speculatively here would couple
evaluation to a port shape that does not yet accept them.
"""

from __future__ import annotations

import asyncio

from contexts.evaluation.domain.model_config import ModelConfig
from contexts.evaluation.domain.replay_result import ReplayResult
from contexts.inference.api import Message, request_completion
from contexts.inference.ports import InferencePort as _InferencingInferencePort
from shared_kernel import LatencyTier, TenantContext


class InferenceAdapter:
    """Adapter implementing evaluation's InferencePort against
    ``contexts.inference``.

    Constructed with the inference context's port (typically the
    LiteLLMAdapter wired at apps/api/main.py). The adapter does not
    instantiate the underlying port itself — composition lives in
    apps/, the same shape the inference router uses.
    """

    def __init__(self, inference_port: _InferencingInferencePort) -> None:
        self._inference_port = inference_port

    async def complete(
        self,
        *,
        model_config: ModelConfig,
        input: str,
        tenant_context: TenantContext,
    ) -> ReplayResult:
        # D122 (S46): the replay engine and prompt applier run as an
        # evaluation harness — substrate analysis the user is not
        # waiting on in real time — so this path opts into the
        # async-tolerant tier per D122's classification.
        completion = await asyncio.to_thread(
            request_completion,
            port=self._inference_port,
            messages=[Message(role="user", content=input)],
            model=model_config.model_name,
            tenant_context=tenant_context,
            latency_tier=LatencyTier.ASYNC_TOLERANT,
        )
        return ReplayResult(
            output_text=completion.text,
            trace_id=completion.trace_id or "",
        )
