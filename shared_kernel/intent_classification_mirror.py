"""Mirror-conversation intent prompt and schema (D137, P14, S52).

The mirror-conversation cell's intent-classification prompt and schema
live at shared_kernel/ so the production cell at
``contexts/mirror_conversation/application/cell.py`` and the D137
substrate evaluation runner consume the same primitive — the same
single-source-of-truth discipline ``shared_kernel/intent_classification.py``
established at S48b for the manual entry cell and
``shared_kernel/intent_classification_audit.py`` for audit-conversation.

Six concrete intents plus the unclear fallback, mirroring
``contexts/mirror_conversation/domain/intent.py``'s ``MirrorIntentType``.

The prompt accepts conversation-history context the cell renders into
the flattened ``role: text`` shape. Relative intents (DrillDownToChild,
ShowParent, ShowSiblings) reference the conversation's current focus
artefact extracted from the prior outbound's cell_payload column per
D141; the classifier reads the history to disambiguate "tell me about
revenue" as a relative drill-down within the current case versus a
fresh ShowDataPoint.

Per D16 shared_kernel is policed framework-free. Schema is a dict;
prompt builder is a pure function over strings.
"""

from __future__ import annotations

from typing import Any


MIRROR_INTENT_PREAMBLE: str = (
    "You extract a structured query intent from a busy professional's "
    "message to their assistant about their portfolio of work. Mirror-"
    "conversation answers 'what is the current state' queries — listing "
    "cases, showing case details, showing data points, and navigating "
    "the case hierarchy.\n\n"
    "Seven intent classes (six concrete plus one fallback). Three are "
    "ABSOLUTE — they reference an artefact by natural-language phrase:\n"
    "  show_case: 'show me the Q3 review', 'tell me about the Acme deal'.\n"
    "  list_cases: 'list my cases', 'what cases do I have?'.\n"
    "  show_data_point: 'show me the revenue data point on Q3', "
    "'what's the value of the latency goal?'.\n\n"
    "Three are RELATIVE — they depend on what the assistant just "
    "showed (the recent conversation context). Use the conversation "
    "history to disambiguate; if the user references something the "
    "prior assistant turn surfaced, classify relative:\n"
    "  drill_down_to_child: 'tell me about revenue' (after the "
    "assistant just showed a case containing a revenue data point); "
    "'what about latency?'; 'drill down to the second one'.\n"
    "  show_parent: 'show the parent', 'what case does this belong "
    "to?'.\n"
    "  show_siblings: 'what else is in this case?', 'siblings of this "
    "data point'.\n\n"
    "One is the fallback:\n"
    "  unclear_mirror: the message does not map cleanly to any of "
    "the above; populate the clarification field with a question "
    "asking the operator to specify.\n\n"
    "Fill only the fields relevant to the chosen intent; leave every "
    "other field as an empty string. Populate the confidence field "
    "with your self-reported confidence in the classification "
    "(0.0-1.0)."
)


MIRROR_INTENT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent_class": {
            "type": "string",
            "enum": [
                "show_case",
                "list_cases",
                "show_data_point",
                "drill_down_to_child",
                "show_parent",
                "show_siblings",
                "unclear_mirror",
            ],
            "description": "the kind of mirror query the message asks for",
        },
        "case_reference": {
            "type": "string",
            "description": (
                "a natural-language reference to a case — for "
                "show_case and optionally narrowing show_data_point; "
                "empty string otherwise"
            ),
        },
        "data_point_reference": {
            "type": "string",
            "description": (
                "a natural-language reference to a data point — for "
                "show_data_point; empty string otherwise"
            ),
        },
        "child_reference": {
            "type": "string",
            "description": (
                "the name of the child artefact within the current "
                "focus — for drill_down_to_child; empty string otherwise"
            ),
        },
        "confidence": {
            "type": "number",
            "description": (
                "self-reported confidence in the classification; "
                "0.0 to 1.0"
            ),
        },
        "clarification": {
            "type": "string",
            "description": (
                "a question to ask the operator — for unclear_mirror; "
                "empty string otherwise"
            ),
        },
    },
    "required": [
        "intent_class",
        "case_reference",
        "data_point_reference",
        "child_reference",
        "confidence",
        "clarification",
    ],
    "additionalProperties": False,
}


def build_mirror_extraction_prompt(message: str) -> str:
    """Build the structured-output prompt for mirror-conversation intent extraction.

    The cell's intent-extraction call and the D137 substrate evaluation
    runner both consume this builder so the prompt the model sees is
    identical across production and evaluation.
    """
    return f'{MIRROR_INTENT_PREAMBLE}\n\nThe operator sent: "{message}"'


__all__ = [
    "MIRROR_INTENT_EXTRACTION_SCHEMA",
    "MIRROR_INTENT_PREAMBLE",
    "build_mirror_extraction_prompt",
]
