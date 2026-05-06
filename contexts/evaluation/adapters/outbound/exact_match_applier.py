"""Polymorphic applier adapter implementing ApplierPort (D54).

Single adapter class dispatches on ``applier_config.applier_type``.
S16 ships the deterministic dispatch path only: the adapter resolves
``deterministic_function_name`` against the deterministic-library
registry and invokes the function. Prompt and human dispatch paths
raise ``NotImplementedError`` at S16; they land at S17 (prompt) and
P10/P11 (human-review UI) per D53. The class is named
``ExactMatchApplier`` because the registry currently holds only the
``exact_match`` deterministic function; the structural shape is
polymorphic-by-applier-type, and S17 either renames the file or adds
sibling adapters as the registry grows.

The adapter is stateless — no per-tenant configuration sits on
``self`` — so a single instance serves every tenant. Wiring (use case
construction at the inbound adapter or test) injects this instance as
the ``ApplierPort`` value.
"""

from __future__ import annotations

from contexts.evaluation.adapters.outbound.deterministic_library import REGISTRY
from contexts.evaluation.domain.applier import ApplierConfig, ApplierType
from contexts.evaluation.domain.interaction import Interaction
from contexts.evaluation.domain.scoring_sheet import Criterion


class ExactMatchApplier:
    """ApplierPort implementation. Dispatches on applier_type."""

    async def apply(
        self,
        *,
        interaction: Interaction,
        output: str,
        criterion: Criterion,
        applier_config: ApplierConfig,
    ) -> str | None:
        if applier_config.applier_type == ApplierType.DETERMINISTIC:
            return self._apply_deterministic(
                interaction=interaction,
                output=output,
                criterion=criterion,
                applier_config=applier_config,
            )
        if applier_config.applier_type == ApplierType.PROMPT:
            raise NotImplementedError(
                "prompt applier dispatch lands at S17 (LLM-as-judge); "
                "S16 ships only the deterministic path"
            )
        if applier_config.applier_type == ApplierType.HUMAN:
            raise NotImplementedError(
                "human applier mode is data-substrate-only at S16 per D53; "
                "no automated write path exists for human-score"
            )
        raise ValueError(
            f"unknown applier_type: {applier_config.applier_type!r}"
        )

    def _apply_deterministic(
        self,
        *,
        interaction: Interaction,
        output: str,
        criterion: Criterion,
        applier_config: ApplierConfig,
    ) -> str:
        # __post_init__ on ApplierConfig guarantees
        # deterministic_function_name is non-null when applier_type is
        # DETERMINISTIC; the assertion below is defence-in-depth at the
        # adapter boundary.
        function_name = applier_config.deterministic_function_name
        if function_name is None:
            raise ValueError(
                "deterministic applier missing deterministic_function_name "
                "(domain invariant violated; should be unreachable)"
            )
        function = REGISTRY.get(function_name)
        if function is None:
            raise ValueError(
                f"deterministic_function_name {function_name!r} not in "
                f"registry; known functions: {sorted(REGISTRY)}"
            )
        return function(
            interaction=interaction,
            output=output,
            criterion=criterion,
        )
