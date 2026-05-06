"""replay_and_score orchestrator (D53, S17a).

For each interaction in a set, run the configured model against the
input via ``InferencePort``, then apply the scoring sheet to the
model's output. Each ``RubricApplication`` produced carries the
``trace_id`` of the inference call that produced its scored output,
linking the score back to the OTel/Langfuse trace for cost-per-
successful-task computation at S17b.

The orchestrator is the architectural authority on flow shape;
``apply_scoring_sheet`` (the use case at the per-interaction
granularity) is reused unchanged except for an optional ``trace_id``
parameter added at this commit. The two-level shape (per-set
orchestrator + per-interaction use case) reflects the natural
boundary: the orchestrator's responsibility is iteration and
inference; the use case's responsibility is per-interaction scoring
and persistence.

ModelConfig is a caller parameter rather than a per-interaction-set
field. The model is one of the variables under test in evaluation —
"how does this scoring sheet score this set when run against model
X versus model Y" — and lifting the choice to the caller reflects
that. Persisting the model choice on the interaction set itself
would foreclose A/B comparison.

The orchestrator does not own model selection logic. Callers (CLI
runner at S18, future authoring UI, recommendation engine at P11)
choose the model and pass it through; the orchestrator is
mechanical.
"""

from __future__ import annotations

from typing import Awaitable, Callable
from uuid import UUID

from contexts.evaluation.domain.interaction import Interaction
from contexts.evaluation.domain.model_config import ModelConfig
from contexts.evaluation.domain.rubric_application import RubricApplication
from contexts.evaluation.ports.applier_port import ApplierPort
from contexts.evaluation.ports.inference_port import InferencePort
from contexts.evaluation.ports.interaction_repository_port import (
    InteractionRepositoryPort,
)
from contexts.evaluation.ports.rubric_application_repository_port import (
    RubricApplicationRepositoryPort,
)
from contexts.evaluation.ports.scoring_sheet_repository_port import (
    ScoringSheetRepositoryPort,
)
from shared_kernel import TenantContext


_ApplyScoringSheet = Callable[..., Awaitable[list[RubricApplication]]]


async def replay_and_score(
    *,
    tenant_context: TenantContext,
    scoring_sheet_revision_id: UUID,
    interaction_set_id: UUID,
    model_config: ModelConfig,
    inference_port: InferencePort,
    interaction_repository: InteractionRepositoryPort,
    scoring_sheet_repository: ScoringSheetRepositoryPort,
    rubric_application_repository: RubricApplicationRepositoryPort,
    applier: ApplierPort,
    apply_scoring_sheet: _ApplyScoringSheet,
) -> list[RubricApplication]:
    """Replay each interaction against ``model_config`` and score it.

    ``apply_scoring_sheet`` is injected as a callable so unit tests
    can substitute a fake; production wiring imports the real use
    case. The injection mirrors the dependency-injection shape the
    use case suite already uses — ports for storage, callable for
    the use case.
    """
    interactions: list[Interaction] = (
        await interaction_repository.list_by_set_id(interaction_set_id)
    )
    all_applications: list[RubricApplication] = []
    for interaction in interactions:
        replay_result = await inference_port.complete(
            model_config=model_config,
            input=_format_input(interaction),
            tenant_context=tenant_context,
        )
        applications = await apply_scoring_sheet(
            tenant_context=tenant_context,
            scoring_sheet_revision_id=scoring_sheet_revision_id,
            interaction=interaction,
            output=replay_result.output_text,
            scoring_sheet_repository=scoring_sheet_repository,
            rubric_application_repository=rubric_application_repository,
            applier=applier,
            trace_id=replay_result.trace_id or None,
        )
        all_applications.extend(applications)
    return all_applications


def _format_input(interaction: Interaction) -> str:
    """Render the interaction's input dict into the prompt string the
    inference port expects.

    The interaction model carries jsonb-shaped inputs to support text
    prompts, structured payloads, and future agent-trajectory inputs
    (per the schema rationale at S16). At S17a we recognise one
    shape: ``{"prompt": "..."}`` is rendered as the prompt string.
    Any other shape falls back to ``str(input)`` — honest about the
    shape rather than failing silently. Future sessions add richer
    rendering (chat messages, tool-call trajectories) as the input
    shapes that need them activate.
    """
    if isinstance(interaction.input, dict):
        prompt = interaction.input.get("prompt")
        if isinstance(prompt, str):
            return prompt
    return str(interaction.input)
