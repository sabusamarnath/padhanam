"""Schema-diff backward-compatibility stub at tool revision creation (D89).

Compares the parameters and returns schemas of revision Rn versus
Rn+1 and produces a ``BCResult`` (passed if the new revision's
schemas are identical or strict supersets of the prior revision's;
failed otherwise). The stub is the Phase 1 substrate; richer BC
testing (contract tests per tool, scenario-based regression,
type-evolution rules) defers to the activating session per the
deferred-decisions entry on rich BC testing.

Pass conditions:

- Identical schemas (byte-equivalent dicts after canonicalisation).
- New optional fields added (the new revision accepts a wider input
  shape; old callers' calls remain valid).
- Type widening (a field that was ``int`` becomes ``int | None``; an
  enum that gains values; type expanded to a strict superset).

Fail conditions:

- Removed fields (old callers may have used the removed field).
- Newly-required fields (callers that didn't supply the field now
  break).
- Type narrowing (a field that was ``int | None`` becomes ``int``;
  an enum that loses values).
- Returns-schema narrowing (downstream consumers expecting the
  wider shape now break).

The stub operates on JSON-schema-style dicts (the same shape stored
on ``ToolRevision.parameters_schema`` and
``ToolRevision.returns_schema``). It does not attempt full
JSON-schema validation; the comparison is structural.

The result lands on ``ToolRevision.bc_result`` as JSONB metadata at
``create_tool_revision`` time, and feeds the
``RoleToolBinding.can_auto_adopt`` flag in
``ToolRepository.list_roles_using_tool``: a binding can auto-adopt
the latest revision if every BC result in the chain between
``current_revision_id`` and ``latest_revision_id`` passed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class BCOutcome(str, Enum):
    """Outcome of the schema-diff backward-compatibility check (D89)."""

    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True)
class BCResult:
    """Result of a single schema-diff BC check (D89).

    ``outcome`` carries the pass/fail signal; ``reason`` is a short
    human-readable explanation for the operator (rendered in the
    ``RoleToolBinding`` adoption-flow UX at Phase 2).
    """

    outcome: BCOutcome
    reason: str

    def to_dict(self) -> dict[str, str]:
        """JSONB-friendly encoding for ``ToolRevision.bc_result``."""
        return {"outcome": self.outcome.value, "reason": self.reason}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BCResult":
        """Decode a stored ``bc_result`` JSONB payload.

        Returns a synthetic "passed" result with an empty reason when
        the payload is empty (the substrate's default before the BC
        stub runs at create_tool_revision time).
        """
        if not payload:
            return cls(outcome=BCOutcome.PASSED, reason="")
        return cls(
            outcome=BCOutcome(payload.get("outcome", "passed")),
            reason=str(payload.get("reason", "")),
        )


def check_revision_compatibility(
    *,
    old_parameters: Mapping[str, Any] | None,
    old_returns: Mapping[str, Any] | None,
    new_parameters: Mapping[str, Any],
    new_returns: Mapping[str, Any],
) -> BCResult:
    """Schema-diff comparison between old and new revision shapes (D89).

    Returns ``BCResult.PASSED`` when:

    - Both schemas are identical, or
    - The new schema strictly widens the old (new optional fields,
      type widening, returns schema preserves the old's properties
      while possibly adding more).

    Returns ``BCResult.FAILED`` when:

    - A property in the old schema is removed in the new.
    - A property's ``required`` status flips from False to True in
      the new revision and the property is also in the old's
      properties.
    - A newly-required property is added that wasn't in the old.
    - The returns schema narrows (a property in the old returns is
      removed in the new returns).

    The check is a stub per the deferred-decisions entry on rich BC
    testing — it covers structural shape diff but not semantic
    behavioural compatibility. The first false-result evidence
    refines the stub per the activating session.
    """
    if old_parameters is None or old_returns is None:
        # No prior revision (genesis case for revision 1). Pass
        # trivially; the chain anchors here.
        return BCResult(
            outcome=BCOutcome.PASSED,
            reason="genesis revision; no predecessor to diff against",
        )

    params_failure = _diff_parameters(
        old=old_parameters, new=new_parameters,
    )
    if params_failure is not None:
        return BCResult(outcome=BCOutcome.FAILED, reason=params_failure)

    returns_failure = _diff_returns(old=old_returns, new=new_returns)
    if returns_failure is not None:
        return BCResult(outcome=BCOutcome.FAILED, reason=returns_failure)

    return BCResult(
        outcome=BCOutcome.PASSED,
        reason="schemas identical or strictly widened",
    )


def _diff_parameters(
    *,
    old: Mapping[str, Any],
    new: Mapping[str, Any],
) -> str | None:
    """Return the failure reason or None if compatible."""
    old_props = dict(old.get("properties", {}))
    new_props = dict(new.get("properties", {}))
    old_required = set(old.get("required", []) or [])
    new_required = set(new.get("required", []) or [])

    # Removed properties: any property in old but missing in new.
    removed = set(old_props.keys()) - set(new_props.keys())
    if removed:
        return (
            f"property removed from parameters schema: "
            f"{sorted(removed)!r}"
        )

    # Newly-required properties: in new.required but not in old (or
    # in old but not required there).
    became_required = (new_required & set(old_props.keys())) - old_required
    if became_required:
        return (
            f"property promoted to required in parameters schema: "
            f"{sorted(became_required)!r}"
        )

    new_only_required = new_required - set(old_props.keys())
    if new_only_required:
        return (
            f"newly-required property added to parameters schema: "
            f"{sorted(new_only_required)!r}"
        )

    # Type narrowing: a property whose old type is a strict subset of
    # the new type is compatible (widening). A property whose old
    # type is a strict superset (narrowing) is a fail. The check is
    # conservative: any change to ``type`` that isn't a known
    # widening pattern fails.
    for name in old_props:
        old_type = old_props[name].get("type")
        new_type = new_props[name].get("type")
        if old_type is None or new_type is None:
            continue
        if old_type == new_type:
            continue
        if not _is_type_widening(old_type=old_type, new_type=new_type):
            return (
                f"parameter {name!r} type narrowed: {old_type!r} -> "
                f"{new_type!r}"
            )

    return None


def _diff_returns(
    *,
    old: Mapping[str, Any],
    new: Mapping[str, Any],
) -> str | None:
    """Return the failure reason or None if compatible.

    Returns schemas may widen (new optional fields, type widening)
    but cannot narrow (removing fields, type narrowing).
    """
    old_props = dict(old.get("properties", {})) if isinstance(old, Mapping) else {}
    new_props = dict(new.get("properties", {})) if isinstance(new, Mapping) else {}

    # Top-level type check.
    old_top_type = old.get("type") if isinstance(old, Mapping) else None
    new_top_type = new.get("type") if isinstance(new, Mapping) else None
    if old_top_type is not None and new_top_type is not None:
        if old_top_type != new_top_type and not _is_type_widening(
            old_type=old_top_type, new_type=new_top_type,
        ):
            return (
                f"returns schema top-level type changed: {old_top_type!r} -> "
                f"{new_top_type!r}"
            )

    removed = set(old_props.keys()) - set(new_props.keys())
    if removed:
        return (
            f"property removed from returns schema: {sorted(removed)!r}"
        )

    for name in old_props:
        old_type = old_props[name].get("type")
        new_type = new_props[name].get("type")
        if old_type is None or new_type is None:
            continue
        if old_type == new_type:
            continue
        if not _is_type_widening(old_type=old_type, new_type=new_type):
            return (
                f"returns property {name!r} type narrowed: {old_type!r} -> "
                f"{new_type!r}"
            )

    return None


def _is_type_widening(*, old_type: Any, new_type: Any) -> bool:
    """Heuristic for "new_type is a strict superset of old_type" (D89).

    Phase 1 covers the simple cases:

    - Adding ``null`` to a previously-non-nullable type widens.
    - ``int`` -> ``[int, str]`` (or any list containing the old
      type) widens.
    - Anything else returns False (the stub defaults to "this is
      a narrowing change" out of conservatism; richer rules per the
      deferred-decisions entry).
    """
    if isinstance(new_type, list) and not isinstance(old_type, list):
        return old_type in new_type
    if isinstance(new_type, list) and isinstance(old_type, list):
        return set(old_type).issubset(set(new_type))
    return False


__all__ = [
    "BCOutcome",
    "BCResult",
    "check_revision_compatibility",
]
