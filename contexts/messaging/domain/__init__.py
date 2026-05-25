"""Messaging domain layer (D129).

- ``Message`` (aggregate root) at ``message.py`` — one inbound or
  outbound communication on a channel, with the ``MessageDirection``,
  ``MessageChannel``, and ``MessageStatus`` enums.
- The intent value objects at ``intent.py`` (S46) — the discriminated
  union the manual entry cell extracts from an inbound message.

Domain code is framework-free per D16 — stdlib plus shared_kernel.
"""

from contexts.messaging.domain.intent import (
    INTENT_EXTRACTION_SCHEMA,
    AddDataPointIntent,
    CreateCaseIntent,
    Intent,
    IntentType,
    ReviseDataPointIntent,
    UnclearIntent,
    parse_intent,
)
from contexts.messaging.domain.message import (
    Message,
    MessageChannel,
    MessageDirection,
    MessageStatus,
)
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
    PendingClarificationStatus,
)

__all__ = [
    "INTENT_EXTRACTION_SCHEMA",
    "AddDataPointIntent",
    "CreateCaseIntent",
    "Intent",
    "IntentType",
    "Message",
    "MessageChannel",
    "MessageDirection",
    "MessageStatus",
    "PendingClarification",
    "PendingClarificationStatus",
    "ReviseDataPointIntent",
    "UnclearIntent",
    "parse_intent",
]
