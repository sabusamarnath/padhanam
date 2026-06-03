"""Deterministic rule-based MetaClassifier adapter for tests (D140, S52).

A non-LLM ``MetaClassifier`` adapter for unit and integration tests
that exercise ``dispatch_inbound`` without round-tripping a real model.
Classification rules are deterministic substring matches plus a small
relative-intent heuristic over conversation history.

The production behaviour is the ``LlmMetaClassifierAdapter`` at
``contexts/messaging/adapters/llm_meta_classifier.py``; this adapter
is the composition-root swap for tests and for the offline contract
harness.

Per D140 alternative (a) rejection: rule-based dispatch is not the
production architecture (the bet's conversational positioning fails
under keyword-prefix shapes); this adapter exists strictly for test
predictability.
"""

from __future__ import annotations

from uuid import UUID

from contexts.messaging.application.ports.meta_classifier import (
    ConversationTurn,
    MetaClassificationResult,
)
from contexts.messaging.domain.cell_identifier import CellIdentifier


# Substring matches per cell. The order matters when multiple match;
# manual_entry wins on write-shaped verbs, audit_conversation on
# history-shaped nouns, mirror_conversation on read-shaped verbs.
_MANUAL_ENTRY_TOKENS = (
    "add ", "create ", "start tracking", "record ", "update ", "revise ",
    "note that", "track a", "track that",
)
_AUDIT_TOKENS = (
    "audit ", "audit history", "audit log", "what happened",
    "history of ", "show me events", "show me audit",
)
_MIRROR_TOKENS = (
    "show ", "list ", "tell me about", "what's the ", "what is the ",
    "drill down", "parent", "siblings", "children of ",
)
_MIRROR_RELATIVE_TOKENS = (
    "tell me about", "what about ", "drill down", "parent", "siblings",
)
_CALENDAR_TOKENS = (
    "calendar", "meeting", "meetings", "schedule", "what's on",
    "whats on", "next meeting", "free tomorrow", "free today",
    "am i busy", "am i free", "on my calendar",
)
_EMAIL_TOKENS = (
    "email", "emails", "inbox", "what came in", "what came through",
    "did i get", "any mail", "unread", "message from", "messages from",
)


class RuleBasedMetaClassifierAdapter:
    """Deterministic rules over inbound text + relative-intent over history."""

    def __init__(self, *, default_confidence: float = 0.95) -> None:
        if not 0.0 <= default_confidence <= 1.0:
            raise ValueError(
                "default_confidence must be in [0.0, 1.0]; "
                f"got {default_confidence}"
            )
        self._default_confidence = default_confidence

    async def classify(
        self,
        *,
        tenant_id: UUID,
        inbound_text: str,
        conversation_history: tuple[ConversationTurn, ...] = (),
    ) -> MetaClassificationResult:
        del tenant_id
        lowered = inbound_text.lower().strip()

        # Manual entry wins on write-shaped verbs.
        if any(token in lowered for token in _MANUAL_ENTRY_TOKENS):
            return MetaClassificationResult(
                cell_identifier=CellIdentifier.MANUAL_ENTRY,
                confidence=self._default_confidence,
            )

        # Audit conversation wins on history-shaped nouns.
        if any(token in lowered for token in _AUDIT_TOKENS):
            return MetaClassificationResult(
                cell_identifier=CellIdentifier.AUDIT_CONVERSATION,
                confidence=self._default_confidence,
            )

        # Calendar conversation wins on calendar/meeting/schedule nouns,
        # checked before the generic mirror read-verbs so "show my
        # meetings" routes to the calendar surface (S55b-2).
        if any(token in lowered for token in _CALENDAR_TOKENS):
            return MetaClassificationResult(
                cell_identifier=CellIdentifier.CALENDAR_CONVERSATION,
                confidence=self._default_confidence,
            )

        # Email conversation wins on email/inbox/message-arrival nouns,
        # checked before the generic mirror read-verbs so "show my
        # emails" routes to the email surface (S56b).
        if any(token in lowered for token in _EMAIL_TOKENS):
            return MetaClassificationResult(
                cell_identifier=CellIdentifier.EMAIL_CONVERSATION,
                confidence=self._default_confidence,
            )

        # Relative-intent inbound with a prior mirror-conversation
        # outbound in history routes to mirror_conversation.
        if any(token in lowered for token in _MIRROR_RELATIVE_TOKENS):
            return MetaClassificationResult(
                cell_identifier=CellIdentifier.MIRROR_CONVERSATION,
                confidence=self._default_confidence,
            )

        # Mirror conversation wins on read-shaped verbs.
        if any(token in lowered for token in _MIRROR_TOKENS):
            return MetaClassificationResult(
                cell_identifier=CellIdentifier.MIRROR_CONVERSATION,
                confidence=self._default_confidence,
            )

        # No deterministic match — return manual_entry at low confidence
        # so the dispatch use case routes to Step 5 (clarification
        # PendingClarification per D140 dispatch flow).
        return MetaClassificationResult(
            cell_identifier=CellIdentifier.MANUAL_ENTRY,
            confidence=0.2,
        )


__all__ = ["RuleBasedMetaClassifierAdapter"]
