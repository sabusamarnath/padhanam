"""Polymorphic applier adapter implementing ApplierPort (D54).

Single adapter class dispatches on ``applier_config.applier_type``.
The deterministic dispatch path resolves
``deterministic_function_name`` against the deterministic-library
registry and invokes the function. The prompt dispatch path
formats ``applier_config.prompt_template`` against the (output,
criterion) pair and asks the configured ``InferencePort`` to run a
judge model against the formatted prompt; the result is parsed into
the criterion's score-label space. The human dispatch path is
data-substrate-only per D53's Reading-C posture (no automated write
path runs at any session through P5).

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
serves every tenant. The ``InferencePort`` injected at construction
time is the cross-context boundary; the adapter does not
instantiate it (apps/ wires the LiteLLM-backed adapter, tests pass
fakes). This keeps composition out of the context per D17.

Score parsing strategy at S17a (reflection prompt 2): regex for the
first integer or first instance of a level label defined on the
criterion. The strategy is deliberately simple at S17a; sophisticated
parsing (structured output, JSON mode, calibration) is downstream
work. If the judge response contains no parseable score, the
adapter returns the empty string — a non-null automated_score that
downstream consumers can treat as "judge produced no score" without
the column being null. The S17b/S18 sessions inherit any failure
modes the integration test surfaces and address them with richer
parsing or structured output.

Dispatch-mechanical contingency from D54 (reflection prompt 1):
the prompt branch must stay free of domain-shaped knowledge. The
implementation here threads the criterion shape into the template
formatting (``criterion_name``, ``criterion_levels``) but does not
encode any conditional that varies by criterion *content* —
formatting is uniform; the LLM judges what the criterion means.
If the prompt branch ever needs to inspect criterion levels to
decide between parsing strategies or to choose a judge model, the
contingency bites and D54 revisits.
"""

from __future__ import annotations

import re

from contexts.evaluation.adapters.outbound.deterministic_library import REGISTRY
from contexts.evaluation.domain.applier import ApplierConfig, ApplierType
from contexts.evaluation.domain.interaction import Interaction
from contexts.evaluation.domain.model_config import ModelConfig
from contexts.evaluation.domain.scoring_sheet import Criterion
from contexts.evaluation.ports.inference_port import InferencePort
from shared_kernel import TenantContext


class PolymorphicApplier:
    """ApplierPort implementation. Dispatches on applier_type.

    Constructor takes the optional ``InferencePort`` and
    ``TenantContext`` so the prompt branch can call inference. The
    deterministic branch ignores both; constructing the adapter
    without them is supported for purely-deterministic workloads
    (e.g. the S16 integration test continued to work post-rename
    with no constructor arguments).
    """

    def __init__(
        self,
        inference_port: InferencePort | None = None,
        tenant_context: TenantContext | None = None,
    ) -> None:
        self._inference_port = inference_port
        self._tenant_context = tenant_context

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
            return await self._apply_prompt(
                output=output,
                criterion=criterion,
                applier_config=applier_config,
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

    async def _apply_prompt(
        self,
        *,
        output: str,
        criterion: Criterion,
        applier_config: ApplierConfig,
    ) -> str:
        if self._inference_port is None or self._tenant_context is None:
            raise ValueError(
                "prompt applier dispatch requires the adapter to be "
                "constructed with an InferencePort and TenantContext"
            )
        # __post_init__ on ApplierConfig guarantees prompt_template
        # and judge_model are non-null when applier_type is PROMPT.
        template = applier_config.prompt_template
        judge_model = applier_config.judge_model
        if template is None or judge_model is None:
            raise ValueError(
                "prompt applier missing prompt_template or judge_model "
                "(domain invariant violated; should be unreachable)"
            )
        formatted_prompt = template.format(
            output=output,
            criterion_name=criterion.name,
            criterion_levels=", ".join(level.label for level in criterion.levels),
        )
        replay_result = await self._inference_port.complete(
            model_config=ModelConfig(model_name=judge_model),
            input=formatted_prompt,
            tenant_context=self._tenant_context,
        )
        return self._parse_score(
            text=replay_result.output_text,
            criterion=criterion,
        )

    @staticmethod
    def _parse_score(*, text: str, criterion: Criterion) -> str:
        """Extract a score label from the judge model's response.

        Strategy at S17a: prefer matching against the criterion's
        defined level labels (longest-first to avoid prefix collisions);
        fall back to the first integer in the response. If neither
        produces a hit, return the empty string — the column is
        text and nullable, but a non-null empty value lets downstream
        consumers distinguish "judge produced no score" from "no
        judge ran." S17b/S18 inherits the parsing failure modes.
        """
        labels_by_length = sorted(
            (level.label for level in criterion.levels),
            key=len,
            reverse=True,
        )
        lowered = text.lower()
        for label in labels_by_length:
            if label.lower() in lowered:
                return label
        match = re.search(r"-?\d+", text)
        if match is not None:
            return match.group(0)
        return ""
