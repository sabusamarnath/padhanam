"""EffectiveConstraintBundle — the fully resolved invocation surface (D88, D87).

The bundle is the output of ``compose_effective_constraint_bundle`` at
``contexts/agent/application/composition.py``: the role's constraint
bundle composed with the methodology revision's per-role overrides
per D87's three-mode space (augment, replace, tighten). It flows
through ``invoke_agent`` into ``AgentInvocationContext`` and on to the
``AgentExecutor`` adapter.

Domain code is framework-free per D16 — stdlib dataclasses, no
Pydantic, no SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from shared_kernel import ToolAllowlistEntry


@dataclass(frozen=True)
class EffectiveConstraintBundle:
    """Composed view of a role plus optional methodology overrides (D87, D88).

    Field shapes match the role aggregate's constraint bundle (per D86).
    The composition resolver guarantees:

    - ``system_prompt`` reflects D87's mode for ``system_prompt``
      (augment concatenates role base with two newlines plus methodology
      override value; replace substitutes).
    - ``tool_allowlist``, ``filter_tree``, ``top_k``, ``min_score``
      reflect tighten semantics (intersection for list-shaped fields;
      more-restrictive for numeric fields) when methodology overrides
      apply; otherwise carry role base verbatim.
    - ``retrieval_strategy``, ``model_selection`` reflect replace
      semantics when overridden; otherwise carry role base verbatim.

    Inadmissible (field, mode) pairs cannot reach this point because
    they are rejected at methodology write time per D87's
    ``validate_override``.
    """

    system_prompt: str
    tool_allowlist: tuple[ToolAllowlistEntry, ...]
    retrieval_strategy: Mapping[str, Any]
    filter_tree: Mapping[str, Any]
    top_k: int
    min_score: Decimal
    model_selection: str
