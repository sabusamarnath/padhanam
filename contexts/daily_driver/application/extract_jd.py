"""extract_jd_qualification — store the pasted JD and draft three qualification
fields (S103ad, D236). Matching-engine leg one.

Stores the job-description text on the opportunity (a durable source for
re-extraction and leg 3's match), calls the ``JdExtractorPort`` (the LiteLLM seam),
and writes each drafted field to a ``q_<key>_draft`` slot — a *suggestion*, never
the field value. Only the operator's Save (``set_qualification_field``) creates a
value, so no qualification field ever holds an unproofed fact (D200).
"""

from __future__ import annotations

from uuid import UUID

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
    """Store the JD and draft the three fields as suggestions (D236). Returns the
    field keys that got a draft. Writes only ``q_<key>_draft`` slots — never a value.
    An empty paste, an absent opportunity, or a non-conforming model response yields
    no drafts (the caller reloads the qualification either way)."""
    text = (jd_text or "").strip()
    if not text:
        return ()
    await goal_graph.set_opportunity_job_description(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id, text=text,
    )
    extracted = await jd_extractor.extract(jd_text=text)
    if extracted is None:
        return ()
    drafted: list[str] = []
    for field_key, draft in extracted.drafts():
        await goal_graph.set_qualification_draft(
            tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
            field_key=field_key, value=draft,
        )
        drafted.append(field_key)
    return tuple(drafted)


__all__ = ["extract_jd_qualification"]
