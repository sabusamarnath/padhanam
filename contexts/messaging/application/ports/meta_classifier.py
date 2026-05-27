"""MetaClassifier port — three-cell dispatch classification (D140, S52).

D140's meta-classifier dispatch substrate routes inbound messages to
the correct ConversationFlow implementer at P14 close (three cells:
manual_entry, audit_conversation, mirror_conversation). The cell-
internal intent classifiers each carry their own intent surface; the
meta-classifier sits one altitude up and decides which cell receives
the inbound.

The port is async (the production adapter performs an LLM call via
``StructuredOutputPort`` at ``REAL_TIME_REQUIRED`` latency tier per
D122); test adapters can be synchronous-friendly via Python's async
sugar.

The classifier consumes recent conversation history alongside the
inbound message so context-dependent cells (e.g., follow-up turns
into mirror-conversation drill-down) classify correctly even when the
inbound text alone is ambiguous.

Per D140 alternative (a) rejection: the meta-classifier shape replaces
keyword-prefix dispatch (which fails the bet's conversational-UX
positioning). Per D140 alternative (b) rejection: per-cell intent
classification stays at the cell-internal D137 surfaces; the meta-
classifier does not absorb cell-internal intent classes.

Ports are pure per D16 — no SQLAlchemy, no vendor SDKs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
from uuid import UUID

from contexts.messaging.domain.cell_identifier import CellIdentifier


@dataclass(frozen=True)
class ConversationTurn:
    """One turn in the recent conversation history (D140).

    ``role`` is ``"user"`` for inbound messages and ``"assistant"``
    for platform outbound messages. ``text`` is the message body. The
    classifier reads these in chronological order so a relative-intent
    inbound ("tell me about revenue") resolves against the prior
    assistant turn that surfaced the parent case.
    """

    role: str
    text: str

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant"):
            raise ValueError(
                "ConversationTurn.role must be 'user' or 'assistant'; "
                f"got {self.role!r}"
            )
        if not self.text or not self.text.strip():
            raise ValueError("ConversationTurn.text must be non-empty")


@dataclass(frozen=True)
class MetaClassificationResult:
    """The meta-classifier's structured output (D140).

    ``cell_identifier`` names the dispatched cell when confidence is
    high; the dispatch_inbound use case treats the value as the
    authoritative routing decision. ``confidence`` is the self-
    reported confidence in ``[0.0, 1.0]``; the dispatch use case
    compares against the configured cut-offs to choose between Steps
    4 (high-confidence dispatch) and 5 (low-confidence pending).
    """

    cell_identifier: CellIdentifier
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "MetaClassificationResult.confidence must be in [0.0, 1.0]; "
                f"got {self.confidence}"
            )


@runtime_checkable
class MetaClassifier(Protocol):
    """The meta-classifier dispatch port (D140).

    An adapter satisfies the Protocol structurally — the LiteLLM-backed
    adapter at ``contexts/messaging/adapters/llm_meta_classifier.py``
    implements via ``StructuredOutputPort``; the rule-based adapter at
    ``contexts/messaging/adapters/rule_based_meta_classifier.py``
    implements via deterministic substring matching for tests.
    """

    async def classify(
        self,
        *,
        tenant_id: UUID,
        inbound_text: str,
        conversation_history: tuple[ConversationTurn, ...] = (),
    ) -> MetaClassificationResult:
        """Classify the inbound text into a target cell with confidence.

        ``tenant_id`` is the tenant whose conversation history the
        classifier scopes to; the production adapter does not query
        the database (the caller passes ``conversation_history`` already
        loaded). ``inbound_text`` is the user's current message;
        ``conversation_history`` is the recent N turns in chronological
        order. Returns a ``MetaClassificationResult``; raises
        ``StructuredOutputParseFailure`` when the LLM's output cannot
        be parsed (the dispatch use case routes parse-failure as a
        low-confidence Step 5).
        """
        ...


__all__ = [
    "ConversationTurn",
    "MetaClassificationResult",
    "MetaClassifier",
]
