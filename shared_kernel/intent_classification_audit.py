"""Audit-conversation intent prompt and schema — cross-cutting primitive (D137, D138, P14, S51).

Sibling to ``shared_kernel/intent_classification.py`` (the manual entry
cell's prompt+schema primitive). The audit-conversation cell consumes
this module; the D137 evaluation runner at
``contexts/intent_classification_evaluation/`` consumes the same
primitive when running an audit-conversation gold set. Single-source-
of-truth structural binding ensures the substrate measures what
production runs.

Per the D137 substrate parameterisation deferred-decisions entry (S51
framing), the evaluation runner gains a small surface-to-primitive
lookup at S51 commit 6 mapping the gold-set's ``intent_surface`` field
to the appropriate (prompt builder, schema) pair. The third-instance
trigger (mirror-conversation at S52, plus any P15+ extension) promotes
the lookup to a parameterised abstraction.

Framework-free per D16 — schema is a plain dict; prompt builder is a
pure function on strings.
"""

from __future__ import annotations

from typing import Any


AUDIT_EXTRACTION_PREAMBLE: str = (
    "You extract a structured audit-query intent from a message a busy "
    "professional sent their assistant. The message is a question about "
    "the audit chain — the operator is asking about platform actions, "
    "actor activity, or event history. Classify the message as "
    "find_by_case (audit events for a named case), find_by_date_range "
    "(audit events in a relative time window), find_by_actor (audit "
    "events authored by a named actor), find_by_event_type (audit "
    "events of a given action), find_by_combination (multiple filters "
    "combined in one query), or unclear_audit (the message does not map "
    "cleanly to one of those). Fill only the fields relevant to the "
    "chosen intent; leave every other field as an empty string. For "
    "find_by_date_range and the date-range slot of find_by_combination, "
    "range_keyword is one of today, yesterday, this_week, last_week, "
    "this_month, last_month. Populate the confidence field with your "
    "self-reported confidence in the classification (0.0-1.0)."
)


# JSON Schema (strict-mode) the audit-intent extraction call conforms
# to. Flat object; every field is required; non-applicable fields come
# back as empty strings. The intent_class enum values match the
# ``contexts.audit_conversation.domain.intent.AuditIntentType`` StrEnum
# values; a unit test asserts the alignment so the duplication does not
# drift silently.
AUDIT_INTENT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent_class": {
            "type": "string",
            "enum": [
                "find_by_case",
                "find_by_date_range",
                "find_by_actor",
                "find_by_event_type",
                "find_by_combination",
                "unclear_audit",
            ],
            "description": "the kind of audit query the message asks for",
        },
        "case_reference": {
            "type": "string",
            "description": (
                "a natural-language reference to an existing case — for "
                "find_by_case or find_by_combination; empty string otherwise"
            ),
        },
        "range_keyword": {
            "type": "string",
            "description": (
                "the time-window keyword — one of today, yesterday, "
                "this_week, last_week, this_month, last_month — for "
                "find_by_date_range or find_by_combination; empty string "
                "otherwise"
            ),
        },
        "actor": {
            "type": "string",
            "description": (
                "an actor identifier or name — for find_by_actor or "
                "find_by_combination; empty string otherwise"
            ),
        },
        "event_type": {
            "type": "string",
            "description": (
                "an action-verb event type (e.g. portfolio.case.create) — "
                "for find_by_event_type or find_by_combination; empty "
                "string otherwise"
            ),
        },
        "clarification": {
            "type": "string",
            "description": (
                "a short follow-up question the assistant should ask — "
                "for unclear_audit; empty string otherwise"
            ),
        },
        "confidence": {
            "type": "number",
            "description": (
                "self-reported confidence in the classification, 0.0-1.0"
            ),
            "minimum": 0.0,
            "maximum": 1.0,
        },
    },
    "required": [
        "intent_class",
        "case_reference",
        "range_keyword",
        "actor",
        "event_type",
        "clarification",
        "confidence",
    ],
    "additionalProperties": False,
}


def build_audit_extraction_prompt(message: str) -> str:
    """Return the audit-intent extraction prompt for a given user message."""
    return f"{AUDIT_EXTRACTION_PREAMBLE}\n\nMessage:\n{message}"


__all__ = [
    "AUDIT_EXTRACTION_PREAMBLE",
    "AUDIT_INTENT_EXTRACTION_SCHEMA",
    "build_audit_extraction_prompt",
]
