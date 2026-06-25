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
    significant_tokens,
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
    # D212: the unit's primary facet, so the drawer can open its read-only source.
    # Prefer the email facet (the verification target); fall back to the first
    # present facet (task/calendar). None when the unit has no present facet.
    from contexts.daily_driver.domain.work_unit import FacetType
    source_by_unit: dict = {}
    for v in views:
        present = [f for f in v.facets if f.present]
        email_f = next(
            (f for f in present if f.facet_type is FacetType.EMAIL), None
        )
        chosen = email_f or (present[0] if present else None)
        if chosen is not None:
            source_by_unit[v.unit_id] = (chosen.facet_type.value, chosen.facet_id)
    owned = await unit_graph.list_user_owned_unit_ids(
        tenant_context=actor.tenant_context
    )
    # The element vocabulary, for the why + the discriminativeness read (S103c-fix):
    # each authored element's label by id, and how many elements share each token.
    label_by_element: dict = {}
    all_labels: list[str] = []
    # S103c-fix-3: the goal-name/alias tokens per goal, so an alias binding's why
    # shows the real unit∩goal-name token (not the "goal name" placeholder).
    goal_tokens_by_outcome: dict = {}
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
        goal_tokens_by_outcome[goal.id] = frozenset(
            element_token_counts((goal.name, *goal.aliases)).keys()
        )
    token_counts = element_token_counts(tuple(all_labels))
    # D212: the corpus-IDF the discriminative basis ranks on — how many of the
    # tenant's units contain each significant token. Computed from the same unit
    # titles the correlate's bar reads, so the read-side basis and the bind-time bar
    # share the corpus frequencies and cannot diverge (D204/D212). Counts per unit
    # (a token in a unit's title counts once for that unit).
    unit_token_counts: dict[str, int] = {}
    for v in views:
        seen: set[str] = set()
        for f in v.facets:
            if f.present and f.title:
                seen |= significant_tokens(f.title)
        for tok in seen:
            unit_token_counts[tok] = unit_token_counts.get(tok, 0) + 1

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
            goal_tokens=goal_tokens_by_outcome.get(e.outcome_id, frozenset()),
            unit_token_counts=unit_token_counts,
        )
        src = source_by_unit.get(e.unit_id)
        bindings.append(
            ElementBinding(
                unit_id=e.unit_id,
                title=title,
                element_kind=e.element_kind,
                element_id=e.element_id,
                outcome_id=e.outcome_id,
                tier=e.tier,
                user_owned=e.unit_id in owned,
                matched_term=matched_term,
                strength=strength,
                source_facet_type=src[0] if src else "",
                source_facet_id=src[1] if src else None,
            )
        )
    return tuple(bindings)


__all__ = ["read_element_bindings", "read_element_evidence"]
