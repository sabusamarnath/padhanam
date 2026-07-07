"""OutcomeGraphPort — the typed goal-graph surface on the shared graph (D163).

The whole-life goal taxonomy (D163) models a goal as an ``:Outcome`` node and
its lever as a ``:Lever`` node connected by a ``LEVER_FOR`` edge that carries
the goal's ``mode`` and, for a progressive goal, an ordered level ladder plus a
current target level. This port is the typed graph capability for that shape.

It is a *sibling* of ``GraphRepositoryPort``: the existing ``:Entity`` /
``Relationship`` vocabulary is built for LLM-extracted source entities keyed by
``source_chunk_ids`` and cannot carry a mode or a target ladder, so the
Outcome/lever shape is a new node-and-edge family rather than a reuse. It lives
behind the same ``TenantScopedNeo4jSession`` wrapper (the single Cypher surface
fenced by the ``neo4j-confined`` contract and the AST enforcement test), so no
raw driver call enters domain code.

The port is deliberately goal-agnostic at the graph boundary: it speaks of
Outcomes and Levers in primitive terms (ids, names, the mode string, the ladder
strings). The daily-driver context owns the *goal* concept and consumes this
through its own ``GoalGraphPort`` + an apps-composition-root bridge (the
calendar/email ``MeetingGraphIndexPort`` precedent). The ``:Lever`` node is a
thin *reference* to the commitment that lives in Postgres — it carries only the
``commitment_id``, never a copy of the commitment's row (D163 Step 0 F3).

Every node and edge carries ``tenant_id`` + ``jurisdiction`` and is reached only
through the tenant-scoped wrapper, so property-based isolation per D63/D64
holds for the goal graph exactly as it does for the entity graph.

Errors reuse ``GraphRepositoryError`` / ``GraphRepositoryConfigurationError``
from ``graph_repository_port`` so callers handle one error taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Sequence
from uuid import UUID

from shared_kernel import TenantContext


@dataclass(frozen=True)
class LeverEdgeRecord:
    """One ``LEVER_FOR`` edge as read from the graph (D163, S63).

    ``commitment_id`` is the thin :Lever reference's Postgres commitment id;
    ``step_order`` + ``step_state`` are the lever's relationship-level
    attributes for a sequence goal (``None`` for a single-lever progressive
    goal).
    """

    commitment_id: UUID
    step_order: int | None = None
    step_state: str | None = None


@dataclass(frozen=True)
class OutcomeGraphRecord:
    """One Outcome with all its lever edges as read from the graph (D163).

    Goal-level properties live on the Outcome (the D163 clarification):
    ``ladder`` + ``current_target_level`` for a progressive goal,
    ``terminal_target`` + ``terminal_state`` for a sequence goal (each ``None``/
    empty for the other shape). ``levers`` carries every ``LEVER_FOR`` edge — one
    for a progressive goal, the ordered chain for a sequence goal.
    """

    outcome_id: UUID
    name: str
    control: str
    subject: str
    mode: str
    ladder: tuple[str, ...]
    current_target_level: str | None
    terminal_target: str | None = None
    terminal_state: str | None = None
    levers: tuple[LeverEdgeRecord, ...] = ()
    # Goal-owned alias terms (category synonyms, D174 tier two).
    aliases: tuple[str, ...] = ()
    # Goal domain (D179): the surface tier this goal's covered work renders
    # under (work / personal / family). None when unset (the read falls through
    # to the connection default).
    domain: str | None = None


@dataclass(frozen=True)
class AuthoredElementRecord:
    """One authored CDD element as read from the graph (S102, D200).

    ``element_kind`` is ``lever`` / ``intermediary`` / ``external`` (the node
    label, lower-cased). ``element_id`` is the element's stable id (an authored
    lever's ``lever_id``; an intermediary's / external's ``element_id``).
    ``outcome_id`` is the goal whose CDD this element belongs to. ``label`` is
    the human-readable text; ``provenance_origin`` and ``proof_state`` carry the
    D200 authored signal.
    """

    element_kind: str
    element_id: UUID
    outcome_id: UUID
    label: str
    provenance_origin: str
    proof_state: str
    # The gate whose local CDD this element belongs to (S103g, D207), or None for
    # a goal-level (portfolio) element.
    gate_id: UUID | None = None


@dataclass(frozen=True)
class GateRecord:
    """One process-flow gate as read from the graph (S103g, D207).

    A gate is a first-class flow node, sequenced by ``gate_order``, scoped to the
    goal by ``outcome_id``. The gate node is its local CDD's local-outcome
    endpoint (an intermediary FEEDS the gate); ``local_outcome`` / ``local_goal``
    are the framework's gate-level outcome and goal. ``step_commitment_id``
    references the D163 lever-step the gate corresponds to, or None.
    """

    gate_id: UUID
    outcome_id: UUID
    name: str
    gate_order: int
    local_outcome: str
    local_goal: str
    provenance_origin: str
    proof_state: str
    step_commitment_id: UUID | None = None


@dataclass(frozen=True)
class OpportunityRecord:
    """One opportunity (process instance / Flow item) as read from the graph
    (S103h, D208). Belongs to the goal by ``outcome_id``, positioned at
    ``current_gate_id`` (its furthest-evidenced gate), grouping ``unit_count``
    units via ``BELONGS_TO``. ``source`` records the clustering signature."""

    opportunity_id: UUID
    name: str
    current_gate_id: UUID | None
    provenance_origin: str
    proof_state: str
    unit_count: int
    source: str | None = None
    # The closed state (S103n, D214). ``status`` is ``live`` or ``closed``
    # (coalesced from a missing value to ``live`` for pre-D214 opportunities);
    # ``closed_reason`` (one of the five outcome types) + ``closed_at`` are set when
    # closed. Closing is archive-not-erase — the binds + correspondence stay.
    status: str = "live"
    closed_reason: str | None = None
    closed_at: datetime | None = None
    # The lead-origination properties (S103t, D221) — operator-set on a lead, ``None``
    # on a clustered opportunity. ``fit_tier`` bullseye/strong/opportunistic;
    # ``warm_access_available`` warm/cold; ``origination_source`` inbound/outbound.
    fit_tier: str | None = None
    warm_access_available: str | None = None
    origination_source: str | None = None
    # The qualification props (S103w, D228): a ``q_``-prefixed map (value + ``_ts``).
    qualification: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ContactRecord:
    """One contact (a person in the operator's network) as read from the graph
    (S103u, D222). Linked to a company by ``company`` (a normalized string, not a
    node). ``degree``/``strength``/``reachability`` are ``None`` until the operator
    proofs them (the operator authors the relationship, D200)."""

    contact_id: UUID
    name: str
    email: str | None
    company: str | None
    degree: str | None
    strength: str | None
    reachability: str | None
    capture_source: list[str] = field(default_factory=list)  # set-valued channels (S103x, D230)
    provenance_origin: str = "system_suggested"
    process_role: str | None = None  # the hiring-process part they play (S103w, D227)


@dataclass(frozen=True)
class SkillItemRecord:
    """One skill-profile entry as read from the graph (S103af, D238). Extracted from
    the operator's CV, ``proof_state`` ``suggested`` until the operator confirms/edits
    → ``confirmed`` (the extract-and-proof lifecycle, D215/D222)."""

    item_id: UUID
    kind: str
    text: str
    proof_state: str
    provenance_origin: str


@dataclass(frozen=True)
class AuthoredEdgeRecord:
    """One authored causal edge as read from the graph (S102, D200).

    ``edge_type`` is ``FEEDS`` or ``INFLUENCES``; ``source_kind`` / ``target_kind``
    are the endpoint labels lower-cased (``lever`` / ``intermediary`` /
    ``external`` / ``outcome``); the ids are the endpoints' stable ids.
    ``needs_review`` is set when a reclassify (D201, S103a) made the edge
    ungrammatical for the new source kind — flagged for the user, never dropped.
    """

    edge_type: str
    source_kind: str
    source_id: UUID
    target_kind: str
    target_id: UUID
    needs_review: bool = False


@dataclass(frozen=True)
class AuthoredCddRecord:
    """A goal's authored CDD as read from the graph (S102, D200).

    ``expected_outcome`` is the authored stance on the outcome — the measurable
    result that means the goal is met — stored on the ``:Outcome`` node; ``None``
    when never drafted. ``expected_outcome_origin`` / ``expected_outcome_proof_state``
    carry its authored signal (S103a; coalesced to ``llm_drafted`` / ``pending``
    for the S102 drafts that predate the proof properties), both ``None`` when
    there is no authored outcome.
    """

    outcome_id: UUID
    elements: tuple[AuthoredElementRecord, ...]
    edges: tuple[AuthoredEdgeRecord, ...]
    expected_outcome: str | None = None
    expected_outcome_origin: str | None = None
    expected_outcome_proof_state: str | None = None
    # The precision pass's disposition counts (S103i, D210), or None when never
    # correlated: moat (confirmed job emails), pipeline + market (routed counts),
    # parked (un-bound by the genuine-match bar).
    disposition_moat: int | None = None
    disposition_pipeline: int | None = None
    disposition_market: int | None = None
    disposition_parked: int | None = None


class OutcomeGraphPort(Protocol):
    """Typed goal-graph capability on the shared Neo4j instance (D163)."""

    async def merge_outcome(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        name: str,
        control: str,
        subject: str,
        mode: str,
        ladder: Sequence[str],
        current_target_level: str | None,
        terminal_target: str | None = None,
        terminal_state: str | None = None,
        aliases: Sequence[str] = (),
        domain: str | None = None,
    ) -> None:
        """Idempotently MERGE an ``:Outcome`` node by ``(tenant_id, outcome_id)``.

        Per the D163 clarification (S63), the goal-level properties live on the
        node: ``mode``, the ``ladder`` + ``current_target_level`` (progressive),
        and ``terminal_target`` + ``terminal_state`` (sequence). Re-running
        updates them and leaves ``created_at`` from the first MERGE intact.
        """
        ...

    async def merge_lever_for_outcome(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        commitment_id: UUID,
        step_order: int | None = None,
        step_state: str | None = None,
    ) -> None:
        """MERGE the ``:Lever`` node (by ``(tenant_id, commitment_id)``) and the
        ``LEVER_FOR`` edge to the Outcome. The edge carries only that the lever
        serves the outcome plus, for a sequence goal, the lever's
        relationship-level ``step_order`` + ``step_state`` (the D163
        clarification). The Outcome must already exist (caller merges it first);
        the lever is a thin reference to the Postgres commitment, not a copy.
        """
        ...

    async def set_outcome_target(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        current_target_level: str,
    ) -> str | None:
        """Set the ``current_target_level`` on an existing ``:Outcome`` node
        (the explicit raise action — never automatic, D9). The target is a
        goal-level property (D163 clarification), so the raise needs no lever
        id. Returns the new level on success, ``None`` when the outcome is
        absent or cross-tenant.
        """
        ...

    async def archive_outcome(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> bool:
        """Mark a goal archived (S103e, D205) — a reversible, non-destructive
        removal that sets ``archived_at`` on the ``:Outcome`` node. The goal is
        never deleted (the no-auto-deletion invariant: user-initiated removal
        marks, never erases); its CDD elements, evidence binds and audit history
        stay intact. An archived goal drops out of ``list_outcomes`` (active
        only), so the assess surface and the matcher stop reading it. Returns
        ``True`` when the goal was found, ``False`` when absent or cross-tenant.
        """
        ...

    async def unarchive_outcome(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> bool:
        """Re-activate an archived goal (S103e, D205) — removes ``archived_at``
        so the goal returns whole to every read. Returns ``True`` when found."""
        ...

    async def list_archived_outcome_ids(
        self, *, tenant_context: TenantContext
    ) -> list[UUID]:
        """Return the ids of every archived goal (S103e, D205) — the complement
        of ``list_outcomes`` (active-only). Reactivation reads this to restore the
        whole archived set without depending on seed-module ids."""
        ...

    async def list_outcomes(
        self,
        *,
        tenant_context: TenantContext,
    ) -> Sequence[OutcomeGraphRecord]:
        """Return every **active** Outcome (``archived_at IS NULL``) with its
        lever edge for the bound tenant, ordered by name. Archived goals (S103e)
        are scoped out here, so every consumer — the assess surface and the
        matcher — reads active goals only. Cross-tenant rows never surface (the
        wrapper binds ``tenant_id`` into every predicate)."""
        ...


    # --- Authored CDD layer (S102, D200) -----------------------------------

    async def merge_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        element_kind: str,
        element_id: UUID,
        label: str,
        provenance_origin: str,
        proof_state: str,
        gate_id: UUID | None = None,
    ) -> None:
        """Idempotently MERGE an authored CDD element (S102, D200).

        ``element_kind`` is ``lever`` / ``intermediary`` / ``external`` — the
        node label, drawn from a whitelist (Neo4j labels are not parameterisable,
        so the wrapper composes the literal label from the whitelist, never from
        free input). An authored lever identifies by ``lever_id`` and may have no
        ``commitment_id`` yet; an intermediary/external identifies by
        ``element_id``. ``provenance_origin`` and ``proof_state`` carry the D200
        authored signal. ``gate_id`` (S103g, D207) scopes the element to a gate's
        local CDD; goal-level elements pass ``None``.
        """
        ...

    # --- Process gates (S103g, D207) ---------------------------------------

    async def merge_gate(
        self,
        *,
        tenant_context: TenantContext,
        gate_id: UUID,
        outcome_id: UUID,
        name: str,
        gate_order: int,
        local_outcome: str,
        local_goal: str,
        provenance_origin: str,
        proof_state: str,
        step_commitment_id: UUID | None = None,
    ) -> None:
        """Idempotently MERGE a process-flow gate (D207) — a first-class flow node
        and its local CDD's local-outcome endpoint."""
        ...

    async def list_gates(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> Sequence[GateRecord]:
        """Return a goal's gates ordered by ``gate_order`` (D207)."""
        ...

    # --- Process instances / opportunities (S103h, D208) -------------------

    async def merge_opportunity(
        self,
        *,
        tenant_context: TenantContext,
        opportunity_id: UUID,
        outcome_id: UUID,
        name: str,
        current_gate_id: UUID | None,
        provenance_origin: str,
        proof_state: str,
        source: str | None = None,
        fit_tier: str | None = None,
        warm_access_available: str | None = None,
        origination_source: str | None = None,
    ) -> None:
        """Idempotently MERGE an opportunity Flow item (D208) — a process instance
        belonging to the goal, positioned at its furthest-evidenced gate. The three
        lead-origination properties (S103t, D221) are ``None`` for clustered
        opportunities and set for a user-authored lead at the Lead gate."""
        ...

    async def list_opportunities(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> Sequence[OpportunityRecord]:
        """Return a goal's opportunities with their unit counts (D208)."""
        ...

    async def set_outcome_disposition(
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
        so the Map's recommendation-shaped summary reads them."""
        ...

    async def close_opportunity(
        self, *, tenant_context: TenantContext, opportunity_id: UUID,
        closed_reason: str,
    ) -> bool:
        """Close an opportunity with its outcome reason (S103n, D214) —
        archive-not-erase: sets status/reason/closed_at, leaves the node, its
        memberships, and its binds intact. Returns True when matched."""
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
        """Re-stage an opportunity by writing its gate position (S103q, D217); null
        clears to Unplaced. The operator proofing the gate. True when matched."""
        ...

    async def delete_opportunity(
        self, *, tenant_context: TenantContext, opportunity_id: UUID
    ) -> bool:
        """Reject (delete) a suggested opportunity (S103o, D215) — the units + binds
        survive; only the node + BELONGS_TO go. True when a node was deleted."""
        ...

    # --- Contacts (S103u, D222) --------------------------------------------

    async def merge_contact(
        self, *, tenant_context: TenantContext, contact_id: UUID, name: str,
        email: str | None, company: str | None, degree: str | None,
        strength: str | None, reachability: str | None, capture_source: str,
        provenance_origin: str, process_role: str | None = None,
    ) -> None:
        """Idempotently MERGE a :Contact (D222) — a person in the operator's network,
        linked to a company by a normalized string. Seeded system_suggested from the
        moat senders, or hand-added user_authored. ``process_role`` is the hiring-
        process part they play (S103w, D227)."""
        ...

    async def set_contact_role(
        self, *, tenant_context: TenantContext, contact_id: UUID,
        process_role: str | None,
    ) -> bool:
        """Set a contact's process role → user_authored (S103w, D227)."""
        ...

    async def add_capture_source(
        self, *, tenant_context: TenantContext, contact_id: UUID, channel: str
    ) -> bool:
        """Add a channel to a contact's capture_source set (S103x, D230)."""
        ...

    async def backfill_capture_source(
        self, *, tenant_context: TenantContext
    ) -> int:
        """Backfill scalar capture_source to single-element lists (S103x, D230)."""
        ...

    async def set_qualification_field(
        self, *, tenant_context: TenantContext, opportunity_id: UUID,
        field_key: str, value: str | None, touch_only: bool = False,
    ) -> bool:
        """Set a qualification field's value + last_touched, or bump only the
        timestamp when ``touch_only`` (S103w, D228/D229). A saved value clears any
        JD-extracted draft (S103ad/D236)."""
        ...

    async def set_qualification_draft(
        self, *, tenant_context: TenantContext, opportunity_id: UUID,
        field_key: str, value: str | None,
    ) -> bool:
        """Set or clear a qualification field's JD-extracted draft (S103ad/D236)."""
        ...

    async def set_opportunity_job_description(
        self, *, tenant_context: TenantContext, opportunity_id: UUID, text: str,
    ) -> bool:
        """Store the pasted job-description text on the opportunity (S103ad/D236)."""
        ...

    async def set_opportunity_match(
        self, *, tenant_context: TenantContext, opportunity_id: UUID,
        result_json: str, fit_tier_suggested: str | None, inputs_hash: str,
    ) -> bool:
        """Store the leg-3 match result on the opportunity (S103ag, D239) —
        schemaless props (coverage JSON, fit-tier suggestion, input fingerprint, run
        instant); never touches ``fit_tier``."""
        ...

    async def set_opportunity_fit_tier(
        self, *, tenant_context: TenantContext, opportunity_id: UUID, fit_tier: str,
    ) -> bool:
        """Promote the match's suggestion to the operator's ``fit_tier`` (S103ag,
        D239) — the accept path, a targeted SET."""
        ...

    async def read_opportunity_match(
        self, *, tenant_context: TenantContext, opportunity_id: UUID,
    ) -> dict | None:
        """Read the stored match + the current selection criteria (S103ag, D239) for
        the on-demand match read + staleness recompute."""
        ...

    async def list_contacts(
        self, *, tenant_context: TenantContext
    ) -> Sequence[ContactRecord]:
        """The tenant's contacts (D222) — read for the derive, the proof surface, and
        a lead's inline contacts."""
        ...

    async def confirm_contact(
        self, *, tenant_context: TenantContext, contact_id: UUID
    ) -> bool:
        """Confirm a system-suggested contact → user_authored (D222/D215)."""
        ...

    async def enrich_contact(
        self, *, tenant_context: TenantContext, contact_id: UUID,
        degree: str | None, strength: str | None, reachability: str | None,
    ) -> bool:
        """Enrich a contact with degree/strength/reachability (D222) — also flips
        provenance to user_authored (the operator authors the relationship)."""
        ...

    async def delete_contact(
        self, *, tenant_context: TenantContext, contact_id: UUID
    ) -> bool:
        """Reject (delete) a contact (D222/D215) — the user-initiated delete."""
        ...

    # --- Skills profile (S103af, D238) -------------------------------------

    async def merge_skill_item(
        self, *, tenant_context: TenantContext, item_id: UUID, kind: str,
        text: str, proof_state: str, provenance_origin: str,
    ) -> None:
        """Idempotently MERGE a :SkillItem (D238) — one entry in the operator's skills
        profile, drafted 'suggested' by CV extraction or hand-added 'confirmed'."""
        ...

    async def list_skill_items(
        self, *, tenant_context: TenantContext
    ) -> Sequence[SkillItemRecord]:
        """The tenant's skill-profile items (D238) — read for the proof surface and
        the leg-3 fit read."""
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

    async def delete_skill_item(
        self, *, tenant_context: TenantContext, item_id: UUID
    ) -> bool:
        """Reject (delete) a skill item (D238) — the user-initiated delete."""
        ...

    async def attach_unit_to_opportunity(
        self, *, tenant_context: TenantContext, unit_id: UUID, opportunity_id: UUID
    ) -> None:
        """MERGE the BELONGS_TO membership edge (D208) — idempotent."""
        ...

    async def clear_opportunity_units(
        self, *, tenant_context: TenantContext, opportunity_id: UUID
    ) -> None:
        """Delete an opportunity's BELONGS_TO edges so a re-instantiation
        reconciles cleanly (D208)."""
        ...

    async def set_element_gate(
        self,
        *,
        tenant_context: TenantContext,
        element_kind: str,
        element_id: UUID,
        gate_id: UUID,
    ) -> bool:
        """Relocate an authored element into a gate (D207) — set its ``gate_id``,
        preserving the node, label, and provenance (the relocation carries the
        live provenance; it is not a re-authoring). Returns ``True`` when matched."""
        ...

    async def delete_authored_edge(
        self,
        *,
        tenant_context: TenantContext,
        edge_type: str,
        source_kind: str,
        source_id: UUID,
        target_kind: str,
        target_id: UUID,
    ) -> None:
        """Delete one authored edge by its endpoints (D207 — edge migration when
        an element relocates: drop the old goal-level edge, add the gate one)."""
        ...

    async def set_authored_outcome(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        expected_outcome: str,
        provenance_origin: str,
        proof_state: str,
    ) -> None:
        """Set the authored ``expected_outcome`` stance on an ``:Outcome`` node
        with its ``provenance_origin`` + ``proof_state`` (S102 draft, S103a
        author/correct) — the measurable result that means the goal is met."""
        ...

    async def accept_authored_outcome(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> bool:
        """Set the authored outcome's ``proof_state`` to ``accepted`` (the
        outcome accept path, S103a). Returns ``False`` when the goal has no
        authored outcome or is cross-tenant."""
        ...

    async def clear_authored_outcome(
        self, *, tenant_context: TenantContext, outcome_id: UUID
    ) -> bool:
        """Remove the authored outcome stance from an ``:Outcome`` node (the
        outcome reject path, S103a — the node itself, the goal, is never
        deleted). Returns ``False`` when there was none."""
        ...

    async def merge_authored_edge(
        self,
        *,
        tenant_context: TenantContext,
        edge_type: str,
        source_kind: str,
        source_id: UUID,
        target_kind: str,
        target_id: UUID,
    ) -> None:
        """Idempotently MERGE an authored causal edge (``FEEDS`` / ``INFLUENCES``,
        S102, D200) between two authored elements (or to the ``:Outcome``). Kinds
        and edge type are whitelisted; endpoints must already exist."""
        ...

    async def read_authored_cdd(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
    ) -> AuthoredCddRecord:
        """Read a goal's authored CDD — its elements (with origin + proof state)
        and authored edges — for proof review (S102, D200)."""
        ...

    async def set_authored_proof_state(
        self,
        *,
        tenant_context: TenantContext,
        element_kind: str,
        element_id: UUID,
        proof_state: str,
    ) -> bool:
        """Set an authored element's ``proof_state`` (the accept path, S102).
        Returns ``True`` when an element was updated, ``False`` when absent or
        cross-tenant."""
        ...

    async def set_authored_label(
        self,
        *,
        tenant_context: TenantContext,
        element_kind: str,
        element_id: UUID,
        label: str,
    ) -> bool:
        """Edit an authored element's ``label`` and flip its
        ``provenance_origin`` to ``user_authored`` (the correct path, S102/D200).
        Returns ``True`` when updated, ``False`` when absent or cross-tenant."""
        ...

    async def delete_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        element_kind: str,
        element_id: UUID,
    ) -> bool:
        """Remove an authored element and its authored edges (the reject path,
        S102) — a user-initiated delete (allowed; the no-auto-deletion invariant
        forbids *auto* deletion, not user-asked removal). Returns ``True`` when an
        element was removed."""
        ...

    async def reclassify_authored_element(
        self,
        *,
        tenant_context: TenantContext,
        from_kind: str,
        to_kind: str,
        element_id: UUID,
    ) -> bool:
        """Reclassify an authored element across types (D201, S103a): swap the
        type-label preserving the node and its stable id, flip the origin to
        ``user_authored``, and flag (never drop) any incident edge the new kind
        makes ungrammatical. Returns ``False`` when absent or cross-tenant."""
        ...


__all__ = [
    "AuthoredCddRecord",
    "AuthoredEdgeRecord",
    "AuthoredElementRecord",
    "ContactRecord",
    "GateRecord",
    "LeverEdgeRecord",
    "OpportunityRecord",
    "OutcomeGraphPort",
    "OutcomeGraphRecord",
    "SkillItemRecord",
]
