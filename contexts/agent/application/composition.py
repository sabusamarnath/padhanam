"""Effective constraint bundle composition (D87 resolver, D88).

Implements the D87 override-mode resolver semantics deferred from
S26b. The composition function consumes a role's base constraint
bundle (from ``RoleView``) plus a methodology revision's per-role
overrides (the structured ``{field: {"mode": <str>, "value": <any>}}``
shape that lands on ``RoleRef.overrides`` per D87) and produces an
``EffectiveConstraintBundle`` carrying the field-by-field resolved
values.

D87 mode-by-field algorithm:

- ``system_prompt`` augment: ``role_base + "\\n\\n" + methodology_value``.
  The two-newline separator per D88 is the simplest viable shape;
  richer framing (named sections, XML wrapping) deferred until LLM
  behaviour evidence demands.
- ``system_prompt`` replace: methodology value substitutes role base.
- ``tool_allowlist`` tighten: intersection of role-base list and
  methodology override list, preserving role-base ordering.
- ``tool_allowlist`` replace: methodology list substitutes.
- ``retrieval_strategy`` replace (only admissible mode per D87):
  methodology value substitutes.
- ``filter_tree`` tighten: AND-merge of role base and methodology
  trees. If either side is empty, the non-empty side wins; if both
  are non-empty, wrap as ``{"op": "and", "operands": [base, override]}``.
- ``filter_tree`` replace: methodology value substitutes.
- ``top_k`` tighten: ``min(role_base, methodology_value)`` — methodology
  may only decrease the cap.
- ``top_k`` replace: methodology value substitutes.
- ``min_score`` tighten: ``max(role_base, methodology_value)`` —
  methodology may only raise the floor.
- ``min_score`` replace: methodology value substitutes.
- ``model_selection`` replace (only admissible mode per D87):
  methodology value substitutes.

Methodology absent (empty overrides dict) yields the role base
unchanged across every field.

The resolver trusts D87's substrate-side validation: inadmissible
(field, mode) pairs cannot reach this point because they are
rejected at methodology write time via
``contexts/methodology/domain/overrides.py:validate_override``. The
resolver still raises ``CompositionError`` on an internally
inconsistent override shape (missing ``mode`` or ``value`` keys, or
mode strings outside the D87 mode space) as defence-in-depth.

This module is application-layer; per D17 it imports from the agent
context's domain (``EffectiveConstraintBundle``) and application
ports (``RoleView``) but never reaches into methodology or ingestion.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from contexts.agent.application.ports import RoleView
from contexts.agent.domain.effective_bundle import EffectiveConstraintBundle


SYSTEM_PROMPT_AUGMENT_SEPARATOR = "\n\n"


class CompositionError(ValueError):
    """Raised when an override payload reaching the resolver is malformed.

    The substrate validates writes per D87, so reaching this exception
    indicates either a substrate bypass (override authored without going
    through ``project_overrides``) or a bug in the methodology repository.
    The resolver still defends with explicit error rather than implicit
    fallback.
    """


def compose_effective_constraint_bundle(
    *,
    role: RoleView,
    methodology_overrides: Mapping[str, Mapping[str, Any]],
) -> EffectiveConstraintBundle:
    """Compose role base plus methodology per-role overrides (D87, D88).

    When ``methodology_overrides`` is empty (no methodology lineage,
    or the methodology has no override entry for this role), the
    returned bundle equals the role base verbatim.

    Each non-empty override entry pairs a field name with a
    ``{"mode": <str>, "value": <any>}`` mapping. The resolver
    dispatches per (field, mode) and produces the effective value.
    """
    system_prompt = _resolve_text_field(
        field="system_prompt",
        base=role.system_prompt,
        overrides=methodology_overrides,
        augment_separator=SYSTEM_PROMPT_AUGMENT_SEPARATOR,
    )
    tool_allowlist = _resolve_tool_allowlist(
        base=role.tool_allowlist,
        overrides=methodology_overrides,
    )
    retrieval_strategy = _resolve_replace_only_mapping(
        field="retrieval_strategy",
        base=role.retrieval_strategy,
        overrides=methodology_overrides,
    )
    filter_tree = _resolve_filter_tree(
        base=role.filter_tree,
        overrides=methodology_overrides,
    )
    top_k = _resolve_numeric_tighten(
        field="top_k",
        base=role.top_k,
        overrides=methodology_overrides,
        tighten=_min_int,
    )
    min_score = _resolve_numeric_tighten(
        field="min_score",
        base=role.min_score,
        overrides=methodology_overrides,
        tighten=_max_decimal,
    )
    model_selection = _resolve_replace_only_string(
        field="model_selection",
        base=role.model_selection,
        overrides=methodology_overrides,
    )
    return EffectiveConstraintBundle(
        system_prompt=system_prompt,
        tool_allowlist=tool_allowlist,
        retrieval_strategy=retrieval_strategy,
        filter_tree=filter_tree,
        top_k=top_k,
        min_score=min_score,
        model_selection=model_selection,
    )


def _entry(
    overrides: Mapping[str, Mapping[str, Any]],
    field: str,
) -> tuple[str, Any] | None:
    """Pull a single override entry, validate shape, return (mode, value).

    Returns None when the field has no override entry; raises
    CompositionError when the entry shape is malformed.
    """
    entry = overrides.get(field)
    if entry is None:
        return None
    if "mode" not in entry or "value" not in entry:
        raise CompositionError(
            f"override entry for field {field!r} is malformed: "
            f"expected keys {{'mode', 'value'}}, got {sorted(entry.keys())!r}"
        )
    mode = str(entry["mode"])
    return mode, entry["value"]


def _resolve_text_field(
    *,
    field: str,
    base: str,
    overrides: Mapping[str, Mapping[str, Any]],
    augment_separator: str,
) -> str:
    """Resolve a free-text soft field (augment or replace per D87)."""
    pair = _entry(overrides, field)
    if pair is None:
        return base
    mode, value = pair
    if mode == "augment":
        return f"{base}{augment_separator}{value}"
    if mode == "replace":
        return str(value)
    raise CompositionError(
        f"override mode {mode!r} unexpected for field {field!r}; "
        f"D87 admissible modes for free-text fields are 'augment' or 'replace'"
    )


def _resolve_tool_allowlist(
    *,
    base: tuple[str, ...],
    overrides: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    """Resolve tool_allowlist (tighten via intersection, or replace).

    Tighten preserves role-base ordering so the effective list is
    deterministic and the byte-level shape is stable across invocations.
    """
    pair = _entry(overrides, "tool_allowlist")
    if pair is None:
        return base
    mode, value = pair
    incoming = tuple(str(t) for t in value)
    if mode == "tighten":
        incoming_set = set(incoming)
        return tuple(t for t in base if t in incoming_set)
    if mode == "replace":
        return incoming
    raise CompositionError(
        f"override mode {mode!r} unexpected for field 'tool_allowlist'; "
        f"D87 admissible modes are 'tighten' or 'replace'"
    )


def _resolve_replace_only_mapping(
    *,
    field: str,
    base: Mapping[str, Any],
    overrides: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Resolve a field whose only admissible mode is replace (D87)."""
    pair = _entry(overrides, field)
    if pair is None:
        return base
    mode, value = pair
    if mode == "replace":
        return dict(value)
    raise CompositionError(
        f"override mode {mode!r} unexpected for field {field!r}; "
        f"D87 admits only 'replace' for this field"
    )


def _resolve_replace_only_string(
    *,
    field: str,
    base: str,
    overrides: Mapping[str, Mapping[str, Any]],
) -> str:
    pair = _entry(overrides, field)
    if pair is None:
        return base
    mode, value = pair
    if mode == "replace":
        return str(value)
    raise CompositionError(
        f"override mode {mode!r} unexpected for field {field!r}; "
        f"D87 admits only 'replace' for this field"
    )


def _resolve_filter_tree(
    *,
    base: Mapping[str, Any],
    overrides: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Resolve filter_tree (tighten via AND-merge, or replace)."""
    pair = _entry(overrides, "filter_tree")
    if pair is None:
        return base
    mode, value = pair
    incoming = dict(value)
    if mode == "tighten":
        if not base:
            return incoming
        if not incoming:
            return dict(base)
        return {
            "op": "and",
            "operands": [dict(base), incoming],
        }
    if mode == "replace":
        return incoming
    raise CompositionError(
        f"override mode {mode!r} unexpected for field 'filter_tree'; "
        f"D87 admissible modes are 'tighten' or 'replace'"
    )


def _resolve_numeric_tighten(
    *,
    field: str,
    base: Any,
    overrides: Mapping[str, Mapping[str, Any]],
    tighten,
) -> Any:
    """Resolve a numeric field (tighten via min/max, or replace).

    ``tighten`` is the more-restrictive selector: ``min`` for caps
    (top_k where overriding lowers the cap) or ``max`` for floors
    (min_score where overriding raises the floor).
    """
    pair = _entry(overrides, field)
    if pair is None:
        return base
    mode, value = pair
    if mode == "tighten":
        return tighten(base, value)
    if mode == "replace":
        return value
    raise CompositionError(
        f"override mode {mode!r} unexpected for field {field!r}; "
        f"D87 admissible modes are 'tighten' or 'replace'"
    )


def _min_int(a: int, b: Any) -> int:
    return min(int(a), int(b))


def _max_decimal(a: Decimal, b: Any) -> Decimal:
    incoming = b if isinstance(b, Decimal) else Decimal(str(b))
    return max(a, incoming)
