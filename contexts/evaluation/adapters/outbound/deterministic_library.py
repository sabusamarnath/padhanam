"""Bounded library of deterministic applier functions (D53).

Per D53, deterministic applier primitives live in code (this module)
rather than as data, because the deterministic applier set is small
and stable; new entries are code changes. Prompt appliers and the
human-applier-mode are data records, governed by D53's authorship-and-
versioning model.

Each entry maps a deterministic_function_name (the value stored in
``appliers.deterministic_function_name`` at the schema layer) to the
callable that implements it. Functions take the interaction, the
actual output, and the criterion, and return the automated_score
string interpreted per the criterion's ``levels`` per D55.

S16 ships exactly one entry: ``exact_match``. S17 extends the registry
(regex_match, json_validate, embedding_cosine, etc.); reflection
prompt 3 in the S16 session log records the design intent so future
additions extend the same shape rather than improvising parallel
patterns.
"""

from __future__ import annotations

from typing import Callable

from contexts.evaluation.domain.interaction import Interaction
from contexts.evaluation.domain.scoring_sheet import Criterion


DeterministicFunction = Callable[..., str]


def exact_match(
    *,
    interaction: Interaction,
    output: str,
    criterion: Criterion,
) -> str:
    """Compare ``output`` to ``interaction.expected_output['value']``.

    Returns ``"pass"`` if the actual output exactly equals the
    expected output value, else ``"fail"``. The criterion is expected
    to declare ``levels`` containing ``pass``/``fail`` labels; the
    function does not consult ``criterion.levels`` directly because
    ``exact_match`` is a binary primitive with fixed labels — criterion
    levels exist to give them human-readable definitions, not to
    parameterise the function.
    """
    if interaction.expected_output is None:
        raise ValueError(
            "exact_match applier requires interaction.expected_output to be set"
        )
    expected = interaction.expected_output.get("value")
    if expected is None:
        raise ValueError(
            "exact_match applier requires expected_output['value'] to be set"
        )
    return "pass" if output == expected else "fail"


REGISTRY: dict[str, DeterministicFunction] = {
    "exact_match": exact_match,
}
