"""Polymorphic applier adapter implementing ApplierPort (D54).

Single adapter class dispatches on ``applier_config.applier_type``.
The deterministic dispatch path resolves
``deterministic_function_name`` against the deterministic-library
registry and invokes the function. The prompt dispatch path lands
at S17a (LLM-as-judge via the ``InferencePort``); the human dispatch
path is data-substrate-only per D53's Reading-C posture (no
automated write path runs at any session through P5).

The class was named ``ExactMatchApplier`` at S16 because the
registry held only ``exact_match``; the structural shape was
already polymorphic-by-applier-type, and the rename to
``PolymorphicApplier`` at S17a reflects responsibility (the adapter
dispatches across all three applier types, not just exact-match).
Naming-as-architecture: the file's responsibility is dispatch;
specific deterministic primitives live in
``deterministic_library.py``, and the prompt branch lives in this
file because it is one of the dispatch arms.

The adapter is stateless with respect to per-tenant configuration —
no tenant-specific state sits on ``self`` — so a single instance
serves every tenant. Wiring (use case construction at the inbound
adapter or test) injects this instance as the ``ApplierPort`` value.
"""

from __future__ import annotations

from contexts.evaluation.adapters.outbound.deterministic_library import REGISTRY
from contexts.evaluation.domain.applier import ApplierConfig, ApplierType
from contexts.evaluation.domain.interaction import Interaction
from contexts.evaluation.domain.scoring_sheet import Criterion


class PolymorphicApplier:
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
                "prompt applier dispatch lands at S17a commit 4; "
                "this commit is the rename only"
            )
        if applier_config.applier_type == ApplierType.HUMAN:
            raise NotImplementedError(
                "human applier mode is data-substrate-only per D53; "
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
