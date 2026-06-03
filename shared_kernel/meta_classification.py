"""Meta-classifier prompt and schema — cross-cutting LLM-call primitive (D140, S52).

D140's meta-classifier dispatch routes inbound messages to the right
ConversationFlow implementer (manual_entry, audit_conversation,
mirror_conversation) plus the dispatch_clarification sentinel for the
low-confidence routing case. The prompt and schema live at
``shared_kernel/`` so the production adapter at
``contexts/messaging/adapters/llm_meta_classifier.py`` and the D137-
substrate evaluation runner consume the same primitive — the same
single-source-of-truth discipline ``shared_kernel/intent_classification.py``
established at S48b for the manual entry cell.

Per D16 ``shared_kernel/`` is policed framework-free. The schema is a
plain ``dict``; the prompt builder is a pure function over strings.
"""

from __future__ import annotations

from typing import Any


META_CLASSIFIER_PREAMBLE: str = (
    "You route a portfolio-management message to the correct "
    "conversational surface inside Padhanam's private-assistant "
    "platform. Four surfaces handle the user's inbounds, plus a "
    "fifth sentinel for ambiguous cases:\n\n"
    "- manual_entry: the user is recording new portfolio state "
    "(creating a case, adding a data point against a case, revising "
    "an existing data point). Look for verbs like 'add', 'create', "
    "'start tracking', 'update', 'note that'.\n"
    "- audit_conversation: the user is asking about the audit history "
    "of what happened in the platform — who did what, when, against "
    "which case. Look for words like 'audit', 'history', 'log', "
    "'what happened', 'show me events'.\n"
    "- mirror_conversation: the user is querying current portfolio "
    "state — listing cases, showing a case, showing a data point, "
    "drilling down into a case's children, asking for parents or "
    "siblings of an artefact already in context. Look for words like "
    "'show', 'list', 'tell me about', 'drill down', 'parent', "
    "'siblings'.\n"
    "- calendar_conversation: the user is asking about their calendar "
    "— meetings and events on their schedule, what is on today or this "
    "week, meetings with a person, a specific meeting by name, or their "
    "next meeting. Look for words like 'calendar', 'meeting', 'meetings', "
    "'schedule', 'event', 'what's on', 'free', 'busy', 'next meeting'.\n"
    "- dispatch_clarification: reserved for the routing layer when "
    "no single surface fits. **Do not return this value yourself**; "
    "if the inbound is ambiguous between surfaces, return your best "
    "guess at a real surface with a low confidence value (below 0.5) "
    "and the dispatch layer will surface a clarifying question.\n\n"
    "Use the recent conversation history as context — a relative "
    "follow-up ('tell me about revenue') against a prior "
    "mirror-conversation outbound routes to mirror_conversation even "
    "though the inbound text alone is ambiguous. Populate the "
    "confidence field with your self-reported confidence in the "
    "classification (0.0-1.0)."
)


META_CLASSIFIER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cell_identifier": {
            "type": "string",
            "enum": [
                "manual_entry",
                "audit_conversation",
                "mirror_conversation",
                "calendar_conversation",
            ],
            "description": (
                "the conversational surface the inbound routes to"
            ),
        },
        "confidence": {
            "type": "number",
            "description": (
                "self-reported confidence in the classification; "
                "0.0 to 1.0"
            ),
        },
    },
    "required": ["cell_identifier", "confidence"],
    "additionalProperties": False,
}


def build_meta_classifier_prompt(
    *,
    inbound_text: str,
    conversation_history_text: str = "",
) -> str:
    """Build the structured-output prompt for meta-classification.

    ``conversation_history_text`` is a flattened textual rendering of
    the recent turns the caller has loaded (typically rendered as
    ``"user: ...\\nassistant: ...\\n..."``). The caller decides how
    many turns to include; the prompt simply concatenates the
    rendered history before the current inbound.
    """
    history_block = (
        f"\n\nRecent conversation:\n{conversation_history_text.rstrip()}"
        if conversation_history_text.strip()
        else ""
    )
    return (
        f"{META_CLASSIFIER_PREAMBLE}"
        f"{history_block}"
        f'\n\nThe operator just sent: "{inbound_text}"'
    )


def render_conversation_history(turns) -> str:
    """Flatten conversation turns into the prompt's history block.

    Pure function over ``Iterable[ConversationTurn]``; the caller
    passes the turns the meta-classifier should see (typically the
    most recent N from the messaging substrate's Message store).
    """
    return "\n".join(f"{t.role}: {t.text}" for t in turns)


__all__ = [
    "META_CLASSIFIER_PREAMBLE",
    "META_CLASSIFIER_SCHEMA",
    "build_meta_classifier_prompt",
    "render_conversation_history",
]
