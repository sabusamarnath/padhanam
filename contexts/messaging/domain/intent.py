"""Intent value objects — the manual entry cell's parsed intents (D129, S46).

The manual entry cell (the first ConversationFlow implementer, S46)
extracts a typed intent from an inbound WhatsApp message via
structured output. This module carries the discriminated intent
union, the JSON Schema the structured-output call conforms to, and
the ``parse_intent`` mapping from the LLM's parsed object to the
typed variant.

Four variants at Phase 2-A scope: ``CreateCaseIntent``,
``AddDataPointIntent``, ``ReviseDataPointIntent``, and
``UnclearIntent`` (the safe fallback when the message does not map
cleanly). ``DropCaseIntent`` and ``QueryStateIntent`` defer to the
second-instance trigger per the build-at-second-instance discipline.

``AddDataPointIntent.case_reference`` and
``ReviseDataPointIntent.data_point_reference`` are natural-language
references — Path B target identifier resolution. The cell resolves
them against portfolio state (``resolve_target``) before driving a
write; this module owns only the parsed shape, not the resolution.

Domain code is framework-free per D16 — stdlib plus shared_kernel.
This module imports no ``contexts/`` type: ``data_point_type`` is a
plain ``str`` validated against the known set rather than the
portfolio ``DataPointType`` enum (cross-context domain independence).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# The portfolio DataPointType values an AddDataPointIntent may name.
# Kept as a plain tuple rather than importing the portfolio enum —
# the messaging domain layer is independent of the portfolio domain.
DATA_POINT_TYPES: tuple[str, ...] = (
    "GOAL",
    "STATUS",
    "METHODOLOGY_APPLICATION",
)


class IntentType(StrEnum):
    """The structured-output discriminant for an extracted intent."""

    CREATE_CASE = "create_case"
    ADD_DATA_POINT = "add_data_point"
    REVISE_DATA_POINT = "revise_data_point"
    UNCLEAR = "unclear"


@dataclass(frozen=True)
class CreateCaseIntent:
    """The operator wants a new Case created with ``title``."""

    title: str

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("CreateCaseIntent.title must be non-empty")


@dataclass(frozen=True)
class AddDataPointIntent:
    """The operator wants a DataPoint added to an existing Case.

    ``case_reference`` is a natural-language reference (Path B); the
    cell resolves it against portfolio state. ``data_point_type`` is
    one of ``DATA_POINT_TYPES``. ``value_text`` is the data point's
    content as the operator phrased it.
    """

    case_reference: str
    data_point_type: str
    value_text: str

    def __post_init__(self) -> None:
        if not self.case_reference or not self.case_reference.strip():
            raise ValueError(
                "AddDataPointIntent.case_reference must be non-empty"
            )
        if self.data_point_type not in DATA_POINT_TYPES:
            raise ValueError(
                "AddDataPointIntent.data_point_type must be one of "
                f"{DATA_POINT_TYPES}; got {self.data_point_type!r}"
            )
        if not self.value_text or not self.value_text.strip():
            raise ValueError(
                "AddDataPointIntent.value_text must be non-empty"
            )


@dataclass(frozen=True)
class ReviseDataPointIntent:
    """The operator wants an existing DataPoint revised.

    ``data_point_reference`` is a natural-language reference (Path B);
    the cell resolves it against portfolio state. ``value_text`` is
    the revised content.
    """

    data_point_reference: str
    value_text: str

    def __post_init__(self) -> None:
        if (
            not self.data_point_reference
            or not self.data_point_reference.strip()
        ):
            raise ValueError(
                "ReviseDataPointIntent.data_point_reference must be non-empty"
            )
        if not self.value_text or not self.value_text.strip():
            raise ValueError(
                "ReviseDataPointIntent.value_text must be non-empty"
            )


@dataclass(frozen=True)
class UnclearIntent:
    """The message did not map cleanly to an actionable intent.

    ``clarification`` is the question the cell asks the operator. It
    is the safe fallback — ``parse_intent`` coerces to it when a
    typed variant cannot be constructed from the extracted fields.
    """

    clarification: str

    def __post_init__(self) -> None:
        if not self.clarification or not self.clarification.strip():
            raise ValueError("UnclearIntent.clarification must be non-empty")


Intent = (
    CreateCaseIntent
    | AddDataPointIntent
    | ReviseDataPointIntent
    | UnclearIntent
)

_DEFAULT_CLARIFICATION = (
    "I could not tell what you would like me to do. You can ask me to "
    "create a case, add a goal or status to a case, or revise an "
    "existing data point."
)

# JSON Schema (strict-mode) the structured-output intent-extraction
# call conforms to. A flat object: every field is required and
# non-applicable fields come back as empty strings, which strict mode
# tolerates cleanly. ``parse_intent`` reads ``intent_type`` and pulls
# the fields relevant to that variant.
INTENT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent_type": {
            "type": "string",
            "enum": [t.value for t in IntentType],
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


def parse_intent(raw: dict[str, Any]) -> Intent:
    """Map a structured-output extraction object to a typed Intent.

    Reads ``intent_type`` and constructs the matching variant from
    the fields relevant to it. When the chosen variant cannot be
    constructed — a missing or empty required field, an unknown
    ``intent_type``, an out-of-set ``data_point_type`` — the result
    coerces to ``UnclearIntent`` rather than raising, so a degraded
    extraction surfaces as a clarification rather than an error.
    """
    intent_type = str(raw.get("intent_type", "")).strip()
    clarification = str(raw.get("clarification", "")).strip()
    try:
        if intent_type == IntentType.CREATE_CASE:
            return CreateCaseIntent(title=str(raw.get("title", "")).strip())
        if intent_type == IntentType.ADD_DATA_POINT:
            return AddDataPointIntent(
                case_reference=str(raw.get("case_reference", "")).strip(),
                data_point_type=str(raw.get("data_point_type", "")).strip(),
                value_text=str(raw.get("value_text", "")).strip(),
            )
        if intent_type == IntentType.REVISE_DATA_POINT:
            return ReviseDataPointIntent(
                data_point_reference=str(
                    raw.get("data_point_reference", "")
                ).strip(),
                value_text=str(raw.get("value_text", "")).strip(),
            )
        if intent_type == IntentType.UNCLEAR:
            return UnclearIntent(
                clarification=clarification or _DEFAULT_CLARIFICATION
            )
    except ValueError:
        # A typed variant could not be constructed from the extracted
        # fields — fall through to the UnclearIntent fallback.
        pass
    return UnclearIntent(clarification=clarification or _DEFAULT_CLARIFICATION)


__all__ = [
    "AddDataPointIntent",
    "CreateCaseIntent",
    "DATA_POINT_TYPES",
    "INTENT_EXTRACTION_SCHEMA",
    "Intent",
    "IntentType",
    "ReviseDataPointIntent",
    "UnclearIntent",
    "parse_intent",
]
