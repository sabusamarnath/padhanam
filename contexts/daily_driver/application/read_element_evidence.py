"""read_element_evidence — the read-only element-evidence summary (D202, S103b).

Surfaces where matched signal landed: per authored element, how many units
evidence it, plus the unbound-bucket size (units that matched no element — the
emergent loop's queue, S104). Read-only; the relink/unlink correction paths are
S103c. Behind ``CDD_READ`` (the user inspecting their own model's evidence).
"""

from __future__ import annotations

from contexts.daily_driver.domain.goal_assessment import (
    ElementBinding,
    ElementEvidenceSummary,
    binding_rationale,
    element_token_counts,
    summarise_element_evidence,
)
from contexts.daily_driver.domain.unit_view import build_unit_views
from contexts.daily_driver.ports.facet_source import FacetSource
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from contexts.daily_driver.ports.unit_graph import UnitGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def read_element_evidence(
    *, unit_graph: UnitGraphPort, actor: ActorContext
) -> ElementEvidenceSummary:
    """Return per-element unit counts + the unbound-bucket size (S103b)."""
    evidence = await unit_graph.list_element_evidence(
        tenant_context=actor.tenant_context
    )
    units = await unit_graph.list_units(tenant_context=actor.tenant_context)
    return summarise_element_evidence(evidence, total_units=len(units))


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def read_element_bindings(
    *,
    unit_graph: UnitGraphPort,
    facet_source: FacetSource,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
) -> tuple[ElementBinding, ...]:
    """Return each unit→element binding joined to the unit's title, its
    user-ownership, and a recomputed-on-read rationale — the *why* (matched term)
    and a lexical **match-strength** band (S103c-fix). Strength is string-match
    strength, not correctness: tier orders it, discriminativeness breaks ties
    within the keyword tier. No storage change — recomputed from the unit title,
    the element label, and the element vocabulary."""
    evidence = await unit_graph.list_element_evidence(
        tenant_context=actor.tenant_context
    )
    records = await unit_graph.list_units(tenant_context=actor.tenant_context)
    facets = await facet_source.list_facets(actor=actor)
    views = build_unit_views(
        tuple(records), {(f.facet_type, f.facet_id): f for f in facets}
    )
    title_by_unit = {v.unit_id: v.title for v in views}
    owned = await unit_graph.list_user_owned_unit_ids(
        tenant_context=actor.tenant_context
    )
    # The element vocabulary, for the why + the discriminativeness read (S103c-fix):
    # each authored element's label by id, and how many elements share each token.
    label_by_element: dict = {}
    all_labels: list[str] = []
    goals = await goal_graph.list_goals(tenant_context=actor.tenant_context)
    for goal in goals:
        cdd = await goal_graph.read_goal_cdd(
            tenant_context=actor.tenant_context, outcome_id=goal.id
        )
        for el in cdd.elements:
            label_by_element[el.element_id] = el.label
            all_labels.append(el.label)
        if cdd.expected_outcome:
            label_by_element[goal.id] = cdd.expected_outcome
            all_labels.append(cdd.expected_outcome)
    token_counts = element_token_counts(tuple(all_labels))

    bindings: list[ElementBinding] = []
    for e in evidence:
        title = title_by_unit.get(e.unit_id, "(unknown)")
        label = label_by_element.get(e.element_id, "")
        matched_term, strength = binding_rationale(
            unit_title=title,
            element_label=label,
            tier=e.tier,
            basis=e.basis,
            token_element_counts=token_counts,
        )
        bindings.append(
            ElementBinding(
                unit_id=e.unit_id,
                title=title,
                element_kind=e.element_kind,
                element_id=e.element_id,
                tier=e.tier,
                user_owned=e.unit_id in owned,
                matched_term=matched_term,
                strength=strength,
            )
        )
    return tuple(bindings)


__all__ = ["read_element_bindings", "read_element_evidence"]
