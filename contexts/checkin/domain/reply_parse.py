"""The check-in reply parse — prompt, schema, and the pure response mapping (D192, D184, S97b).

The load-bearing semantic of the three-state design lives here: an unmentioned
lever must be **absent** from the result (silence is not a miss), a goal-level
reply ("did my meds") must expand to all of a goal's levers, and only an
explicit negative writes ``reported_didnt``. The prompt carries those rules and
groups the levers by goal so the model can expand goal-level replies; the pure
``map_parsed_outcomes`` turns the model's index-keyed answer back into
per-lever outcomes, defensively dropping anything out of range and never
inventing an entry for a lever the model did not return.

Framework-free per D16 — stdlib only. The LLM call itself lives in an adapter
behind the StructuredOutputPort.
"""

from __future__ import annotations

from typing import Any

from contexts.checkin.domain.lever import EligibleLever
from contexts.checkin.domain.outcome import CheckinState, ParsedLeverOutcome

# JSON Schema the structured-output port constrains the model to. Lever is the
# 1-based index from the prompt listing; state is the two reportable values
# (silence is expressed by *omission*, never a third enum value).
PARSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "outcomes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lever": {
                        "type": "integer",
                        "description": "the lever number from the list",
                    },
                    "state": {
                        "type": "string",
                        "enum": ["did", "reported_didnt"],
                    },
                },
                "required": ["lever", "state"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["outcomes"],
    "additionalProperties": False,
}


def build_parse_prompt(
    *, reply_text: str, levers: tuple[EligibleLever, ...]
) -> str:
    """Build the parse prompt — levers grouped by goal, with the silence rule."""
    lines: list[str] = []
    last_goal: str | None = None
    for index, lever in enumerate(levers, start=1):
        if lever.goal_name != last_goal:
            lines.append(f'Goal "{lever.goal_name}":')
            last_goal = lever.goal_name
        lines.append(f"  {index}. {lever.name}")
    listing = "\n".join(lines)
    return (
        "You read a person's daily check-in reply about which of their "
        "habits they did today, and map it to the numbered levers below.\n\n"
        f"Levers (grouped by goal):\n{listing}\n\n"
        f'The person replied: "{reply_text}"\n\n'
        "For each lever the reply CLEARLY speaks to, output an entry "
        "{lever: <number>, state: \"did\" or \"reported_didnt\"}.\n"
        "Rules:\n"
        "- A goal-level mention (e.g. \"did my meds\", \"did health\") means "
        "ALL levers under that goal — output one entry per lever, state "
        "\"did\".\n"
        "- Use \"reported_didnt\" ONLY when the reply explicitly says a lever "
        "was not done / missed / skipped.\n"
        "- If a lever is NOT mentioned at all, OMIT it entirely. Do not output "
        "an entry for it. Silence is not a miss.\n"
        "- Output only levers from the list above, by their number."
    )


def map_parsed_outcomes(
    value: dict[str, Any], levers: tuple[EligibleLever, ...]
) -> tuple[ParsedLeverOutcome, ...]:
    """Map the model's index-keyed answer to per-lever outcomes (pure).

    Out-of-range indices are dropped; a repeated lever keeps the last state;
    a lever absent from ``value`` is absent from the result (silence)."""
    raw = value.get("outcomes", []) if isinstance(value, dict) else []
    by_commitment: dict = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        index = entry.get("lever")
        state_raw = entry.get("state")
        if not isinstance(index, int) or not (1 <= index <= len(levers)):
            continue
        try:
            state = CheckinState(str(state_raw))
        except ValueError:
            continue
        lever = levers[index - 1]
        by_commitment[lever.commitment_id] = ParsedLeverOutcome(
            commitment_id=lever.commitment_id, state=state
        )
    return tuple(by_commitment.values())


__all__ = ["PARSE_SCHEMA", "build_parse_prompt", "map_parsed_outcomes"]
