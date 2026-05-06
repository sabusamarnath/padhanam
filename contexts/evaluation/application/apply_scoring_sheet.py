"""apply_scoring_sheet use case (D53).

Given a tenant context, a scoring sheet revision id, an interaction,
and an output, produce one ``RubricApplication`` per criterion on the
revision. Each criterion's configured applier scores the output via
``ApplierPort``; the resulting ``automated_score`` lands on a new
rubric_application record persisted through the repository port.

Per D53 (Reading-C posture), only the automated write path runs at
S16: ``human_score``, ``reviewed_by_user_id``, and ``confirmed_at``
stay null on every record this use case produces. The human-review
write path lands at P10/P11.

TenantContext is taken as an explicit parameter per D50's propagation
pattern; at S16 it is not consumed inside the use case body (the
ports' adapters carry the per-tenant session-factory at construction
time, resolved upstream by the inbound adapter or test). The
TenantContext on the signature is the discipline-holding shape — when
inbound adapters land later in P5 or in P11, they will resolve the
TenantContext at the router boundary and thread it through unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.evaluation.domain.interaction import Interaction
from contexts.evaluation.domain.rubric_application import RubricApplication
from contexts.evaluation.ports.applier_port import ApplierPort
from contexts.evaluation.ports.rubric_application_repository_port import (
    RubricApplicationRepositoryPort,
)
from contexts.evaluation.ports.scoring_sheet_repository_port import (
    ScoringSheetRepositoryPort,
)
from shared_kernel import TenantContext


async def apply_scoring_sheet(
    *,
    tenant_context: TenantContext,
    scoring_sheet_revision_id: UUID,
    interaction: Interaction,
    output: str,
    scoring_sheet_repository: ScoringSheetRepositoryPort,
    rubric_application_repository: RubricApplicationRepositoryPort,
    applier: ApplierPort,
) -> list[RubricApplication]:
    pairs = await scoring_sheet_repository.get_criteria_with_appliers(
        scoring_sheet_revision_id
    )
    results: list[RubricApplication] = []
    for criterion, applier_config in pairs:
        score = await applier.apply(
            interaction=interaction,
            output=output,
            criterion=criterion,
            applier_config=applier_config,
        )
        rubric_application = RubricApplication(
            id=uuid4(),
            scoring_sheet_revision_id=scoring_sheet_revision_id,
            criterion_id=criterion.id,
            interaction_id=interaction.id,
            applier_id=applier_config.id,
            automated_score=score,
            human_score=None,
            reviewed_by_user_id=None,
            confirmed_at=None,
            created_at=datetime.now(timezone.utc),
        )
        await rubric_application_repository.save(rubric_application)
        results.append(rubric_application)
    return results
