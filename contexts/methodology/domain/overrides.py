"""Override-mode space and per-field admissibility (D87).

S26b adds D87 as a refinement of D86's sub-commitments (b) and (e).
D86 specified "hard fields tighten only; soft fields replace" as the
binding-mode taxonomy. The McKinsey 7-Step brief's first authoring
evidence at S26b surfaced that "system_prompt addition" semantics
read as augment, not replace; D87 admits a richer three-mode space
(augment, replace, tighten) plus per-field default modes plus
structured on-disk overrides shape.

The substrate enforces D87 at three layers:

- ``RoleRef.overrides`` carries ``dict[str, dict[str, Any]]`` where
  each entry is the canonical ``{"mode": <str>, "value": <any>}``
  shape. The dataclass at ``contexts/methodology/domain/methodology.py``
  enforces the type.
- This module exports ``DEFAULT_MODE_BY_FIELD`` (the per-field
  default-mode table from D87) and ``validate_override`` (the
  admissibility predicate). The methodology config parser at
  ``apps/cli/_methodology.py`` invokes both at parse time.
- The canonical-JSON encoder at the methodology hash payload helper
  treats empty overrides as ``null`` for byte-stability with the
  pre-D87 LVT methodology authored at S25; see
  ``application/use_cases.py:_role_ref_to_canonical`` for the
  rationale.

Resolver semantics (how augment concatenates, how tighten intersects,
how replace substitutes at agent invocation time) defer to S27b's
agent runtime per D87. S26b commits storage plus validation only.

Domain code is framework-free per D16 — stdlib only, no Pydantic, no
SQLAlchemy.
"""

from __future__ import annotations

from typing import Any, Mapping

MODE_AUGMENT = "augment"
MODE_REPLACE = "replace"
MODE_TIGHTEN = "tighten"

ALL_MODES = frozenset({MODE_AUGMENT, MODE_REPLACE, MODE_TIGHTEN})

# D87 per-field default-mode table. Each role-bundle field carries
# exactly one default mode; an author writing a flat value at the
# methodology config parser layer expands to the structured form
# using this table. Authors writing the structured form override the
# default.
DEFAULT_MODE_BY_FIELD: dict[str, str] = {
    "system_prompt": MODE_AUGMENT,
    "tool_allowlist": MODE_TIGHTEN,
    "source_filter": MODE_TIGHTEN,
    "retrieval_strategy": MODE_REPLACE,
    "filter_tree": MODE_TIGHTEN,
    "top_k": MODE_TIGHTEN,
    "min_score": MODE_TIGHTEN,
    "model_selection": MODE_REPLACE,
    "cost_ceiling": MODE_TIGHTEN,
}

# D87 admissibility map. Soft free-text fields admit augment or
# replace; hard fields admit tighten or replace; structurally
# meaningful replacement on hard fields is allowed at Phase 1 because
# the meaningful-replacement predicate is the field-shape predicate
# rather than a per-field allowlist. The resolver at S27b honours
# the (field, mode) pair selected at methodology write time.
_ADMISSIBLE_MODES_BY_FIELD: dict[str, frozenset[str]] = {
    "system_prompt": frozenset({MODE_AUGMENT, MODE_REPLACE}),
    "tool_allowlist": frozenset({MODE_TIGHTEN, MODE_REPLACE}),
    "source_filter": frozenset({MODE_TIGHTEN, MODE_REPLACE}),
    "retrieval_strategy": frozenset({MODE_REPLACE}),
    "filter_tree": frozenset({MODE_TIGHTEN, MODE_REPLACE}),
    "top_k": frozenset({MODE_TIGHTEN, MODE_REPLACE}),
    "min_score": frozenset({MODE_TIGHTEN, MODE_REPLACE}),
    "model_selection": frozenset({MODE_REPLACE}),
    "cost_ceiling": frozenset({MODE_TIGHTEN, MODE_REPLACE}),
}


class OverrideValidationError(ValueError):
    """Raised when an override payload violates D87's admissibility rules."""


def validate_override(field: str, mode: str) -> None:
    """Validate that ``mode`` is admissible for ``field`` per D87.

    Raises ``OverrideValidationError`` on inadmissible pairs and on
    unknown fields or unknown modes. The substrate uses this predicate
    at methodology write time so an authoring path cannot persist an
    inadmissible override.
    """
    if mode not in ALL_MODES:
        raise OverrideValidationError(
            f"unknown override mode {mode!r}; valid modes are "
            f"{sorted(ALL_MODES)!r}"
        )
    admissible = _ADMISSIBLE_MODES_BY_FIELD.get(field)
    if admissible is None:
        raise OverrideValidationError(
            f"override field {field!r} is not part of the role constraint "
            f"bundle; valid fields are {sorted(DEFAULT_MODE_BY_FIELD)!r}"
        )
    if mode not in admissible:
        raise OverrideValidationError(
            f"override mode {mode!r} is inadmissible for field {field!r}; "
            f"admissible modes are {sorted(admissible)!r}"
        )


def project_overrides(
    raw: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Project an authoring-shape overrides mapping to the structured form (D87).

    Accepts three shapes per entry:

    - A flat value (any non-mapping or a mapping without a ``mode``
      key): expanded to ``{"mode": DEFAULT_MODE_BY_FIELD[field], "value": <flat>}``.
    - A structured value matching ``{"mode": <str>, "value": <any>}``:
      passes through after validation. The mode is checked against
      D87's admissibility rules.
    - ``None`` or missing: omitted from the projection (empty override
      for that field).

    Returns the structured mapping the substrate persists on
    ``RoleRef.overrides``. Empty input (``None`` or empty mapping)
    projects to ``{}``.

    Raises ``OverrideValidationError`` on unknown fields and
    inadmissible (field, mode) pairs.
    """
    if raw is None:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for field, value in raw.items():
        if value is None:
            continue
        if (
            isinstance(value, Mapping)
            and "mode" in value
            and "value" in value
            and set(value.keys()) <= {"mode", "value"}
        ):
            mode = str(value["mode"])
            payload = value["value"]
        else:
            mode = DEFAULT_MODE_BY_FIELD.get(field)
            if mode is None:
                raise OverrideValidationError(
                    f"override field {field!r} is not part of the role "
                    f"constraint bundle; valid fields are "
                    f"{sorted(DEFAULT_MODE_BY_FIELD)!r}"
                )
            payload = value
        validate_override(field, mode)
        out[field] = {"mode": mode, "value": payload}
    return out
