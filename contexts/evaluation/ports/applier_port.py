"""ApplierPort — single polymorphic contract for all applier types.

Per D54 (committed at S16 commit 6 if the build supports it), the port
is one polymorphic async contract that accepts ``ApplierConfig`` and
returns the automated score string the criterion authors interpret per
its ``levels``. The adapter switches on ``applier_config.applier_type``
to invoke the right deterministic function (S16) or LLM-as-judge call
(S17). The use case stays indifferent to applier mechanism, which
honours D53's appliers-as-data framing.

Return shape note (build-time deviation from S16-prompt's signature):
the prompt's recommended signature returns ``RubricApplication``. At
implementation we found the applier does not have all of the
RubricApplication fields cleanly (``id`` and ``created_at`` are
storage-layer concerns; threading them through the port couples the
applier to the persistence shape). The honest return shape is the
automated score ``str | None`` — the applier is responsible for
scoring, not record assembly. The use case constructs the
``RubricApplication`` from the score plus the context it already
holds (interaction, applier id, criterion id, revision id). This
deviation is documented in D54's reasoning.

The port is a Protocol so adapters need not inherit; satisfying the
async ``apply`` method is sufficient (consistent with the registry
and inference port shapes).
"""

from __future__ import annotations

from typing import Protocol

from contexts.evaluation.domain.applier import ApplierConfig
from contexts.evaluation.domain.interaction import Interaction
from contexts.evaluation.domain.scoring_sheet import Criterion


class ApplierPort(Protocol):
    async def apply(
        self,
        *,
        interaction: Interaction,
        output: str,
        criterion: Criterion,
        applier_config: ApplierConfig,
    ) -> str | None:
        """Return the automated_score for this criterion against this output.

        ``None`` is reserved for the human-applier mode per D53: the
        data-substrate exists at S16 but no automated write path runs;
        the human-score path lands at P10/P11.
        """
        ...
