"""GoalGraphPort — the daily-driver consumer port for the goal graph (D163).

The goal layer (Outcome nodes + lever-to-outcome edges) lives in the shared
graph, which the daily-driver context cannot reach directly: it may import
neither ``neo4j`` (the AST/``neo4j-confined`` fence) nor the ingestion context
(D17 independence). So daily_driver declares this consumer port and the apps
composition root bridges it to ingestion's ``OutcomeGraphPort`` — the
calendar/email ``MeetingGraphIndexPort`` + apps-bridge precedent.

The port speaks the daily-driver ``Goal`` domain (the bridge maps the generic
graph records onto it). Reads return goals with their lever + ladder; the raise
is the explicit, never-automatic target change (D9, the no-auto-modification
invariant). Ports layer is pure per D16 — no SQLAlchemy, no neo4j.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.daily_driver.domain.cdd import (
    ElementKind,
    GoalCddView,
    ProofState,
    ProvenanceOrigin,
)
from contexts.daily_driver.domain.contacts import ContactView
from contexts.daily_driver.domain.goal import Goal
from contexts.daily_driver.domain.skills import SkillItemView
from shared_kernel import TenantContext


class GoalGraphPort(Protocol):
    """Read/raise port for the goal layer in the shared graph (D163), extended
    with the authored CDD layer (S102, D200)."""

    async def list_goals(
        self, *, tenant_context: TenantContext
    ) -> tuple[Goal, ...]:
        """Return the tenant's goals, each with its lever + ladder."""
        ...

    async def raise_target_level(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        new_target_level: str,
    ) -> str | None:
        """Set the goal's current target to ``new_target_level`` (the explicit
        raise). The target is a goal-level property on the Outcome node (D163
        clarification), so the raise needs no lever id. Returns the new level,
        or ``None`` when the goal is absent or cross-tenant. Never called
        automatically — only on an explicit action.
        """
        ...

    # --- Authored CDD layer (S102, D200) -----------------------------------

    async def write_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        kind: ElementKind,
        element_id: UUID,
        label: str,
        origin: ProvenanceOrigin,
        proof_state: ProofState,
    ) -> None:
        """Persist one authored CDD element on the goal (S102, D200)."""
        ...

    async def write_authored_edge(
        self,
        *,
        tenant_context: TenantContext,
        edge_type: str,
        source_kind: str,
        source_id: UUID,
        target_kind: str,
        target_id: UUID,
    ) -> None:
        """Persist one authored causal edge (FEEDS / INFLUENCES, S102)."""
        ...

    async def set_authored_outcome(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        expected_outcome: str,
        origin: ProvenanceOrigin,
        proof_state: ProofState,
    ) -> None:
        """Set the authored expected-outcome stance on the goal with its
        provenance + proof state (S102 draft = llm_drafted/pending; S103a
        author/correct = user_authored/accepted)."""
        ...

    async def accept_authored_outcome(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> bool:
        """Mark the authored outcome accepted (the outcome proof accept path,
        S103a). Returns ``False`` when the goal has no authored outcome."""
        ...

    async def reject_authored_outcome(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> bool:
        """Clear the authored outcome stance — the user-initiated reject (S103a).
        The ``:Outcome`` node is the goal and is never deleted; only the authored
        stance is removed. Returns ``False`` when there was none."""
        ...

    async def read_goal_cdd(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> GoalCddView:
        """Read a goal's authored CDD for proof review (S102, D200)."""
        ...

    async def close_opportunity(
        self, *, tenant_context: TenantContext, opportunity_id: UUID,
        closed_reason: str,
    ) -> bool:
        """Close an opportunity with its outcome reason (S103n, D214) —
        archive-not-erase; the binds + correspondence stay. True when matched."""
        ...

    async def reopen_opportunity(
        self, *, tenant_context: TenantContext, opportunity_id: UUID
    ) -> bool:
        """Reopen a closed opportunity back to live, whole (S103n, D214)."""
        ...

    async def confirm_opportunity(
        self, *, tenant_context: TenantContext, opportunity_id: UUID
    ) -> bool:
        """Confirm a system-suggested opportunity → user_authored (S103o, D215)."""
        ...

    async def set_opportunity_gate(
        self, *, tenant_context: TenantContext, opportunity_id: UUID,
        current_gate_id: UUID | None,
    ) -> bool:
        """Re-stage an opportunity by writing its gate position (S103q, D217)."""
        ...

    async def delete_opportunity(
        self, *, tenant_context: TenantContext, opportunity_id: UUID
    ) -> bool:
        """Reject (delete) a suggested opportunity (S103o, D215); units + binds
        survive."""
        ...

    async def create_lead(
        self, *, tenant_context: TenantContext, opportunity_id: UUID,
        outcome_id: UUID, name: str, lead_gate_id: UUID,
        fit_tier: str, warm_access_available: str, origination_source: str,
    ) -> None:
        """Create a user-authored lead :Opportunity at the Lead gate (S103t, D221) —
        zero touches, no thread; reuses the D215 merge_opportunity write with
        provenance user_authored / accepted and the three origination properties."""
        ...

    # --- Contacts (S103u, D222) --------------------------------------------

    async def list_contacts(
        self, *, tenant_context: TenantContext
    ) -> tuple[ContactView, ...]:
        """The tenant's contacts (D222) — read for the derive, the proof surface, and
        a lead's inline contacts."""
        ...

    async def create_contact(
        self, *, tenant_context: TenantContext, contact_id: UUID, name: str,
        company: str | None, degree: str | None, strength: str | None,
        reachability: str | None, capture_source: str,
    ) -> None:
        """Add a user-authored contact (D222) — the manual capture route (a hand-added
        or LinkedIn-known person email did not surface). Provenance user_authored."""
        ...

    async def confirm_contact(
        self, *, tenant_context: TenantContext, contact_id: UUID
    ) -> bool:
        """Confirm a system-suggested contact → user_authored (D222)."""
        ...

    async def enrich_contact(
        self, *, tenant_context: TenantContext, contact_id: UUID,
        degree: str | None, strength: str | None, reachability: str | None,
    ) -> bool:
        """Enrich a contact with degree/strength/reachability (D222) — also flips
        provenance to user_authored (the operator authors the relationship)."""
        ...

    async def reject_contact(
        self, *, tenant_context: TenantContext, contact_id: UUID
    ) -> bool:
        """Reject (delete) a contact (D222)."""
        ...

    async def set_contact_role(
        self, *, tenant_context: TenantContext, contact_id: UUID,
        process_role: str | None,
    ) -> bool:
        """Set a contact's hiring-process role → user_authored (S103w, D227)."""
        ...

    # --- Skills profile (S103af, D238) -------------------------------------

    async def list_skill_items(
        self, *, tenant_context: TenantContext
    ) -> tuple[SkillItemView, ...]:
        """The tenant's skill-profile items (D238) — read for the proof surface and
        the leg-3 fit read."""
        ...

    async def create_skill_item(
        self, *, tenant_context: TenantContext, item_id: UUID, kind: str, text: str,
    ) -> None:
        """Add a user-authored skill item (D238) — the manual add route. Provenance
        user_authored, proof_state confirmed (the operator authored it directly)."""
        ...

    async def seed_skill_item(
        self, *, tenant_context: TenantContext, item_id: UUID, kind: str, text: str,
    ) -> None:
        """Seed a CV-extracted skill item (D238) — provenance cv_extraction,
        proof_state suggested. Idempotent + non-clobbering on re-upload (proof_state
        is written ON CREATE only, so re-seeding never un-confirms a proofed item)."""
        ...

    async def confirm_skill_item(
        self, *, tenant_context: TenantContext, item_id: UUID
    ) -> bool:
        """Confirm a suggested item → confirmed (D238)."""
        ...

    async def edit_skill_item(
        self, *, tenant_context: TenantContext, item_id: UUID, text: str
    ) -> bool:
        """Edit an item's text → confirmed (an authoring act, D238)."""
        ...

    async def reject_skill_item(
        self, *, tenant_context: TenantContext, item_id: UUID
    ) -> bool:
        """Reject (delete) a skill item (D238)."""
        ...

    async def set_qualification_field(
        self, *, tenant_context: TenantContext, opportunity_id: UUID,
        field_key: str, value: str | None, touch_only: bool = False,
    ) -> bool:
        """Set a qualification field's value + last_touched, or bump only the
        timestamp when ``touch_only`` (S103w, D228/D229). Writing a value also
        clears any JD-extracted draft for the field (Save supersedes the suggestion,
        S103ad/D236)."""
        ...

    async def set_opportunity_job_description(
        self, *, tenant_context: TenantContext, opportunity_id: UUID, text: str,
    ) -> bool:
        """Store the pasted job-description text on the opportunity (a schemaless
        ``job_description`` prop, S103ad/D236) — the durable source for extraction and
        leg 3's match. Returns True on match."""
        ...

    async def set_qualification_draft(
        self, *, tenant_context: TenantContext, opportunity_id: UUID,
        field_key: str, value: str | None,
    ) -> bool:
        """Set or clear a qualification field's JD-extracted draft (``q_<key>_draft``,
        S103ad/D236). ``value=None`` clears it (Dismiss). The draft is a suggestion,
        never the field value — only ``set_qualification_field`` creates a value."""
        ...

    async def set_disposition_counts(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        moat: int,
        pipeline: int,
        market: int,
        parked: int,
    ) -> None:
        """Persist the precision pass's disposition counts on the goal (S103i/D210)
        for the Map's recommendation-shaped summary."""
        ...

    async def accept_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        kind: ElementKind,
        element_id: UUID,
    ) -> bool:
        """Mark an authored element accepted (the proof accept path, S102)."""
        ...

    async def correct_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        kind: ElementKind,
        element_id: UUID,
        label: str,
    ) -> bool:
        """Edit an authored element's label and flip its origin to
        ``user_authored`` (the proof correct path, S102/D200)."""
        ...

    async def reject_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        kind: ElementKind,
        element_id: UUID,
    ) -> bool:
        """Remove an authored element (the proof reject path — user-initiated
        delete, allowed under the no-auto-deletion invariant, S102)."""
        ...

    async def reclassify_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        from_kind: ElementKind,
        to_kind: ElementKind,
        element_id: UUID,
    ) -> bool:
        """Reclassify an authored element across types (D201, S103a): preserve the
        node and its stable id, flip the origin to ``user_authored``, and flag
        (never drop) any now-ungrammatical incident edge. Returns ``False`` when
        absent or cross-tenant."""
        ...


__all__ = ["GoalGraphPort"]
