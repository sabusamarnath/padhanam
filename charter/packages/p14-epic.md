# P14 Epic — ConversationFlow implementers (audit-conversation + mirror-conversation)

## Scope

P14 commits two ConversationFlow implementers at Phase 2-A:

1. **Audit-conversation** (per 5.1) at `contexts/audit_conversation/`. Inbound user query against the audit chain; classified into audit query intent types; the cell composes an `AuditEventListFilters` DTO from the classified intent and consumes the existing `AuditEventReader` port from S36 to execute the query against the audit chain Postgres adapter; response composed with citations per D131/D138.
2. **Mirror-conversation** (per 4.1) at `contexts/mirror_conversation/`. Inbound user query against portfolio state (Case, DataPoint, future artefact types); classified into absolute or relative intents; portfolio read-side ports execute the query; drill-down navigation stateless per turn against conversation history; response composed with citations per D131/D138.

Together, P14 closes the bet's read-loop substrate. P13 closed the write-loop (manual entry cell at S46-S47); P15 lands outbound initiation plus intake-side integrations.

## Scope deferrals to P15+

The following surfaces defer to P15+ at the noted activation triggers (per the narrow-scope decision at P14 framing 2026-05-26):

- Calendar-read cells (Google, MS365): P15 framing activation per `charter/deferred-decisions.md` "Calendar-read and email-read cells at P14 versus P15+".
- Email-read cells (Gmail, Outlook): same entry, same trigger.
- Daily-briefing surface: P15 framing activation.
- Threshold-briefing surface: P15 framing activation.
- Outbound initiation (D136 Primitive 2): P15 framing activation; first instance ships outbound.

No D136 multi-channel UX primitive activates at P14. Primitives 1, 2, and 4 stay deferred at their existing triggers; Primitive 3 (PendingClarification user-scoped) stays active from S47.

## Sequencing

Two build sessions:

- **S51**: CitedResponse Protocol commit + ArtefactCitation typed value object + CellResponse refactor (ahead of the first implementer; single-file `shared_kernel/conversation_flow.py` per pre-write reconciliation Finding 2; the brief's separate AuditQueryPort + Postgres adapter + Alembic migration dropped per Finding 1 because the existing AuditEventReader from S36 carries the load); audit-conversation implementer consuming existing AuditEventReader; WhatsApp render extension; ConversationFlow contract harness extensions (CitedResponse conformance + resolution-ambiguity conformance); audit-conversation gold set at D137 substrate at the established fixtures path per Finding 3; procedural smoke.
- **S52**: Portfolio read-side ports; mirror-conversation implementer with stateless-per-turn drill-down; WhatsApp render extension; mirror-conversation gold set at D137 substrate; procedural smoke; P14 close marker.

Audit-first sequencing chosen on risk-shape grounds: audit-conversation's response shape is structurally simpler (audit events as direct citations; no novel state-machine concerns), letting the CitedResponse Protocol's correctness verify against the cleaner implementer first. Mirror-conversation introduces drill-down stateless-classification, which the audit-first sequence isolates from Protocol-shape debugging.

## Commitment inheritance

P14 inherits substantial architectural and methodology context from the convergence-plus-post-S47 arc:

- D133 (gateway-as-resolution-point; model registry; dispatch port).
- D134 (confidence-aware response composition; ConfidenceCalculator port; ThresholdResolver port; PendingClarification entity).
- D135 (domain-decides-content channel-decides-format rendering pattern).
- D136 (multi-channel UX architectural primitives; dispatch port boundary).
- D131 (provenance-aware response composition; D138's structural enforcement at the citation surface).
- D137 (intent-classification evaluation substrate; per-implementer gold sets).

Plus the S49 methodology promotions:

- Interface-versus-implementation discipline at standing pre-write reconciliation surfaces.
- Component-quality-versus-integration-smoke discipline.
- Structural-test SSOT binding.

Plus the standing pre-write reconciliation surfaces from prior methodology promotions: path-naming reconciliation (S43b); forward-commitment-evaluation (S44a); file topology budget (S44a/S44b); cross-context contract verification (S44b); scope-discipline-at-brief-authoring three modes (S49 first instance, S50 second instance, P14 framing three-modes refinement); substrate-inheritance survey (S51 framing three-instance promotion candidate).

## P14-specific architectural surfaces

Committed at framing:

- **CitedResponse Protocol at shared_kernel** (D138). Runtime-checkable Protocol; three citation tuple fields; ArtefactCitation typed value object authored fresh at S51 with discriminator (Phase 2-A union: `"case"`, `"data_point"`); single-file `shared_kernel/conversation_flow.py` per Finding 2.
- **Resolution-ambiguity routing to D134** (D139). Cross-cutting promotion of S50's pattern from implementer-specific to all ConversationFlow implementers.
- **Audit-conversation consumes existing AuditEventReader** (S36) per Finding 1. No new AuditQueryPort, no new Postgres adapter, no Alembic migration; tenant-scoping inherited structurally from the existing reader plus S36's tenant_isolation contract scenario.
- **Symmetric-with-mirror heterogeneous citations** at audit-conversation per operator architectural disposition on Finding 4. The `cited_artefacts` tuple surfaces every entity referenced by cited audit events (Case plus DataPoint citations) rather than only the queried entity. Render-layer decoupling improves; refactor consolidates at S51 not S52.
- **Mirror drill-down stateless-per-turn**. Conversation history as classifier context; no new persisted state entity at P14; activation trigger recorded at deferred-decisions for state entity if dogfooding surfaces brittleness.
- **Audit-event citation closure** of S46's empty-field gap on the read-side at audit-conversation's natural composition.

## Acceptance criteria for P14 close

At P14 close (S52 close):

1. CitedResponse Protocol structurally enforced; three implementers satisfy (CellResponse refactored at S51 commit 2; AuditConversationResponse from S51; MirrorConversationResponse from S52).
2. ConversationFlow contract harness verifies CitedResponse conformance and resolution-ambiguity routing for all three implementers.
3. Meta-classifier dispatch substrate operational (D140); three-way classification (plus dispatch_clarification) with confidence-aware composition routing.
4. PendingClarification target_cell field operational (D140); active-pending routing consults the field.
5. Message cell_payload field operational (D141); mirror-conversation persists current_focus_artefact for drill-down extraction.
6. Audit-conversation gold set, mirror-conversation gold set, and meta-classifier gold set all operational at D137 evaluation substrate (at `tests/fixtures/intent_classification/`; `INTENT_CLASSES` and `INTENT_SURFACES` extended per S52 commits 5 and 9).
7. Procedural smokes for audit-conversation (S51) and three-cell dispatch with mirror-conversation (S52) executable against tenant_a.
8. Charter touch-points updated across S51 and S52: D138, D139, D140, D141, architecture.md prose, packages.md revision, deferred-decisions.md updates, p14-epic.md, schema.md PendingClarification section plus target_cell plus cell_payload rows, captures.md entries.
9. Phase 2-A close criterion progress: read-loop substrate complete; operator dogfooding loop extends to read-side queries (audit and mirror) plus dispatch routing across three cells.

## S52 commit shape

Twelve commit-shaped units (Alembic numbering bumped to 0023 / 0024 at pre-write reconciliation Finding 1 because S48b's intent_class_eval_substrate already holds 0022):

1. Charter commit: D140 (meta-classifier dispatch routing with PendingClarification target_cell extension) + D141 (ConversationFlow cell-payload persistence) + architecture.md additions (meta-classifier dispatch + target_cell + cell_payload + mirror-conversation context + mirror-conversation drill-down extraction sub-sections) + schema.md additions (PendingClarification full section since the S47 hygiene gap; target_cell column; cell_payload column on messages; cell_payload field on Message dataclass) + packages.md P14 line revision (CLOSED marker) + deferred-decisions.md updates (drill-down state-entity S52 build evidence; multi-channel UX P14 close confirmation; D137 substrate parameterisation S52 exercise; new cell-payload schema registry entry) + p14-epic.md (this update) + captures.md entries (five new) + current-package.md in-flight marker + brief preserved at `briefs/p14/s52.md`.
2. Alembic 0023: PendingClarification target_cell extension.
3. Alembic 0024: Message cell_payload extension.
4. MetaClassifier port + LiteLLM adapter + deterministic rule-based adapter at messaging context.
5. Meta-classifier gold set at parameterised D137 substrate (third instance).
6. dispatch_inbound use case + webhook handler refactor.
7. MirrorPortfolioReader consumer port + cross-context wiring adapter.
8. Mirror-conversation cell + intent VOs + response value object + drill-down resolution + cell_payload persistence.
9. Mirror-conversation gold set at parameterised D137 substrate (fourth instance).
10. WhatsApp render extension for MirrorConversationResponse.
11. ConversationFlow contract harness extensions (mirror-conversation registration).
12. Procedural smoke + session log + current-package transition + P14 close marker.
