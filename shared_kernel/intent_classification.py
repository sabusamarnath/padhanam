"""Intent-classification prompt and schema — cross-cutting LLM-call primitive (D137, S48b).

D137 commits an intent-classification evaluation substrate at
``contexts/intent_classification_evaluation/``. The substrate's
load-bearing claim — "measure component-quality of model X against
Padhanam's intent surface" — requires the substrate to call the
structured-output port with the same prompt and schema the
production cell uses. Otherwise the substrate measures a different
prompt's classifications.

The cell's prompt-and-schema primitive lived at
``contexts/messaging/domain/intent.py`` and
``contexts/messaging/application/manual_entry_cell.py`` until S48b;
S48b extracts both to this shared_kernel module so the cell and the
evaluation runner share a single source of truth. A symbol-identity
structural test at ``tests/contract/shared_kernel/`` binds the
single-source-of-truth claim in CI.

Per D16 ``shared_kernel/`` is policed framework-free. The schema is
a plain ``dict``; the prompt builder is a pure function over
strings. No Pydantic, no Pydantic-derived primitives, no LLM-vendor
SDK references.

Intent value-object types (``Intent``, ``CreateCaseIntent``,
``AddDataPointIntent``, ``ReviseDataPointIntent``, ``UnclearIntent``,
``IntentType``) stay at ``contexts/messaging/domain/intent.py`` per
the messaging-context-owns-its-domain-types discipline. The schema
and prompt are the cross-cutting primitives the substrate-under-
test exposes; the parsed-value types are messaging-domain shape.

Future ConversationFlow implementers at P14+ (audit-conversation,
mirror-conversation) extend this module with sub-surfaces (or
create their own equivalents) per the build-at-second-instance
discipline at D127 alternative (d).
"""

from __future__ import annotations

from typing import Any


EXTRACTION_PREAMBLE: str = (
    "You extract a structured intent from a portfolio-management "
    "message a busy professional sent their assistant. Classify the "
    "message as create_case (start tracking a new case or item), "
    "add_data_point (record a goal, status, or methodology "
    "application against an existing case), revise_data_point (update "
    "an existing data point), or unclear (the message does not map "
    "cleanly to one of those). Fill only the fields relevant to the "
    "chosen intent; leave every other field as an empty string. For "
    "add_data_point, data_point_type is one of GOAL, STATUS, or "
    "METHODOLOGY_APPLICATION. Populate the confidence field with your "
    "self-reported confidence in the classification (0.0-1.0)."
)


# JSON Schema (strict-mode) the structured-output intent-extraction
# call conforms to. A flat object: every field is required and
# non-applicable fields come back as empty strings, which strict mode
# tolerates cleanly. The intent_type enum literal values mirror the
# ``contexts.messaging.domain.intent.IntentType`` StrEnum values; a
# unit test at ``tests/unit/contexts/messaging/domain/test_intent.py``
# asserts the alignment so this duplication does not drift silently.
INTENT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent_type": {
            "type": "string",
            "enum": [
                "create_case",
                "add_data_point",
                "revise_data_point",
                "unclear",
            ],
            "description": "the kind of action the message asks for",
        },
        "title": {
            "type": "string",
            "description": (
                "the case title — for create_case; empty string otherwise"
            ),
        },
        "case_reference": {
            "type": "string",
            "description": (
                "a natural-language reference to an existing case — for "
                "add_data_point; empty string otherwise"
            ),
        },
        "data_point_type": {
            "type": "string",
            "description": (
                "GOAL, STATUS, or METHODOLOGY_APPLICATION — for "
                "add_data_point; empty string otherwise"
            ),
        },
        "data_point_reference": {
            "type": "string",
            "description": (
                "a natural-language reference to an existing data point — "
                "for revise_data_point; empty string otherwise"
            ),
        },
        "value_text": {
            "type": "string",
            "description": (
                "the data point content — for add_data_point and "
                "revise_data_point; empty string otherwise"
            ),
        },
        "clarification": {
            "type": "string",
            "description": (
                "a question to ask the operator — for unclear; empty "
                "string otherwise"
            ),
        },
    },
    "required": [
        "intent_type",
        "title",
        "case_reference",
        "data_point_type",
        "data_point_reference",
        "value_text",
        "clarification",
    ],
    "additionalProperties": False,
}


def build_extraction_prompt(message: str) -> str:
    """Build the structured-output prompt for intent extraction.

    The cell's ``_extract_intent`` and the intent-classification
    evaluation runner both call this function so the prompt the
    model sees is identical across production and evaluation.
    """
    return f'{EXTRACTION_PREAMBLE}\n\nThe operator sent: "{message}"'


__all__ = [
    "EXTRACTION_PREAMBLE",
    "INTENT_EXTRACTION_SCHEMA",
    "build_extraction_prompt",
]
