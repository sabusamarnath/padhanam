"""extract_jd_qualification — store the pasted JD, draft the two context fields, and
merge the discrete demand requirements (S103ad/D236, deepened S103ah/D240). Matching-engine
leg one.

Stores the job-description text on the opportunity (a durable source for re-extraction and
leg 3's match), calls the ``JdExtractorPort`` (the LiteLLM seam), and:

- writes each drafted **context** field to a ``q_<key>_draft`` slot — a *suggestion*, never
  the field value (D236); only the operator's Save creates a value.
- merges the extracted **requirements** into the schemaless ``demand_requirements`` list
  (D240): fresh drafts are added, every **confirmed** requirement is kept (invariant 4, no
  clobber), and the merge is idempotent (stable content-hash ids). No requirement is a fact
  until the operator proofs it (D200).
"""

from __future__ import annotations

from uuid import UUID

from contexts.daily_driver.domain.demand_requirements import (
    deserialize,
    merge_extracted,
    serialize,
)
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from contexts.daily_driver.ports.jd_extractor import JdExtractorPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def extract_jd_qualification(
    *, goal_graph: GoalGraphPort, jd_extractor: JdExtractorPort,
    actor: ActorContext, opportunity_id: UUID, jd_text: str,
) -> tuple[str, ...]:
    """Store the JD, draft the two context fields as ``q_<key>_draft`` suggestions, and
    merge the discrete requirement drafts into ``demand_requirements`` (D236/D240).
    Returns the context field keys that got a draft. An empty paste, an absent
    opportunity, or a non-conforming model response yields no drafts (the caller reloads
    either way). The requirement merge keeps confirmed items — re-extraction never
    clobbers a proofed requirement."""
    text = (jd_text or "").strip()
    if not text:
        return ()
    await goal_graph.set_opportunity_job_description(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id, text=text,
    )
    extracted = await jd_extractor.extract(jd_text=text)
    if extracted is None:
        return ()

    # Merge the requirement drafts (keep confirmed, replace drafts, idempotent, D240).
    existing = deserialize(
        await goal_graph.read_opportunity_requirements(
            tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
        )
    )
    merged = merge_extracted(existing, extracted.requirements)
    await goal_graph.set_opportunity_requirements(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
        requirements_json=serialize(merged),
    )

    # Draft the two context fields as q_<key>_draft suggestions (D236, unchanged).
    drafted: list[str] = []
    for field_key, draft in extracted.context_drafts():
        await goal_graph.set_qualification_draft(
            tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
            field_key=field_key, value=draft,
        )
        drafted.append(field_key)
    return tuple(drafted)


__all__ = ["extract_jd_qualification"]
