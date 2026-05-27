"""LiteLLM-backed MetaClassifier adapter (D140, D130, D122, S52).

Implements the ``MetaClassifier`` port at
``contexts/messaging/application/ports/meta_classifier.py`` via the
existing ``StructuredOutputPort`` (D130) at the ``REAL_TIME_REQUIRED``
latency tier (D122). The structured-output schema is the four-cell
enum (minus dispatch_clarification — the routing layer never asks the
model to return the sentinel; ambiguous inbounds surface as low
confidence on a real cell identifier per D140's Step 5 commitment)
plus a confidence float.

Sits at ``contexts/messaging/adapters/`` (sibling of ``outbound/``)
matching the ``threshold_single_pair.py`` placement convention — the
adapter has no vendor dependency of its own (LiteLLM enters via the
StructuredOutputPort implementation at the inference adapter).

The adapter is stateless; one instance serves every dispatch_inbound
invocation. Composition root wiring sets it on the
``MessagingComposition`` (S52 commit 6).
"""

from __future__ import annotations

from uuid import UUID

from contexts.messaging.application.ports.meta_classifier import (
    ConversationTurn,
    MetaClassificationResult,
)
from contexts.messaging.domain.cell_identifier import CellIdentifier
from shared_kernel import (
    LatencyTier,
    StructuredOutputPort,
    StructuredOutputRequest,
)
from shared_kernel.meta_classification import (
    META_CLASSIFIER_SCHEMA,
    build_meta_classifier_prompt,
    render_conversation_history,
)


class LlmMetaClassifierAdapter:
    """LiteLLM-backed adapter for the MetaClassifier port (D140)."""

    def __init__(
        self,
        *,
        structured_output_port: StructuredOutputPort,
        latency_tier: LatencyTier = LatencyTier.REAL_TIME_REQUIRED,
    ) -> None:
        self._structured_output = structured_output_port
        self._latency_tier = latency_tier

    async def classify(
        self,
        *,
        tenant_id: UUID,
        inbound_text: str,
        conversation_history: tuple[ConversationTurn, ...] = (),
    ) -> MetaClassificationResult:
        del tenant_id  # The classifier itself is tenant-agnostic; the
        # caller scopes which conversation history is loaded.
        history_text = render_conversation_history(conversation_history)
        prompt = build_meta_classifier_prompt(
            inbound_text=inbound_text,
            conversation_history_text=history_text,
        )
        request = StructuredOutputRequest(
            prompt=prompt,
            schema=META_CLASSIFIER_SCHEMA,
            latency_tier=self._latency_tier,
            temperature=0.0,
        )
        result = await self._structured_output.generate_structured(request)
        value = result.value
        raw_identifier = str(value.get("cell_identifier", "")).strip()
        cell_identifier = CellIdentifier(raw_identifier)
        confidence = float(value.get("confidence", 0.0))
        return MetaClassificationResult(
            cell_identifier=cell_identifier,
            confidence=confidence,
        )


__all__ = ["LlmMetaClassifierAdapter"]
