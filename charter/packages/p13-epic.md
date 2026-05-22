# P13 Epic — Foundational substrate (Phase 2-A Wave 1)

## Framing lens: the three-mode picture

Padhanam's Private Assistant Platform operates in three modes that share one substrate.

**Attentional mode.** Threshold briefings that prime the user's attention before they enter a context. Declarative. No action required. The assistant tells the user what is, not what to do.

**Workflow mode.** The assistant does tasks on request: drafts emails, sets up calls, runs methodologies. Permission moments are gated. The user asks, the assistant executes.

**Observation-and-suggestion mode.** The assistant quietly tracks the user's world (calendar, email, messages, to-do app) and notices gaps. Gaps surface as offers phrased as questions: "I haven't seen anything to suggest you reached out to Nestor. Want me to draft an email?" Yes runs workflow mode. No backs off. The mode depends on an established trust relationship.

The platform's positioning is meta-layer over the user's existing apps. Calendar apps stay the calendar. To-do apps stay the to-do list. Email clients stay the email client. The platform reads from these for observation and writes to them on request, but does not duplicate their function. The platform does not do reminders.

## Package goal

P13 delivers the foundational substrate that all three modes share at Phase 2-A. At P13 close, the operator can manually enter portfolio state through Twilio Sandbox messaging, state persists across sessions, the Revisable Protocol holds for entities the operator updates, and the substrate supports forward extension to Wave 2's observation and methodology work without major refactor.

P13 is the first Phase 2-A wave. It commits foundational charter additions (Revisable Protocol, ConversationFlow Protocol, three architecture primitives, no-silent-operation principle, PA communication discipline principle) and the substrate that those commitments operate on.

## Package contents

Six committed work-streams from the Phase 2 design 7-Step Step 6 commitment set:

- **State persistence (sub-problem 1.3).** Per-tenant persistence of the foundational domain entities. Survives session boundaries. Substrate for every later wave.
- **Manual entry cell (sub-problem 1.1, first messaging cell).** The operator types portfolio state into a Twilio Sandbox WhatsApp message; the platform parses, validates, persists. The first end-to-end exercise of the substrate.
- **Latency-tier routing extension at the LiteLLM port (D122).** Hint vocabulary that lets each call site declare its latency preference. The LiteLLM port resolves the hint to a routing decision.
- **Twilio Sandbox setup plus messaging adapter scaffold (D119).** Sandbox account configured; webhook endpoint receives inbound messages; outbound send works; the adapter implements the messaging port interface.
- **Revisable Protocol definition (D114).** The shape contract for entities that revise rather than overwrite. Implementations land at P14 and beyond; P13 commits the shape and applies it to state-persistence entities.
- **ConversationFlow Protocol definition (D115).** The shape contract for multi-turn interactions that resolve revisions and clarifications. Implementations land at P15 and beyond; P13 commits the shape.

Six build-now forward-compat substrate items per Decision 7:

- **Structured output object.** A first-class entity at the LLM port boundary. Phase 2-A reads structured JSON; substrate supports tool-call structures and refusal envelopes without later schema break.
- **ActorContext extension.** Schema extension to the existing TenantContext shape adding actor identity, role list, and authorisation set. Used by every use case from P13 onward.
- **Authorisation decorator.** Enforced at the use case boundary. Phase 2-A populates with operator-role-only checks. Substrate supports role hierarchy as a pure extension at activation.
- **Four-layer model ontology shape (Provider, Account, Version, Configuration).** Naming and substrate at the LiteLLM port. No catalogue UX at P13. Touching the port for D122 makes the naming cheap to land now.
- **Intake record.** First-class entity captured before any execution path runs. P13's manual entry is an intake path; P14's calendar-read and email-read are intake paths. Intake records are the canonical boundary of incoming work.
- **Case plus Data Point plus Assertion naming alignment.** Domain entities at substrate level. Portfolio item at 1.3 maps to Case. Goals, statuses, methodology applications are Data Points. Revisable Protocol revisions are Assertions. Naming aligns with the karma prior-art vocabulary.

Three architecture primitive commits (charter additions at architecture.md; implementation exercised at later waves):

- **Tiered-by-salience (D117).** Surfacing primitive. P15 implements.
- **Two-vector decay (D118).** Surfacing primitive. P15 implements.
- **Three-tier consent-and-awareness (D116).** Consent primitive. P14 implements through the Gate entity (Gate entity itself defers from P13 to P14 per Decision 7 placement revision).

Two charter principle commits:

- **No-silent-operation (D121).** Already committed in principles.md at Step 7 close; P13 honours the principle in implementation.
- **PA communication discipline (new principle at P13).** Declarative not imperative; suggestion-as-question; subtle not pushy; specific over generic; visible reasoning; no compliance language.

One charter-only hygiene item bundled into a pre-P13 session per Decision 2:

- schema.md formalisation (P13 commits new schema entries; formalising schema.md ahead of those commits reduces formalisation cost later).
- doc-content rebrand (former-platform-name find-replace across stale references).

## Substrate-to-mode mapping

- **State persistence** serves all three modes. Memory is the moat.
- **Manual entry cell** serves workflow mode at P13. Observation mode reads from the same persistence layer at P14.
- **Messaging substrate (Twilio Sandbox plus adapter)** serves all three modes. Threshold briefings, workflow responses, and suggestion-as-question all flow through messaging at Phase 2-A.
- **Latency-tier routing** serves all three modes by routing each call to the model class its latency tolerance allows.
- **Revisable Protocol** serves workflow mode (revisable assertions about state) and observation mode (revising what the platform thinks happened).
- **ConversationFlow Protocol** serves all three modes. Multi-turn clarification matters most in suggestion mode (the user accepts or declines an offer; the protocol carries the exchange).
- **Structured output object** serves workflow mode primarily.
- **ActorContext** serves workflow mode (who is acting) and observation mode (who is the observer).
- **Authorisation decorator** serves workflow mode primarily.
- **Four-layer model ontology shape** serves all three modes as the model selection substrate.
- **Intake record** serves observation mode primarily; workflow mode at the point a request enters.
- **Case, Data Point, Assertion** serve all three modes as the domain vocabulary.

## Session forecast

Four sessions per Decision 3 (a') with the fourth shaped as a bridge session.

**Session 1 (S43): foundational domain layer.** The `contexts/portfolio/` bounded context — name settled at the S43 brief over `state_persistence` (karma portfolio-of-relationships vocabulary; PORTFOLIO_ITEM case_type; symmetry with the domain-named P11 contexts). Case/DataPoint/Assertion entities and three per-tenant tables (D124); the Revisable Protocol shape as a generic `Protocol` in `shared_kernel/` (D125; D114 committed the framework). D124 and D125 land as separate entries. Read-side HTTP plus a `padhanam portfolio` CLI write path for the live-stack smoke; write-side HTTP defers to S44. The no-silent-operation and PA communication discipline principles landed earlier at the P13 framing landing commit, not this session. Ten commits.

**Session 2 (S44a): identity-and-permissions substrate.** ActorContext shared-kernel value object as a compose-shape envelope wrapping TenantContext; authorisation decorator at the use-case boundary with AuthorisationDenied translation to 403; the five portfolio use cases updated to consume ActorContext and apply the decorator; ActorReference retained as the persisted authoring-identity value object (D126 supersedes D124's forward commitment that `authored_by` becomes ActorContext — a single persisted text column cannot round-trip a request-scoped authorisation envelope). The D116 three-tier consent-and-awareness architecture-primitive prose already landed at the P13 framing landing commit; no architecture.md edit at S44a. Estimated 8 commits. (As-built: the framing nine-commit estimate dropped to eight at S44a pre-write reconciliation when the ActorReference-deletion commit fell away.)

**Session 2b (S44b): write-path substrate and transport with intake-canonical orchestration.** New `contexts/intake/` bounded context — IntakeRecord aggregate root with IntakeSource enum and ManualEntryPayload value object; repository port plus Postgres adapter; Alembic 0017 substrate migration plus 0018 intake_id additions to cases and assertions; three standalone intake use cases plus three cross-context orchestration use cases (record_intake_and_create_case, record_intake_and_create_data_point, record_intake_and_revise_data_point) at the intake context's application layer, depending on a consumer-defined `PortfolioWriter` port. Write-side HTTP routes for portfolio (POST `/api/v1/cases`, POST `/api/v1/data_points`, PATCH `/api/v1/data_points/{id}`) invoking the orchestrations. Intake HTTP routes (POST `/api/v1/intakes`; GET single and list surfaces). CLI write path updated to invoke the orchestrations. Two D-entries: D127 (intake substrate plus orchestration) and D128 (intake-canonical commitment as cross-context posture). Twelve commits. (Numbered "2b" rather than "Session 3" to avoid colliding with the existing Session 3 messaging line below; S44 split into S44a/S44b per the planned-bridge sub-variant. As-built: the framing eleven-commit estimate grew to twelve at S44b pre-write reconciliation when the create_data_point write-surface gap surfaced a third orchestration.)

**Session 3 (S45): messaging substrate plus ConversationFlow Protocol plus structured-output shared kernel.** New `contexts/messaging/` bounded context — Message aggregate root with MessageDirection / MessageChannel / MessageStatus enums (WhatsApp at Phase 2-A per D119); MessageRepository and MessageDeliveryPort; four use cases; TwilioMessageDeliveryAdapter plus LocalEchoMessageDeliveryAdapter; Postgres persistence; Alembic 0019 messages table plus 0020 intake_source WHATSAPP_INBOUND extension. Inbound-as-intake-orchestration via `record_intake_and_record_inbound_message` at the intake context per D127 alternative (d), with a MessageWriter consumer port. ConversationFlow Protocol shape at `shared_kernel/conversation_flow.py` with five value objects (landing D115 directly; no separate shape D-entry) plus a contract harness with no implementers at S45. Structured-output discipline at `shared_kernel/structured_output.py` with StructuredOutputRequest / StructuredOutputResponse[T] / StructuredOutputPort; the inference adapter extended to implement the port; a contract harness with the inference adapter as first implementer. HTTP routes for messaging including the Twilio WhatsApp webhook receiver with X-Twilio-Signature verification. D129 messaging substrate, D130 structured-output discipline, D131 provenance-aware response composition. The architecture-primitive prose for D117 (tiered-by-salience) and D118 (two-vector decay) verified already-landed at P13 framing; no architecture.md edit for them at S45. The original framing forecast of 7-to-9 commits revised to 13 at the updated brief. (As-built scope per `briefs/p13/s45.md`, the updated brief superseding the original 284-line draft.)

**Session 4: end-to-end exercise (bridge session).** Manual entry cell (1.1 first messaging cell); latency-tier routing at the LiteLLM port (D122); four-layer model ontology shape commit. End-to-end demonstration: operator sends a portfolio update via Twilio Sandbox, the platform parses through the manual entry cell, persists through state persistence, returns a structured confirmation through the messaging adapter. Estimated 5 to 7 commits.

Total P13 forecast: 25 to 33 commits across four sessions.

## D-entry forecast

Seven to twelve new D-entries surface during implementation. Likely candidates:

- State persistence schema (likely one D-entry).
- Revisable Protocol shape (one D-entry; D114 already commits the framework, this commits the shape).
- ConversationFlow Protocol shape (one D-entry; same pattern as Revisable Protocol).
- Messaging adapter shape (one D-entry covering the Twilio integration boundary).
- Latency-tier hint vocabulary (one D-entry; D122 commits the routing decision, this commits the vocabulary).
- Manual entry cell discipline (one D-entry).
- ActorContext extension shape (one D-entry).
- Authorisation decorator shape (one D-entry; may bundle with ActorContext).
- Four-layer model ontology shape commitment (one D-entry).
- Intake record shape (one D-entry).
- Case/DataPoint/Assertion naming and shape (one D-entry; may bundle with state persistence schema).

Final D-entry count settles during build. Some candidates bundle; some warrant standalone entries.

## Out of scope explicitly

The following are deferred to later waves or later phases. Each is cross-referenced to the deferred-decisions entry or the spec section the deferral applies to.

- **Gate entity and its state machine.** Defers to P14 alongside the first consent-requiring code path (5.4 intelligence-layer guardrails).
- **Methodology-as-workflow data model with steps and signals.** Defers to P14 alongside 2.1 methodology library core.
- **Governance artefact hierarchy shape (Platform / Organisation / Workspace / Agent inheritance).** Defers to P14 alongside governance work.
- **Workspace abstraction within tenant.** Cross-reference to the forkable-versus-non-forkable deferred-decisions entry. Activation trigger: commercial deployment direction commits a customer-organisation buyer model.
- **Role hierarchy with inheritance machinery.** Activation trigger: Phase 2-B or Phase 3+ adds a second role beyond operator.
- **Environment and Promotion abstractions.** Cross-reference to the production-deployment-infrastructure deferred-decisions entry. Activation trigger: Phase 2-B production-deployment infrastructure work.
- **Webhook and outbound API.** Cross-reference to the external-integration-consumer deferred-decisions entry. Activation trigger: external integration consumer arrives.
- **Trials (active testing scheduler revival).** Cross-reference to the deferred entry. Activation trigger: Phase 2-B+ per D92.
- **Browser-based authentication substrate.** Defers to Phase 2-B framing per Decision 1 revised disposition. Phase 2-A ships no browser surface.
- **Frontend stack confirmation.** Defers to Phase 2-B framing per Decision 1 revised disposition. Vite as the build-tool commitment when web surfaces ship; framework choice defers to Phase 2-B framing.
- **Customer-organisation role hierarchy beyond operator.** Defers to Phase 2-B+ or Phase 3+. The karma spec's enterprise-scale role surface is out of scope for Phase 2-A.
- **SPA frontend (Studio, Portal, Canvas, My Tasks).** Defers to Phase 2-B+ web surface delivery. Phase 2-A messaging-first delivery has no SPA.

## Open questions surfaced at framing

**Principal polymorphic shape verification.** Resolved at framing. The current S34/S37/D103 principal shape uses a discriminator field (`PrincipalType` StrEnum with TENANT and PLATFORM_OPERATOR variants) and is already polymorphic and extensible. Adding a third principal type (machine-actor for API callers) at Phase 2-B+ is additive: a new StrEnum value plus a new dependency resolver path. Existing call sites remain unchanged. Classification holds at defer-with-trigger.

**Which to-do app does the operator use?** Settles at P14 framing. The first to-do app integration ships at P14 Wave 2 alongside calendar-read cells per the operator-as-first-user constraint.

**Daily briefing email scope.** Settles at P15 framing. Classified as Kano performance attribute (nice-to-have). Surfaces at P15 if observation and suggestion engines are operational; earlier if P14 close shows it would materially shape rhythm.

## Forward-compat substrate-depth classification table

Phase 2-A-wide scope. Each item classified into one of three categories. The ships-at column names which package builds the item.

### Build now (deferral forces major refactor)

| Item | Ships at | Cost-now versus cost-later reasoning |
|---|---|---|
| Structured output object | P13 | LLM port touched at D122; adding structured output as first-class entity now avoids schema break when tool-call structures arrive at P14+. |
| ActorContext extension | P13 | Used by every use case from P13 onward. Cost now: schema and signature change at one altitude. Cost later: touching every use case signature plus every authorisation check site. |
| Authorisation decorator | P13 | Same logic as ActorContext. Trivial check at one boundary now versus retrofit across every use case later. |
| Four-layer model ontology shape | P13 | D122 latency-tier extension already touches the LiteLLM port. While touching it, the four-layer naming is cheap. Cost now: naming and substrate shape. Cost later: refactor the model port and call sites. |
| Intake record | P13 | P13 manual entry and P14 calendar/email reads are ingestion paths. Adding intake record now is cheap (it is the boundary of work already being done). Cost later: retrofit ingestion paths across multiple sub-problems. |
| Case, Data Point, Assertion naming alignment | P13 | Substrate already exists implicitly: portfolio item maps to Case; goals/statuses/methodologies are Data Points; revisions are Assertions. Cost now: naming alignment with spec vocabulary plus making entities first-class. Cost later: refactor persistence to extract entities from portfolio-item-as-monolith. |
| Gate entity (state machine, signatory rule abstraction) | P14 | First consent-requiring code path arrives at P14 (5.4 intelligence-layer guardrails). Domain entity definition lands then. Cost now (at P14): single domain entity. Cost later: refactor every place that handles consent inline. |
| Methodology-as-workflow data model | P14 | P14 ships 2.1 methodology library core. Versioning via D114 already committed. Steps and signals declarations are additions at P14. Cost now: data model addition. Cost later: P18 adds the data model concurrent with agent runtime build, which is two concerns at once and risks structural drift. |
| Governance artefact hierarchy shape | P14 | P14 governance work populates the inheritance shape. Phase 2-A operates at operator-as-organisation level and single-default-workspace level. Cost now: inheritance shape commitment. Cost later: refactor every governance-config-check site to handle multi-level resolution. |

### Defer with named activation trigger

| Item | Activation trigger | Cross-reference |
|---|---|---|
| Role hierarchy with inheritance machinery | Phase 2-B or Phase 3+ adds a second role beyond operator | New deferred-decisions entry at P13 framing commit. ActorContext plus authorisation decorator substrate supports role hierarchy as pure extension. |
| Workspace abstraction within tenant | Commercial deployment direction commits a customer-organisation buyer model | Existing forkable-versus-non-forkable deferred-decisions entry. D93 keeps deferred indefinitely unless Phase 3+ surfaces commercial-deployment evidence. |
| Environment plus Promotion abstractions | Phase 2-B production-deployment infrastructure work | Existing production-deployment-infrastructure deferred-decisions entry. |
| Webhook plus outbound API | External integration consumer arrives | Existing external-integration-consumer deferred-decisions entry. Build-now HTTP surface at S34 plus S42 exposes use cases; webhook plus API extensions plug in at activation. |
| Trials (active testing scheduler revival) | Phase 2-B+ per D92 | Existing trials deferred-decisions entry. |
| Principal polymorphic shape (machine-actor variant) | API caller arrives at Phase 2-B+ | Resolved at P13 framing: current S37/D103 shape already polymorphic. New deferred-decisions entry at P13 framing commit naming machine-actor variant as additive extension. |

### Flag for future testing (build-now substrate Phase 2-A operator dogfooding does not exercise)

Each item lands as a deferred-decisions entry with activation trigger plus a Phase 2-A close audit input naming the test coverage gap.

| Item | Activation | Phase 2-A test coverage gap |
|---|---|---|
| Authorisation paths beyond operator-role check | Phase 2-B+ adds a second role | No Phase 2-A scenario trips authorisation rejection paths. |
| Governance hierarchy levels above Organisation and below default Workspace | Phase 3+ commercial deployment or Phase 2-B B9 extensions | Phase 2-A has no Platform or sub-Workspace inhabitants. |
| Multi-signatory Gate paths | Phase 2-B+ surface adds multi-actor scenarios | Phase 2-A is single-signatory. Flagged with Gate entity at P14. |
| Intake authority profiles beyond operator-authority | Phase 2-B+ adds additional intake sources with different authority profiles | Phase 2-A has no intake sources beyond operator. |
| Methodology-step-and-signal declarations beyond what P14's four methodologies populate | P17 B9 methodology authoring adds new methodology shapes | Substrate accepts more shapes than four-methodology testing exercises. Flagged with methodology-as-workflow at P14. |
| Case-DataPoint-Assertion shapes beyond portfolio-item-shaped use | Phase 2-B+ adds new domain entity types | Phase 2-A operator dogfooding generates portfolio-item-shaped Cases only. |

### Table migration trigger

If the classification table proves valuable across P14 and P15 framing, P14 framing migrates the table to a dedicated charter file (`charter/phase-2-substrate-depth.md` or similar). Migration is P14 framing's decision.

## Open thread

The forward-compat-without-major-refactor discipline holds at P13 as a first-instance build-methodology candidate. Recurrence test fires at P14 framing. Promotion to charter-methodology lands at Phase 2-A close audit if the discipline holds across multiple packages.
