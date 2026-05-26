"""ConversationFlow Protocol — cross-context multi-turn-interaction contract (D115, S45).

D115 committed conversation flow as a Phase 2-A architectural
primitive — the standard interface for multi-turn interactions that
resolve revisions and clarifications. This module commits its
concrete shape. Unlike the Revisable shape (which warranted its own
D125 because the shape had contested alternatives), the
ConversationFlow shape lands directly under D115: there are no
contested alternatives to weigh.

``ConversationFlow`` is the structural contract for a multi-turn
interaction with a clean lifecycle — ``open`` starts a conversation
from a ``ConversationInvocation`` and returns the initial
``ConversationState``; ``turn`` advances it by one
``ConversationInput`` and returns the next ``ConversationState``;
``close`` terminates it from a ``ConversationClosure`` and returns
the terminal ``ConversationOutcome``. The methods are async because
a conversation turn typically involves an LLM call.

``CitedResponse`` Protocol (D138, S51) is the cross-cutting structural
enforcement of D131 provenance-aware response composition. Every
ConversationFlow implementer's response value object satisfies
``CitedResponse`` structurally by carrying three citation tuple fields.
``ArtefactCitation`` is the typed value object that populates
``cited_artefacts``: artefact id plus artefact-type discriminator. The
Phase 2-A discriminator union is ``"case"`` and ``"data_point"``;
future artefact types extend the union.

No implementer registers at S45 — audit-conversation (5.1) and
portfolio mirror-conversation (4.1) implementers land at P14+. The
contract harness at ``tests/contract/conversation_flow/`` is ready
for them.

The five value objects carry no bounded-context type — ``shared_kernel/``
cannot import ``contexts/`` per D16. ``parameters`` / ``payload`` /
``metadata`` are open ``dict`` slots an implementer owns.

Framework-free per D16 — shared_kernel is policed; stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class ConversationInvocation:
    """The input that opens a conversation.

    ``purpose`` names what the conversation is for; ``actor_id`` is
    who it is with; ``parameters`` is an implementer-owned slot for
    invocation-specific opening parameters.
    """

    purpose: str
    actor_id: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConversationState:
    """The state carried across conversation turns.

    Returned by ``open`` and ``turn``. ``turn_count`` is 0 at open
    and advances by one per turn; ``is_open`` is True between open
    and close; ``payload`` is the implementer-owned accumulated
    state.
    """

    conversation_id: str
    purpose: str
    turn_count: int
    is_open: bool
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConversationInput:
    """A single user turn's input."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConversationClosure:
    """The instruction to close a conversation."""

    reason: str


@dataclass(frozen=True)
class ConversationOutcome:
    """The terminal result of a closed conversation.

    ``resolution`` is the outcome classification; ``payload`` carries
    the conversation's produced artefact(s).
    """

    conversation_id: str
    turn_count: int
    resolution: str
    payload: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ConversationFlow(Protocol):
    """Multi-turn-interaction contract (D115 primitive, S45 shape).

    An implementer satisfies ``ConversationFlow`` structurally — no
    explicit inheritance is required. The ``@runtime_checkable``
    decorator additionally allows ``isinstance`` conformance checks,
    which the contract harness exercises.
    """

    async def open(
        self, invocation: ConversationInvocation
    ) -> ConversationState:
        """Start a conversation; return the initial state."""
        ...

    async def turn(
        self, state: ConversationState, user_input: ConversationInput
    ) -> ConversationState:
        """Advance the conversation by one turn; return the next state."""
        ...

    async def close(
        self, state: ConversationState, closure: ConversationClosure
    ) -> ConversationOutcome:
        """Terminate the conversation; return the terminal outcome."""
        ...


@dataclass(frozen=True)
class ArtefactCitation:
    """Typed citation for a domain artefact (D138 primitive, S51 shape).

    Authored fresh at S51 (the P14 framing brief's "currently at the
    manual entry cell module" claim was structurally false — pre-write
    reconciliation Finding 4 surfaced the absence). The discriminator
    surfaces artefact type at the citation surface because artefacts are
    heterogeneous in ``cited_artefacts`` at P14: audit-conversation and
    mirror-conversation both cite Case and DataPoint references through
    one tuple field. Future artefact types extend the ``artefact_type``
    discriminator union; Phase 2-A union: ``"case"``, ``"data_point"``.
    """

    artefact_id: UUID
    artefact_type: str

    def __post_init__(self) -> None:
        if not isinstance(self.artefact_type, str) or not self.artefact_type:
            raise ValueError(
                "ArtefactCitation.artefact_type must be a non-empty string; "
                f"got {self.artefact_type!r}"
            )


@runtime_checkable
class CitedResponse(Protocol):
    """Provenance-aware response composition contract (D138, S51).

    The cross-cutting structural enforcement of D131. Every
    ConversationFlow implementer's response value object satisfies
    ``CitedResponse`` structurally by carrying three citation tuple
    fields. The ``@runtime_checkable`` decorator allows ``isinstance``
    conformance checks the contract harness exercises at
    ``tests/contract/conversation_flow/test_cited_response_conformance.py``.

    The three fields cite different artefact categories:

    - ``cited_intake_records``: IntakeRecord ids per D127/D128 intake-
      canonical commitment.
    - ``cited_audit_events``: audit event ids per D102/D103 audit-chain
      substrate.
    - ``cited_artefacts``: heterogeneous artefact citations (typed via
      ``ArtefactCitation`` with the artefact-type discriminator) — Case,
      DataPoint, and future artefact types.

    A response satisfying the Protocol may leave any tuple empty when
    the implementer's natural composition does not populate it (S46's
    CellResponse leaves ``cited_audit_events`` empty per D131 first-
    instance disposition; mirror-conversation leaves ``cited_audit_events``
    empty per audit-chain transitivity through cited IntakeRecord
    anchoring per D128).
    """

    cited_intake_records: tuple[UUID, ...]
    cited_audit_events: tuple[UUID, ...]
    cited_artefacts: tuple[ArtefactCitation, ...]


__all__ = [
    "ArtefactCitation",
    "CitedResponse",
    "ConversationClosure",
    "ConversationFlow",
    "ConversationInput",
    "ConversationInvocation",
    "ConversationOutcome",
    "ConversationState",
]
