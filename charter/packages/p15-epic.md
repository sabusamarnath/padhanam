# P15 Epic — Outbound initiation plus intake-side integrations

## Scope (medium)

P15 commits three substrate areas at Phase 2-A:

1. **Outbound initiation substrate.** BroadcastFlow Protocol (D142); BroadcastDispatch substrate (D143); ChannelResolver Protocol with static-config adapter (D144); HTTP trigger endpoint (D145). Two BroadcastFlow implementers: daily-briefing (S54) and threshold-briefing (S57). One non-user-facing BroadcastFlow implementer: ThresholdEvaluator (S57) for periodic state-change matching.

2. **Calendar-read substrate and cell.** `contexts/calendar/` bounded context (S55) consuming Nango self-hosted via HTTP adapter per D14 separate-service pattern. `contexts/calendar_conversation/` ConversationFlow implementer (S55) with calendar intent classification, cell logic, response composition. Calendar-conversation gold set authored at S55.

3. **Email-read substrate and cell.** `contexts/email/` bounded context (S56) consuming Nango via HTTP adapter symmetric to calendar. `contexts/email_conversation/` ConversationFlow implementer (S56) with email intent classification, cell logic, response composition. Email-conversation gold set authored at S56.

Plus cross-cutting extensions: MetaClassifier from D140 extends to five-way routing (manual_entry, audit_conversation, mirror_conversation, calendar_conversation, email_conversation); meta-classifier gold set extends correspondingly at S55 and S56. ArtefactCitation discriminator from D138 extends to four artefact types (Case, DataPoint, Meeting, Email).

## Scope deferrals to P16

The following surfaces defer to P16 at the noted activation triggers:

- 1.1 Slack messaging trio: P16 framing activation; D136 Primitive 1 User aggregate root activation trigger fires here per second-channel commitment.
- 2.1 methodology library activation (matching, recommendation, adaptation flows): P16 framing activation.
- 3.1 Surfacing mechanics: P16 framing activation.
- 1.5 user-authored items: P16 framing activation.
- 3.2 drop-decision support: P16 framing activation.

Phase 2-A close criterion (operator dogfooding instance complete across at least one week of real use; senior-leader ICP test condition validated) achievable at P15 close; P16 extends the Phase 2-A surface coverage.

## Sequencing

Five build sessions estimated:

- **S53**: BroadcastFlow Protocol plus BroadcastDispatch substrate plus ChannelResolver Protocol plus reactive outbound refactor. Foundational substrate; subsequent sessions consume.
- **S54**: HTTP trigger endpoint per D145 (architecture committed at S53; code lands here) plus daily-briefing BroadcastFlow implementer. First end-to-end broadcast. **Closed 2026-05-28** with D146 (daily-briefing composition pattern with DailyBriefingReader consumer port) and D147 (fired_triggers table with race-safe idempotency at HTTP trigger endpoint); seven commits; fired_triggers table operational via Alembic 0025; FireTrigger use case implements the seven-step endpoint flow; contexts/daily_briefing/ bounded context registered against BroadcastFlow registry with trigger_type=DAILY_SCHEDULED.
- **S55**: `contexts/calendar/` bounded context plus `contexts/calendar_conversation/` ConversationFlow implementer plus calendar-conversation gold set plus meta-classifier gold-set extension (calendar-shaped entries) plus MetaClassifier four-way routing extension. **Split into S55a (calendar data substrate) + S55b (calendar conversation).** **S55a closed 2026-05-28** with D148 (calendar protocol/auth/scope + substrate-inheritance survey result); eight commits; `contexts/calendar/` bounded context with the Connection model (opaque Nango ref), the single NangoProxyCalendarAdapter behind CalendarEventSourcePort, the Meeting event-id-keyed mutable-cache store (Alembic 0026; P3-encrypted content; vector(768)), the trigger-agnostic sync_calendar pull-store-sync pipeline (self-driven tokens, 410 resync), the indexing-per-survey seams (inherits ChunkEmbedderPort + GraphRepositoryPort via consumer ports), and the Meeting discriminator on ArtefactCitation. **S55a-fix (2026-06-02) lands D149**, correcting D148's sync mechanism: the live Stage-1 smoke falsified the assumption that a bounded full sync returns `nextSyncToken` (Google emits it only on an unbounded sync), so calendar sync at Phase 2-A is **scoped full-pull per refresh carrying `showDeleted=true`**, and the incremental `list_events_incremental` / 410-resync / `connections.sync_token` machinery is built but **dormant** with the activation trigger named in D149. The 376 ms scoped-pull latency floor is confirmed for S55b's tiering. **S55b is split into S55b-1 + S55b-2.** **S55b-1 (closed 2026-06-03)** built the calendar conversation surface standalone: the `calendar_conversation` ConversationFlow implementer, refresh-before-answer (D150 Option A), the apps indexing-and-sync wiring bridge deferred from S55a, the calendar-conversation gold set + `INTENT_CLASSES`/`INTENT_SURFACES` extension, and CitedResponse + resolution-ambiguity contract conformance; it opened with a clean-bytecode enforcement hardening. Close smoke ran live (stages 1/3/4 green; cancellation tombstone operator-gated). **S55b-2 (closed 2026-06-02; S55b complete)** carried dispatch integration and closed S55b: the MetaClassifier four-way routing extension to `calendar_conversation` with live dispatch wiring, the four-way routing gold set, the citation-time audit-snapshot evidence (D148 option b; calendar-local first mutable-source case, D21-envelope-encrypted so no plaintext reaches the audit after_state), four-way + citation-snapshot contract conformance, the S55b-1 charter carryovers (D47 provenance, D150 floor, captures), and the dispatch-through smoke (procedural, pending operator run). 2110 tests green; 38 contracts kept. S55b builds the conversation surface, the MetaClassifier four-way extension, the two gold sets, the citation-time audit-snapshot wiring, the apps/ indexing wiring bridge, and the refresh-before-answer tiering.
- **S56** (split into S56a + S56b, mirroring S55): **S56a (closed 2026-06-02; measurement operator-gated)** the email data substrate — `contexts/email/` (Gmail-API-via-Nango google-mail, two-call N+1 adapter, Email artefact + encrypted store + `email_chunks` store, `sync_email` full-pull-only with set-diff deletion, body chunking via email-local chunker + inherited embedder, `history_id` dormant anchor) per D151, plus the measured volume + full-pull floor that decide the deferred sync-mechanism and refresh-strategy framing; `KNOWN_ARTEFACT_TYPES += "email"`. **S56b** the `contexts/email_conversation/` ConversationFlow implementer, the email-conversation gold set, the meta-classifier gold-set extension (email-shaped entries), and the MetaClassifier **five-way** routing extension.
- **S57**: ThresholdEvaluator BroadcastFlow implementer plus threshold-briefing BroadcastFlow implementer plus P15 close marker. ThresholdEvaluator polls audit chain for state-change matches against configured rules; threshold-briefing fires on `THRESHOLD_CROSSED` triggers.

Substrate-foundation-first sequencing chosen because subsequent session implementers consume the substrate; building substrate ahead allows sessions to focus on implementer logic without substrate distractions.

## Commitment inheritance

P15 inherits substantial architectural and methodology context from P14 close and prior packages:

- D138 (CitedResponse Protocol; BroadcastResponse satisfies structurally).
- D139 (resolution-ambiguity routing; new cells inherit).
- D140 (meta-classifier dispatch; extends to five-way routing at P15).
- D141 (cell-payload persistence; generalizes to calendar and email cells).
- D14 (separate-service for calendar and email tools; activated at P15).
- D136 Primitive 2 (channel preference for outbound; activates at S53 with degenerate-static implementation).

Plus methodology promotions:
- Interface-versus-implementation discipline at standing pre-write reconciliation surfaces.
- Component-quality-versus-integration-smoke discipline.
- Structural-test SSOT binding.
- Substrate-inheritance survey at framing altitude (S52 first instance; P15 framing exercised three times).
- Schema.md hygiene check at charter authoring (S52 close methodology candidate).

## P15 close criteria

At P15 close (S57 close):

1. BroadcastFlow Protocol structurally enforced at shared_kernel; three implementers register (daily-briefing, threshold-briefing, ThresholdEvaluator).
2. ChannelResolver Protocol operational; static-config adapter at Phase 2-A.
3. HTTP trigger endpoint operational; external scheduler hits endpoint successfully; `BROADCAST_INITIATED` audit events chain correctly.
4. Calendar-conversation and email-conversation ConversationFlow implementers operational; meta-classifier five-way routing functional; both gold sets at parameterised D137 substrate.
5. Calendar and email contexts consume Nango self-hosted via HTTP adapter; pull-on-demand sync verified end-to-end.
6. ArtefactCitation discriminator extended to four types; existing implementers refactor without shape change.
7. Procedural smokes for substrate (S53), daily-briefing (S54), calendar (S55), email (S56), threshold-briefing (S57) all green against tenant_a.
8. Charter touch-points updated at each session: D-entries, architecture.md, schema.md (where applicable), deferred-decisions.md, packages.md, p15-epic.md.
9. Phase 2-A close criterion: dogfooding-ready substrate complete; operator can dogfood across one week of real use using outbound initiation plus calendar/email intake plus existing manual_entry/audit/mirror conversation surfaces.

## P15-specific architectural surfaces

Committed at framing:

- BroadcastFlow Protocol parallel to ConversationFlow (D142).
- BroadcastDispatch substrate with two trigger sources (D143).
- ChannelResolver Protocol with static-config adapter at Phase 2-A (D144).
- HTTP trigger endpoint substrate (D145; code at S54).
- Two new ConversationFlow implementers (calendar-conversation, email-conversation) following the audit-conversation/mirror-conversation precedent.
- Two new bounded contexts at the cell layer (`contexts/calendar_conversation/`, `contexts/email_conversation/`) plus two new bounded contexts at the substrate layer (`contexts/calendar/`, `contexts/email/`).
- D138 ArtefactCitation discriminator extension to four artefact types (Case, DataPoint, Meeting, Email).
- D140 MetaClassifier extension from three-way to five-way routing.
- Operator-tool-service-sourcing: self-hosted Nango under Elastic License as parallel infrastructure work outside Padhanam's package boundary but prerequisite for live dogfooding.
