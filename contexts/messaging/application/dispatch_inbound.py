"""dispatch_inbound use case — three-cell ConversationFlow routing (D140, S52).

The five-step dispatch flow per D140:

1. Active-pending check: look up the active PendingClarification for
   ``(tenant_id, user_id)`` via the existing PendingClarificationReader port.
2. If an active pending exists, route via the CellDispatch port to the
   cell named in the pending's ``target_cell`` field.
3. If no active pending, call MetaClassifier with the inbound text plus
   recent conversation history.
4. If MetaClassifier confidence is at or above the configured high
   threshold, route via CellDispatch to the identified cell.
5. If confidence is below the threshold or ``StructuredOutputParseFailure``
   fires, create a meta-classification PendingClarification with
   ``target_cell='dispatch_clarification'`` carrying the original
   inbound text and surface the candidate cells to the user; the next
   reply resolves the routing through Step 2.

The webhook handler at ``apps/api/routers/messaging.py`` (S52 commit 6
refactor) retains signature verification and intake recording, then
invokes ``dispatch_inbound.execute(...)`` instead of calling the
manual entry cell directly.

The use case is composition-root-agnostic: callers pass in a registry
of ``CellRunner`` callables keyed by ``CellIdentifier``, and the
dispatch use case picks the right one. The dispatch_clarification
runner is a sibling concern living at this module (it re-runs the
dispatch flow against the user's disambiguating reply); the three
real-cell runners live at the wiring composition (S52 commit 6).

Ports are pure per D16; the use case sits at the application layer
and depends on the messaging context's ports plus the new
MetaClassifier port.
"""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from uuid import UUID

from contexts.audit.domain.ports import AuditPort

from contexts.messaging.application.create_pending_clarification import (
    create_pending_clarification,
)
from contexts.messaging.application.expire_pending_clarification import (
    expire_pending_clarification,
)
from contexts.messaging.application.ports.cell_dispatch import CellDispatch
from contexts.messaging.application.ports.channel_resolver import (
    ChannelResolver,
)
from contexts.messaging.application.ports.meta_classifier import (
    ConversationTurn,
    MetaClassifier,
)
from contexts.messaging.application.ports.pending_clarification_reader import (
    PendingClarificationReader,
)
from contexts.messaging.application.send_message import send_message
from contexts.messaging.domain.cell_identifier import CellIdentifier
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
)
from contexts.messaging.ports.message_delivery_port import MessageDeliveryPort
from contexts.messaging.ports.message_repository import MessageRepository
from contexts.messaging.ports.pending_clarification_repository import (
    PendingClarificationRepository,
)
from shared_kernel import ActorContext, StructuredOutputParseFailure


@dataclass(frozen=True)
class DispatchContext:
    """Inputs to ``dispatch_inbound`` plus values cells inherit.

    Carries the per-inbound state the dispatched cell needs:
    ``tenant_id`` and ``user_id`` (for active-pending lookup and audit
    chaining), the inbound message text, the intake id the webhook
    just persisted, the reply-to address for outbound delivery, and
    the recent conversation history the meta-classifier and the
    mirror-conversation cell both read.
    """

    tenant_id: UUID
    user_id: str
    inbound_text: str
    inbound_intake_id: UUID
    reply_to: str
    conversation_history: tuple[ConversationTurn, ...] = field(default_factory=tuple)


CellRunner = Callable[[DispatchContext], Awaitable[None]]
"""A callable that runs one ConversationFlow implementer for an inbound."""


# Operator-typed reply tokens that resolve a dispatch_clarification pending
# to a specific cell. Numbered shortcuts mirror the rendered prompt's
# enumeration ("1. record new state ... 2. ask about audit history ...
# 3. view portfolio state"). The lexicon is intentionally narrow so the
# dispatch_clarification handler does not absorb cell-internal intent
# parsing.
_DISPATCH_CLARIFICATION_LEXICON: dict[str, CellIdentifier] = {
    "1": CellIdentifier.MANUAL_ENTRY,
    "manual": CellIdentifier.MANUAL_ENTRY,
    "manual_entry": CellIdentifier.MANUAL_ENTRY,
    "record": CellIdentifier.MANUAL_ENTRY,
    "2": CellIdentifier.AUDIT_CONVERSATION,
    "audit": CellIdentifier.AUDIT_CONVERSATION,
    "audit_conversation": CellIdentifier.AUDIT_CONVERSATION,
    "history": CellIdentifier.AUDIT_CONVERSATION,
    "3": CellIdentifier.MIRROR_CONVERSATION,
    "mirror": CellIdentifier.MIRROR_CONVERSATION,
    "mirror_conversation": CellIdentifier.MIRROR_CONVERSATION,
    "view": CellIdentifier.MIRROR_CONVERSATION,
    "show": CellIdentifier.MIRROR_CONVERSATION,
    "4": CellIdentifier.CALENDAR_CONVERSATION,
    "calendar": CellIdentifier.CALENDAR_CONVERSATION,
    "calendar_conversation": CellIdentifier.CALENDAR_CONVERSATION,
    "meetings": CellIdentifier.CALENDAR_CONVERSATION,
    "5": CellIdentifier.EMAIL_CONVERSATION,
    "email": CellIdentifier.EMAIL_CONVERSATION,
    "email_conversation": CellIdentifier.EMAIL_CONVERSATION,
    "inbox": CellIdentifier.EMAIL_CONVERSATION,
}

# Operator-facing routing-prompt body the dispatch_clarification PendingClarification
# surfaces. The numbered options align with _DISPATCH_CLARIFICATION_LEXICON.
_ROUTING_PROMPT_BODY = (
    "I'm not sure which surface to route this to. Could you say "
    "which you'd like?\n"
    "  1. Record new portfolio state (manual entry).\n"
    "  2. Ask about audit history.\n"
    "  3. View current portfolio state.\n"
    "  4. Ask about your calendar.\n"
    "  5. Ask about your email.\n"
    "(reply with the number, or 'manual', 'audit', 'mirror', 'calendar', or 'email')."
)


async def execute(
    *,
    context: DispatchContext,
    actor: ActorContext,
    pending_reader: PendingClarificationReader,
    pending_repository: PendingClarificationRepository,
    meta_classifier: MetaClassifier,
    high_confidence_threshold: float,
    cell_dispatch: CellDispatch,
    audit_port: AuditPort,
    cell_runners: dict[CellIdentifier, CellRunner],
    message_repository: MessageRepository,
    delivery_port: MessageDeliveryPort,
    channel_resolver: ChannelResolver,
    from_address: str,
) -> CellIdentifier:
    """Execute the D140 dispatch flow over one inbound; return the routed cell.

    The dispatched cell runs asynchronously via the CellDispatch port;
    this function returns once the routing decision is made and the
    cell-run is enqueued. The returned ``CellIdentifier`` is the cell
    the inbound was routed to (or ``DISPATCH_CLARIFICATION`` when
    Step 5 fired). The return value supports test observability;
    production callers (the webhook) discard it.
    """
    # Step 1: active-pending check.
    active = await pending_reader.get_active(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
    )

    if active is not None:
        # Special handling for dispatch_clarification: parse the user's
        # disambiguating reply and re-route the original inbound to the
        # cell they named.
        if active.target_cell == CellIdentifier.DISPATCH_CLARIFICATION.value:
            return await _resolve_dispatch_clarification(
                context=context,
                actor=actor,
                active=active,
                pending_repository=pending_repository,
                cell_dispatch=cell_dispatch,
                audit_port=audit_port,
                cell_runners=cell_runners,
                message_repository=message_repository,
                delivery_port=delivery_port,
                channel_resolver=channel_resolver,
                from_address=from_address,
            )

        # Step 2: real-cell active pending → dispatch the named cell.
        cell_identifier = CellIdentifier(active.target_cell)
        await _dispatch_cell(
            context=context,
            cell_identifier=cell_identifier,
            cell_dispatch=cell_dispatch,
            cell_runners=cell_runners,
        )
        return cell_identifier

    # Step 3: meta-classify the inbound.
    try:
        result = await meta_classifier.classify(
            tenant_id=context.tenant_id,
            inbound_text=context.inbound_text,
            conversation_history=context.conversation_history,
        )
    except StructuredOutputParseFailure:
        # Step 5 trigger: parse failure routes as a low-confidence
        # dispatch_clarification.
        await _create_and_send_dispatch_clarification(
            context=context,
            actor=actor,
            pending_repository=pending_repository,
            audit_port=audit_port,
            message_repository=message_repository,
            delivery_port=delivery_port,
            channel_resolver=channel_resolver,
            from_address=from_address,
        )
        return CellIdentifier.DISPATCH_CLARIFICATION

    # Step 4: high-confidence dispatch.
    if result.confidence >= high_confidence_threshold:
        await _dispatch_cell(
            context=context,
            cell_identifier=result.cell_identifier,
            cell_dispatch=cell_dispatch,
            cell_runners=cell_runners,
        )
        return result.cell_identifier

    # Step 5: low-confidence dispatch_clarification.
    await _create_and_send_dispatch_clarification(
        context=context,
        actor=actor,
        pending_repository=pending_repository,
        audit_port=audit_port,
        message_repository=message_repository,
        delivery_port=delivery_port,
        channel_resolver=channel_resolver,
        from_address=from_address,
    )
    return CellIdentifier.DISPATCH_CLARIFICATION


# ----------------------------------------------------------------------- helpers


async def _dispatch_cell(
    *,
    context: DispatchContext,
    cell_identifier: CellIdentifier,
    cell_dispatch: CellDispatch,
    cell_runners: dict[CellIdentifier, CellRunner],
) -> None:
    """Invoke the CellDispatch port with the registered runner for ``cell_identifier``."""
    if cell_identifier not in cell_runners:
        raise ValueError(
            "dispatch_inbound has no registered runner for "
            f"{cell_identifier.value!r}; composition root must register "
            "every CellIdentifier value the dispatcher may route to"
        )
    runner = cell_runners[cell_identifier]

    def _bound() -> Awaitable[None]:
        return runner(context)

    await cell_dispatch.dispatch(
        _bound,
        context={
            "intake_id": str(context.inbound_intake_id),
            "tenant_id": str(context.tenant_id),
            "user_id": context.user_id,
            "cell": cell_identifier.value,
        },
    )


async def _create_and_send_dispatch_clarification(
    *,
    context: DispatchContext,
    actor: ActorContext,
    pending_repository: PendingClarificationRepository,
    audit_port: AuditPort,
    message_repository: MessageRepository,
    delivery_port: MessageDeliveryPort,
    channel_resolver: ChannelResolver,
    from_address: str,
) -> None:
    """Step 5 of the dispatch flow: persist the pending and send the prompt."""
    proposed_intent: dict[str, Any] = {
        "purpose": "dispatch_clarification",
        "original_inbound_text": context.inbound_text,
        "original_intake_id": str(context.inbound_intake_id),
    }
    await create_pending_clarification(
        repository=pending_repository,
        audit_port=audit_port,
        actor=actor,
        user_id=context.user_id,
        originating_channel="WHATSAPP",
        originating_user_address=context.reply_to,
        originating_intake_id=context.inbound_intake_id,
        proposed_intent=proposed_intent,
        proposed_action_summary="route ambiguous inbound to the right cell",
        target_cell=CellIdentifier.DISPATCH_CLARIFICATION.value,
    )
    await send_message(
        repository=message_repository,
        delivery_port=delivery_port,
        audit_port=audit_port,
        channel_resolver=channel_resolver,
        actor=actor,
        from_address=from_address,
        to_address=context.reply_to,
        body=_ROUTING_PROMPT_BODY,
    )


async def _resolve_dispatch_clarification(
    *,
    context: DispatchContext,
    actor: ActorContext,
    active: PendingClarification,
    pending_repository: PendingClarificationRepository,
    cell_dispatch: CellDispatch,
    audit_port: AuditPort,
    cell_runners: dict[CellIdentifier, CellRunner],
    message_repository: MessageRepository,
    delivery_port: MessageDeliveryPort,
    channel_resolver: ChannelResolver,
    from_address: str,
) -> CellIdentifier:
    """Resolve an active dispatch_clarification pending against the user's reply.

    The user's reply names which cell the original inbound should
    route to. Recognised tokens (numbers 1/2/3, "manual", "audit",
    "mirror", plus synonyms) live in ``_DISPATCH_CLARIFICATION_LEXICON``;
    unrecognised replies expire the prior pending and create a new
    one (effectively repeating Step 5 of the flow).
    """
    normalised = context.inbound_text.strip().lower().rstrip(".,!?")
    first_token = normalised.split(" ", 1)[0] if normalised else ""
    chosen = (
        _DISPATCH_CLARIFICATION_LEXICON.get(normalised)
        or _DISPATCH_CLARIFICATION_LEXICON.get(first_token)
    )
    # One "now" for this resolve turn — the expiry here is reply-driven (the
    # action instant), so the operation owns its now and passes it (S75).
    now = datetime.now(timezone.utc)

    if chosen is None:
        # Unrecognised reply — expire the prior pending and re-prompt.
        await expire_pending_clarification(
            repository=pending_repository,
            audit_port=audit_port,
            actor=actor,
            pending=active,
            now=now,
        )
        await _create_and_send_dispatch_clarification(
            context=context,
            actor=actor,
            pending_repository=pending_repository,
            audit_port=audit_port,
            message_repository=message_repository,
            delivery_port=delivery_port,
            channel_resolver=channel_resolver,
            from_address=from_address,
        )
        return CellIdentifier.DISPATCH_CLARIFICATION

    # Recognised reply: expire the prior pending, then dispatch the
    # chosen cell against the *original* inbound text (preserved on
    # the pending's proposed_intent at creation time).
    await expire_pending_clarification(
        repository=pending_repository,
        audit_port=audit_port,
        actor=actor,
        pending=active,
        now=now,
    )

    original_text = str(active.proposed_intent.get("original_inbound_text", ""))
    original_intake_str = str(
        active.proposed_intent.get(
            "original_intake_id", str(context.inbound_intake_id)
        )
    )
    try:
        original_intake_id = UUID(original_intake_str)
    except ValueError:
        original_intake_id = context.inbound_intake_id

    rerouted_context = DispatchContext(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        inbound_text=original_text or context.inbound_text,
        inbound_intake_id=original_intake_id,
        reply_to=context.reply_to,
        conversation_history=context.conversation_history,
    )

    await _dispatch_cell(
        context=rerouted_context,
        cell_identifier=chosen,
        cell_dispatch=cell_dispatch,
        cell_runners=cell_runners,
    )
    return chosen


__all__ = [
    "CellRunner",
    "DispatchContext",
    "execute",
]
