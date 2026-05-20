# Phase 2 design 7-Step arc — Step 6 (Synthesise) — full commit

## Identification

Mode: strategic (charter commit; no code changes; lint and tests not required).
Block: Phase 2 design 7-Step arc — Step 6 (Synthesise) — full canonical commit landing.
Branch: operator-selected at session open.

## Goal at session close

- `charter/phase-2-design-7step.md` carries the Step 6 section at canonical altitude per Commit 1; the section structure mirrors Steps 1-5 precedent.
- `briefs/phase-2/design-7step-step-6.md` preserved (currently untracked) per Commit 1.
- `briefs/phase-2/design-7step-step-6-interim.md` carries an archive-note header per Commit 1; content preserved as historical authoring substrate.
- `charter/decisions.md` carries ten new D-entries (D114 through D123) per Commit 2.
- `charter/principles.md` carries the no-silent-operation principle addition per Commit 2.
- `charter/architecture.md` carries six architectural-primitive additions (five Phase 2-A primitives plus latency-tier inference routing) per Commit 2.
- `charter/deferred-decisions.md` carries four new deferred entries (Q8, Q9, Q10, Q12) per Commit 3.
- `charter/packages.md` carries the Phase 2 package structure (P13 through P20) per Commit 3.
- `charter/current-package.md` gains a new close marker paragraph appended after the prior marker per Commit 4.
- `briefs/phase-2/design-7step-step-6-commit.md` preserves this commit prompt verbatim per Commit 4.
- Session log entry appended to `log/sessions.md` matching the Pass 3 commit entry shape, scaled for four commits.

## Context to read first

1. `briefs/phase-2/design-7step-step-6-interim.md`. The interim record carries Pass 1 dispositions plus Pass 2 package structure plus Pass 3 storyline plus dogfooding-evidence record plus Step 7 carry-forward. Source content for the Step 6 section composition at Commit 1.
2. `briefs/phase-2/design-7step-step-6.md` (currently untracked). Step 6 brief; preserved at Commit 1.
3. `charter/phase-2-design-7step.md`. Steps 1-5 present; Step 5 close paragraph terminal. Step 6 section appends at file tail.
4. `charter/decisions.md` tail. Confirm latest D-entry number is D113; new entries land as D114 onward in the Phase 2 decisions section.
5. `charter/principles.md` User safety section (lines 56-89). New subsection lands after Content framing.
6. `charter/architecture.md` Domain primitives section (around lines 222-264). New "Phase 2 architectural primitives" section lands after Domain primitives, before the four-context substrate section.
7. `charter/packages.md`. Phase 2 packages section appends after the Phase 1 narrative line (line 20).
8. `charter/deferred-decisions.md`. New section "Phase 2 design 7-Step deferrals" appends after "Phase 2 substrate completion."
9. `briefs/phase-2/design-7step-step-6-pass-3-commit.md`. Pass 3 commit prompt as structural precedent.
10. `log/sessions.md`. Latest Pass 3 commit entry as shape precedent.

## Verify-against-current-sources

Pass 1's Q6 disposition committed WhatsApp via Twilio for Phase 2: Twilio Sandbox for Phase 2-A development and dogfooding; Twilio Production verified-business plus template-approval transition at Phase 2-B Wave 1. The D-entry text at Commit 2 names Twilio-specific product naming and WhatsApp Business Platform mechanics. Vendor naming drifts; the Pass 1 reframe was article-driven against the May 2026 state.

Before writing the D-entry for Q6 (D119 per the numbering below), reconcile the naming against Twilio's current documentation. Specifically:
- Confirm "Twilio Sandbox for WhatsApp" remains the current name for the Twilio testing surface, and confirm whether sandbox setup steps have changed since the Pass 1 reframe.
- Confirm "verified-business" plus "template-approval" terminology matches Twilio's current production WhatsApp Business Platform onboarding flow.
- Confirm Twilio's WhatsApp Business Platform offering still requires the Meta-verified business plus template-registration path.

Adjust the D-entry text if Twilio's current documentation uses different naming or sequencing. Do not silently propagate inaccuracies. The S4 Langfuse miss precedent (per the Claude.ai project instructions) warns against this shape of miss. If Twilio's offering has materially shifted since Pass 1's reframe (e.g., Twilio no longer offers the WhatsApp Business Platform path; Meta has restructured the program), flag the shift and pause Commit 2 rather than writing a D-entry that fossilises inaccurate substrate.

The other D-entries (D114-D118, D120-D123) do not name vendor specifics requiring reconciliation.

## Charter changes required this session

This commit lands the full Step 6 substantive charter additions. Four commits closing the session.

## The substantive work

### Commit 1: Step 6 section at canonical altitude plus brief preservation plus interim archive

Conventional commit message: `docs(charter): step 6 section canonical landing + brief preservation + interim archived`

Three operations.

**Operation 1a.** Append the Step 6 section to `charter/phase-2-design-7step.md`. The append lands after the Step 5 close paragraph (Step 5 close ends with the paragraph beginning "Step 6 (Synthesise) opens at a fresh Claude.ai conversation thread..." and the section terminates at the file tail).

The Step 6 section content composes from the interim record at `briefs/phase-2/design-7step-step-6-interim.md` with structural transformations: interim H2 headings (`## Pass 1`, `## Pass 2`, `## Pass 3`, `## Pass 3 close: Dogfooding-evidence record`, `## Pass 3 close: Carry-forward to Step 7`) become H3 headings nested under a new H2 `## Step 6: Synthesise`. The interim's "Methodology observation (resolved at Pass 3 close)" section does NOT appear in the canonical Step 6 section; it stays in the interim record only as historical authoring substrate.

The Step 6 canonical section structure:

````markdown
## Step 6: Synthesise

Step 6 applied the McKinsey 7-Step Synthesiser role's discipline to Step 5's findings plus the sixteen carry-forward questions. The role's function-focused system_prompt commits the role to "synthesise findings into integrated storylines; receive findings from the Analyst; identify the storyline that addresses the original problem from the ProblemFramer's framing; integrate findings into a coherent narrative with explicit logical flow; pass the storyline to the Communicator; do not produce new analyses; integrate existing ones." The McKinsey override layered "Apply pyramid principle to storyline construction." Posture 1.5 dogfooding continued from Steps 1-5.

Step 6 operated across three passes, with Pass 1 plus Pass 2 landing in one Claude.ai conversation and Pass 3 opening in a fresh Claude.ai conversation per the operator's pause-between-passes decision. The multi-conversation pattern is first-instance within the design 7-Step arc. The interim record at `briefs/phase-2/design-7step-step-6-interim.md` preserves the authoring substrate; this canonical Step 6 section is the binding record.

### Pass 1: Sixteen carry-forward question dispositions

[Content per interim file Pass 1 section, with H3 -> H4 heading nesting adjustment: `### Group (a)` becomes `#### Group (a)` etc.]

### Pass 2: Phase 2 LVT placement plus package structure

[Content per interim file Pass 2 section, with H3 -> H4 heading nesting adjustment.]

### Pass 3: Integrated storyline

[Content per interim file Pass 3 section, with H3 -> H4 heading nesting adjustment: `### Top-line answer` becomes `#### Top-line answer` etc.]

### Pass 3 close: Dogfooding-evidence record

[Content per interim file Pass 3 close dogfooding-evidence record section.]

### Pass 3 close: Carry-forward to Step 7 (Communicate)

[Content per interim file Pass 3 close carry-forward section.]

### Step 6 close

Step 6 closes with all sixteen carry-forward questions disposed (Pass 1), the eight-package Phase 2 LVT structure committed (Pass 2; P13-P20 across Phase 2-A Waves 1-4 and Phase 2-B Waves 1-4 with Cluster B9 elevated at Phase 2-B Wave 1 per Q16), the integrated storyline addressing the Step 1 problem statement landed (Pass 3; top-line plus five supporting arguments plus evidence trail plus one storyline-internal tension resolved), the sixth-instance dogfooding-evidence record at firmly-evidenced strength (six instances across six sequential roles spanning the full McKinsey 7-Step analytical arc; the strongest single piece of structural-level procurement-grade evidence accumulated through Phase 2 design), and three open questions carrying forward to Step 7 (Communicate). The Synthesiser role's discipline produced a usable storyline that respected the pyramid principle, integrated across multi-step substrate plus carry-forward dispositions plus package structure, and held the cross-conversation handoff at synthesis altitude. Plus the eight-package Phase 2 LVT structure commits at `charter/packages.md`; the six architectural primitives (revision-with-lineage, conversation flow, three-tier consent-and-awareness, tiered-by-salience, two-vector decay model, latency-tier inference routing) commit at `charter/architecture.md`; the no-silent-operation principle elevates at `charter/principles.md` User safety section; the ten D-entries (D114-D123) land at `charter/decisions.md`; four deferred-decisions entries land at `charter/deferred-decisions.md` Phase 2 design 7-Step deferrals section.

Step 7 (Communicate) opens at a fresh Claude.ai conversation thread with the integrated storyline as input plus the three Step 7 open questions (stakeholder audience; narrative density; supporting artefact set) as Communicate inputs. The Step 7 pre-conversation brief authors at `briefs/phase-2/design-7step-step-7.md` before the Claude.ai conversation opens, continuing the briefs/ discipline pattern now firmly-evidenced.
````

The content blocks `[Content per interim file ...]` indicate: copy the corresponding section verbatim from the interim record at the time of this commit (post-Pass-3-append), adjusting heading levels for nesting as named.

**Operation 1b.** Preserve `briefs/phase-2/design-7step-step-6.md` (currently untracked in the working tree). Add the file to git; no content changes. The file's content is the Step 6 brief authored pre-conversation; preservation matches the briefs/ discipline applied at Steps 1-5 briefs.

**Operation 1c.** Archive the interim record at `briefs/phase-2/design-7step-step-6-interim.md` via header addition. Prepend the following note before the existing H1 heading:

````markdown
> **Archive note.** This interim record's content landed canonically at the Step 6 section of `charter/phase-2-design-7step.md` per the full Step 6 commit (commit [SHA-of-this-commit-at-Operation-1a-completion-time]). Preserved as historical authoring substrate showing the multi-pass synthesis arc (Pass 1 plus Pass 2 in one conversation; Pass 3 in fresh conversation; cross-conversation handoff first instance). The Step 6 section at `charter/phase-2-design-7step.md` is the canonical reference; this file documents the authoring process and the Pass 3 close methodology observation resolution.

---

````

Adjust the commit SHA at write time. The note plus separator preserve the original H1 plus content unchanged below.

### Commit 2: Charter primitives — D-entries plus principles plus architecture

Conventional commit message: `docs(charter): step 6 architectural primitives + 10 D-entries (D114-D123) + no-silent-operation principle`

Three artefacts. Reconcile the Q6 D-entry (D119) against Twilio's current documentation per the verify-against-current-sources block at the top of this prompt before writing.

**(a) Append to `charter/decisions.md`** ten new D-entries (D114 through D123) under the existing `## Phase 2 decisions` heading at line 132. The entries land in the order specified; format mirrors the existing D-entry format (bold ID + title + parenthetical context).

**D114: Revision-with-lineage standard interface as Phase 2-A architectural primitive.** Revisable Protocol implemented by three contexts (portfolio per 1.3, methodology per 2.1, goal per 4.2) with per-context adapters; saturated across 2.1 methodology adaptation, 4.2 goal revision, 3.2 drop status transitions, 6.5 correction mechanics per Step 5 Pass 2 Work-stream 2 architectural patterns. CI-enforceable conformance via contract tests. Landing surfaces: architecture.md Phase 2 architectural primitives section. Kano category: must-have (procurement-grade audit-trailed defensibility per senior-leader ICP at `charter/phase-2-user-segment.md`). References D26 (append-only audit chain) and D31 (revisions pattern). (Phase 2 design 7-Step Step 6 Pass 1 Group (a) Pattern 1, [DATE])

**D115: Conversation flow standard interface as Phase 2-A architectural primitive.** ConversationFlow Protocol implemented by two contexts at Phase 2-A (audit per 5.1, portfolio mirror per 4.1) with per-context adapters; across-the-board at audit-conversation and mirror-conversation per Step 5 Pass 2 Work-stream 2. CI-enforceable conformance via contract tests. Landing surfaces: architecture.md Phase 2 architectural primitives section. Kano category: must-have (messaging-first delivery per Step 4 commitment requires conversation-shaped surfaces, not dashboard surfaces). (Phase 2 design 7-Step Step 6 Pass 1 Group (a) Pattern 2, [DATE])

**D116: Three-tier consent-and-awareness framework as Phase 2-A architectural primitive.** Tier 1 real-time review for high-danger classes; Tier 2 surfaced operation with user-controlled digest review cadence; Tier 3 silent operation does not exist (per D123 no-silent-operation principle). Tier-depends-on-initiation refinement where platform-initiated drops sit at Tier 1 while user-initiated drops follow 1.5 commit-and-notify pattern per Step 5 Pass 1 sub-problem 3.2 finding. Native specification at sub-problem 5.4 per Step 5 Pass 2 Work-stream 2 architectural patterns. Procurement-grade positioning beyond safety hygiene per May 2026 competitor research at `charter/competitors.md`. Existing principles.md consent-granularity principle stays as-is; the three-tier framework operationalises the consent-granularity-is-proportionate-to-danger principle without replacing it. Landing surfaces: architecture.md Phase 2 architectural primitives section. Kano category: must-have (audit-trailed-approval-first defensibility per senior-leader ICP). References D82 (platform invariants) and existing principles.md consent-granularity principle. (Phase 2 design 7-Step Step 6 Pass 1 Group (a) Pattern 3, [DATE])

**D117: Tiered-by-salience as Phase 2-A architectural primitive.** Six instances surfaced at Step 5 Pass 2 Work-stream 2 architectural patterns. Salience classification applies to surfacing-decision logic at 3.1, drop-suggestion triggers at 3.2, mirror-response density at 4.1, audit-narrative density at 5.1, status-veracity surface granularity at 6.3, methodology-applied importance threshold at 2.1. Salience drives per-action surface depth; high-salience surfaces receive richer treatment; low-salience surfaces receive lighter treatment. Landing surfaces: architecture.md Phase 2 architectural primitives section. Kano category: performance (richer salience treatment improves user experience without being a strict procurement gate). (Phase 2 design 7-Step Step 6 Pass 1 Group (a) Pattern 4, [DATE])

**D118: Two-vector decay model as Phase 2-A architectural primitive.** Methodology-applied calibrations stale on two orthogonal vectors: age (time-based; each methodology declares stale-after-N-time-units; RICE quarterly, LVT six-monthly, Kano roughly annual, McKinsey 7-Step faster) and information (event-driven; each methodology declares events that render its application stale for items it has been applied to). Three operator-articulated instances at Step 5 Pass 2 Work-stream 2 architectural patterns. Phase 2-A ships age-based freshness operational; information-based gets architectural commitment with Phase 2-B Cluster B3 operational delivery. Staleness produces two suggestion types: drop suggestion or rescore suggestion. Landing surfaces: architecture.md Phase 2 architectural primitives section. Kano category: performance (methodology-applied calibrations staling honestly improves judgment quality without being a strict procurement gate; becomes must-have if learned-pattern-based depth ships at Phase 2-B). References Step 5 Pass 1 sub-problem 3.2 finding. (Phase 2 design 7-Step Step 6 Pass 1 Group (a) Pattern 5, [DATE])

**D119: WhatsApp via Twilio for Phase 2 messaging-channel-and-path; Baileys excluded; Meta WhatsApp Cloud API direct deferred to Phase 3.** [VENDOR-RECONCILED TEXT PER VERIFY-AGAINST-CURRENT-SOURCES; placeholder text follows that the verification step revises if Twilio's current documentation requires.] WhatsApp messaging at Phase 2-A development and operator dogfooding lands via Twilio Sandbox for WhatsApp (Twilio's testing surface; no Meta verified-business required at sandbox stage). Phase 2-B Wave 1 transition to Twilio Production WhatsApp Business Platform with Meta-verified business plus message-template-registration completed. Baileys excluded as Meta-Terms-of-Service-incompatible (incompatible with procurement-grade audit-trailed-approval-first defensibility per the May 2026 reframe). Meta WhatsApp Cloud API direct path defers to Phase 3 as alternative path. Landing surfaces: `charter/packages.md` P13 Wave 1 names Twilio Sandbox setup workitem; P17 Wave 1 names Twilio Production transition workitem. Kano category: must-have (messaging dual-provider parity at Phase 2-A per senior-leader ICP three-population segment). References Step 5 Q6 carry-forward and Pass 1 reframe against article-surfaced May 2026 state. (Phase 2 design 7-Step Step 6 Pass 1 Group (b) Q6, [DATE])

**D120: Methodology-extension architectural shift to skills-per-role surface as Phase 2-B Cluster B9 shape.** Cluster B9 (methodology authoring extensions) Phase 2-B scope: role-extensions per the methodology-extension pattern surfaced across Steps 1-5 dogfooding (six categories at Step 5 Analyst plus five categories at Step 6 Synthesiser) plus skills-per-role surface per S26b deferred commitment. User-authored methodology surface (sub-problem 2.4) and methodology-fit lifecycle (sub-problem 6.4) live in Cluster B3 per Step 5 clustering, not B9. The architectural shift recognises that role-system_prompt extensions alone do not absorb all the discipline expansions surfaced through dogfooding; skills-per-role surface is the cleaner extension shape for procedural content per the briefs/p8/mckinsey-7-step.md authoring commitment. Landing surfaces: `charter/packages.md` P17 Wave 1 Cluster B9 contents. Kano category: must-have (the bet's procurement-grade methodology-embedding claim at agent-runtime level depends on this; six-instance structural evidence accumulated through Steps 1-6 needs the agent-runtime higher-bar test to close the bet's claim). References D86 (role-first agent identity) and D85 (S26b methodology authoring). (Phase 2 design 7-Step Step 6 Pass 1 Group (c) Q11 reconciliation, [DATE])

**D121: No-silent-operation as charter-grade principle.** Lift to charter-grade principle in `charter/principles.md` User safety section. Binding across phases; every read-every-session pass enforces; constrains all future agent and tool design. The principle states: Padhanam does not operate silently on tenant or user state. Every platform action that mutates state surfaces to the user via either real-time review (Tier 1 per the three-tier consent-and-awareness framework at D116) or user-controlled digest review cadence (Tier 2). Tier 3 silent operation does not exist. Combined with D82 platform invariants and the consent-granularity-proportionate-to-danger principle at `charter/principles.md`, the no-silent-operation principle commits the platform to user-visibility as a foundational property rather than as a configurable preference. Landing surfaces: `charter/principles.md` User safety section new subsection. Kano category: must-have (procurement-grade audit-trailed-approval-first defensibility per senior-leader ICP; competitive differentiator per May 2026 research). References D82 (platform invariants), D116 (three-tier framework), and existing principles.md consent-granularity principle. (Phase 2 design 7-Step Step 6 Pass 1 Group (c) Q13, [DATE])

**D122: Latency-tier inference routing as Phase 2-A architectural primitive.** Extension of D4's LiteLLM abstraction pre-existing slot. Phase 2 call sites pass tier hints to the LLM port; tier classification (real-time-required for user-invoked surfaces plus Tier 1 confirmation dialogs; async-tolerant for substrate ingestion analysis, surfacing-decision logic, methodology-applied judgment calculations, freshness checks across both vectors, audit narrative composition, mirror data composition, drop-suggestion generation, goal-to-item linking inference) drives model selection plus routing target plus timeout configuration. Orthogonal axis to the 5.4 three-tier consent-and-awareness framework at D116; both classifications apply at every platform action. Phase 1 call sites preserve current behaviour with opt-in retrofit. Operator dogfooding feasibility at meaningful daily usage and Phase 3 vertical-wedge procurement-grade defensibility per D14 customer-deployment model both improve substantially with tier-aware routing. Landing surfaces: architecture.md Vendor and dependency posture section addition under LiteLLM. Kano category: must-have (procurement-grade senior-leader ICP requires the architecture to commit latency-tier classification with configured targets per tier; Kano classification drove Q14 disposition). References D4 (LiteLLM abstraction) and D14 (customer-deployment model). (Phase 2 design 7-Step Step 6 Pass 1 Group (c) Q14, [DATE])

**D123: Cluster B9 elevated to Phase 2-B Wave 1.** Cluster B9 (methodology authoring extensions; scope per D120) elevates above other Phase 2-B clusters to Phase 2-B Wave 1 (P17). Sequences alongside foundational engineering clusters (B10 measurement substrate operationalisation; B1 partial; B2 partial) plus Twilio Production transition per D119. The bet's procurement-grade methodology-embedding claim depends on B9; six-instance structural-dogfooding evidence accumulated through Steps 1-6 elevates B9 from "evidenced" to "load-bearing on the bet's claim closure." B9 ships independently of engineering wave assignments based on own dependencies per Q7 parallel work-stream disposition. Landing surfaces: `charter/packages.md` P17 Wave 1 contents. Kano category: must-have (bet's claim closure depends on it). References D120 (B9 scope shift) and Step 6 Q15 disposition (agent-runtime exercise of McKinsey 7-Step at P18 Wave 2). (Phase 2 design 7-Step Step 6 Pass 1 Group (d) Q16, [DATE])

**(b) Append to `charter/principles.md`** the no-silent-operation subsection. Insert as a new H3 subsection under the User safety section, after the "Content framing for high-stakes domains" subsection (line 84) and before "Evolution discipline" (line 86):

````markdown
### No silent operation

Padhanam does not operate silently on tenant or user state. Every platform action that mutates state surfaces to the user via either real-time review (Tier 1 per the three-tier consent-and-awareness framework at D116) or user-controlled digest review cadence (Tier 2). Tier 3 silent operation does not exist. Combined with the platform invariants and the consent-granularity-proportionate-to-danger principle above, this commits the platform to user-visibility as a foundational property rather than as a configurable preference. Per D121.

````

**(c) Append to `charter/architecture.md`** a new H2 section titled "Phase 2 architectural primitives" between the "Domain primitives" section (ends around line 264) and the "The four-context substrate" section (begins around line 266). The new section contains six H3 subsections (one per primitive). Plus add a latency-tier sub-paragraph to the existing "LLM-provider-agnostic via LiteLLM" subsection in the Vendor and dependency posture section.

The new H2 section:

````markdown
## Phase 2 architectural primitives

Six architectural primitives anchor Phase 2-A and carry forward to Phase 2-B. The primitives surfaced at Step 5 of the Phase 2 design 7-Step arc as cross-sub-problem patterns and committed at Step 6 Pass 1 dispositions. Each primitive commits at Phase 2-A with operational delivery per the package structure at `charter/packages.md` P13-P16; Phase 2-B expansions follow per P17-P20.

### Revision-with-lineage standard interface

Per D114. The Revisable Protocol provides revision-with-lineage semantics for aggregates that mutate state through user-initiated or platform-initiated revisions. Three contexts implement the protocol at Phase 2-A: the portfolio context (per 1.3 state persistence; revisions for status transitions and content edits), the methodology context (per 2.1 methodology adaptation; user-adapted methodology revisions preserve genealogy from parent methodology), and the goal context (per 4.2 goal-state tracking; goal revisions preserve lineage and transfer linked items per the revision-with-lineage discipline). The pattern saturated across 2.1, 4.2, 3.2, 6.5 per Step 5 Pass 2 Work-stream 2 architectural patterns. CI-enforceable conformance via contract tests at `tests/contract/revisable/`. Cross-context reuse pattern structurally honest: the Revisable Protocol is general (any append-only-with-lineage surface uses the same shape) while input-shaping per context lives at each context's domain layer. References D26 (append-only audit chain), D31 (revisions pattern), and the hash-chain primitive at `padhanam/security/hash_chain.py` per D75.

### Conversation flow standard interface

Per D115. The ConversationFlow Protocol provides conversation-shaped surface semantics for user-invoked review and platform-initiated review-or-confirmation flows. Two contexts implement at Phase 2-A: the audit context (per 5.1 audit-conversation; broad audit review, filtered-by-event-class queries, item-specific drill-downs, goal-specific drill-downs, reflection-shaped queries) and the portfolio context (per 4.1 mirror-conversation; user invocation, narrative-response structure, drill-down conversation paths). Across-the-board at Phase 2-A per Step 5 Pass 2 Work-stream 2. Cross-context reuse pattern: the protocol carries the conversation-shaped surface contract; per-context content discipline lives at each context's domain layer (audit-narrative composition is technical-writer discipline with per-event-class templates; mirror-narrative composition is technical-writer discipline with narrative-language overlay). CI-enforceable conformance via contract tests at `tests/contract/conversation_flow/`.

### Three-tier consent-and-awareness framework

Per D116. Three tiers govern platform-initiated action surfacing: Tier 1 real-time review for high-danger classes (financial execution, outbound communication, legal commitments, irreversible operations); Tier 2 surfaced operation with user-controlled digest review cadence (routine reversible actions with audit visibility); Tier 3 silent operation does not exist per D121. Tier-depends-on-initiation refinement: same operation operates at different tiers depending on initiation context, not on operation type. Platform-initiated drops sit at Tier 1 (reversibility-sensitive); user-initiated drops follow the 1.5 commit-and-notify pattern. Native specification at sub-problem 5.4; cross-cuts surfacing mechanics at 3.1, drop-suggestion logic at 3.2, methodology adaptation at 2.1, goal-revision at 4.2, audit-conversation at 5.1, status-veracity at 6.3, correction mechanics at 6.5. The framework operationalises the existing consent-granularity-proportionate-to-danger principle at `charter/principles.md` without replacing it; framework operates as commercial positioning differentiator beyond safety hygiene per the procurement-grade audit-trailed-approval-first defensibility pattern identified in May 2026 competitor research at `charter/competitors.md`. References D82 (platform invariants) and D116.

### Tiered-by-salience

Per D117. Salience classification drives per-action surface depth across six surfaces: surfacing-decision logic at 3.1 (single-most-urgent platform-initiated default; batched narrative for user-invoked); drop-suggestion triggers at 3.2 (salience-weighted trigger evaluation); mirror-response density at 4.1 (configurable depth per user salience preference); audit-narrative density at 5.1 (per-event-class salience-weighted summarisation); status-veracity surface granularity at 6.3 (lower-pressure status options for low-salience items); methodology-applied importance threshold at 2.1 (salience-weighted methodology-recommendation surfacing). High-salience surfaces receive richer treatment; low-salience surfaces receive lighter treatment. Salience classification per surface is rules-driven at Phase 2-A (item-type rules; user-declared preferences; methodology-applied importance signals); learned-pattern-based salience defers to Phase 2-B Cluster B4 per the deferred-decisions entry on pattern-based triggers.

### Two-vector decay model

Per D118. Methodology-applied calibrations stale on two orthogonal vectors. Age vector: time-based decay; each methodology declares stale-after-N-time-units (RICE quarterly cadence; LVT six-month cadence; Kano roughly twelve-month cadence; McKinsey 7-Step faster). Information vector: event-driven decay; each methodology declares "events of type X make my application stale for items I have been applied to if [matching condition]" (RICE: new customer-research events, new effort estimates, new competitor moves; LVT: new initiative, new strategic priority shift, new resource constraint; Kano: new competitor offering changing user baseline expectations; McKinsey 7-Step: new stakeholder input, new evidence at any of the seven steps). Phase 2-A ships age-based freshness operational; information-based gets architectural commitment with Phase 2-B Cluster B3 operational delivery per P19 contents. Staleness produces two suggestion types at the methodology layer: drop suggestion (item no longer engaged; lives at 3.2) or rescore suggestion (methodology rescoring opportunity; lives at 2.1 methodology layer). References Step 5 Pass 1 sub-problem 3.2 finding introducing both vectors.

### Latency-tier inference routing

Per D122. Architectural extension of D4's LiteLLM abstraction pre-existing slot. Phase 2 call sites pass tier hints to the LLM port. Tier classification: real-time-required for user-invoked surfaces plus Tier 1 confirmation dialogs (latency budget under one second; latency-optimised model selection plus routing target); async-tolerant for substrate ingestion analysis, surfacing-decision logic, methodology-applied judgment calculations, freshness checks across both vectors, audit narrative composition, mirror data composition, drop-suggestion generation, goal-to-item linking inference (latency budget seconds-to-minutes; quality-optimised model selection plus higher-context routing target). Tier classification per call site is declared at call site annotation; LiteLLM gateway routes per tier configuration in `padhanam/config/inference.py`. Phase 1 call sites preserve current behaviour with opt-in retrofit. Orthogonal axis to the 5.4 three-tier consent-and-awareness framework at D116; both classifications apply at every platform action. The architecture commits to tier classification at every call site as Phase 2 discipline; tier-specific model selection plus routing configuration evolves with Phase 2-A dogfooding evidence. See also `charter/architecture.md` Vendor and dependency posture section for the LiteLLM gateway architecture this primitive extends.

````

Additionally append to `charter/architecture.md` the latency-tier sub-paragraph at the end of the existing "LLM-provider-agnostic via LiteLLM" subsection (currently ends at line 208 with the principles.md reference). Insert after the existing closing sentence:

````markdown

Phase 2 extends the LiteLLM abstraction with latency-tier inference routing per D122. Call sites pass tier hints; the gateway routes per tier configuration in `padhanam/config/inference.py`. See `charter/architecture.md` "Phase 2 architectural primitives" "Latency-tier inference routing" subsection for full specification.

````

### Commit 3: Operational charter — deferred-decisions plus packages

Conventional commit message: `docs(charter): step 6 operational landing — 4 deferred entries + Phase 2 P13-P20 package structure`

Two artefacts.

**(a) Append to `charter/deferred-decisions.md`** a new H2 section titled "Phase 2 design 7-Step deferrals" after the "Phase 2 substrate completion" section. The new section carries four entries.

````markdown
## Phase 2 design 7-Step deferrals

Architectural decisions deferred at Phase 2 design 7-Step Step 6 Pass 1 dispositions. Each entry names the activation trigger and the activating session or context.

### Phase 2-B Wave 4 versus Phase 3 boundary

Per Step 6 Pass 1 Q8 disposition. Several P20 Wave 4 candidates may legitimately slip to Phase 3: Cluster B1 remainder (work-app cells beyond operator stack); Cluster B7 conditional (watching, delegated additions); Cluster B9 second wave (skills-per-role surface refinement if not landed at P17); Cluster B5 conditional (normalised value units if Phase 2-A per-methodology friction).

**Activation trigger.** Approaching Phase 2-B Wave 4 (P19 close). Decision made when concrete context exists about what is ready to ship versus what carries to Phase 3.

**The specific D-entry lands at the activating session.** References Step 6 Pass 2 P20 Wave 4 contents.

### Tier 4 sub-problem activation triggers

Per Step 6 Pass 1 Q9 disposition. Single deferred entry covering all eight Tier 4 sub-problems from Step 3 prioritisation (1.2, 2.2, 2.3, 2.5, 3.3, 3.4, 4.5, 5.2, 5.3, 6.1, 6.2 with 2.2 plus 2.4 plus 4.5 plus 6.1 plus 6.2 plus 6.5 carrying into Phase 2-B clusters per Step 5 activation map). Tier 4 sub-problems that do not activate through Phase 2-B clusters remain Tier 4 deferred.

**Activation trigger.** Per Tier 4 sub-problem detailed design when the sub-problem's containing Phase 2-B cluster (per Step 5 activation map) enters package scope. Sub-problems not activated through Phase 2-B clusters review at Phase 3 framing.

**The specific D-entries land per sub-problem at activating session.** References Step 5 Work-stream 4 Tier 4 activation map.

### Identity-fork schema-based threshold

Per Step 6 Pass 1 Q10 disposition. The identity-fork mechanism for methodology adaptation crossing structural threshold (when an adapted methodology has diverged so far from parent that it is structurally a different methodology rather than a revision). Step 5 surfaced schema-based threshold detection as candidate; final threshold definition defers to detailed design at Phase 2-B Cluster B3 activation.

**Activation trigger.** Phase 2-B Cluster B3 detailed design session (P19; methodology layer depth wave).

**The specific D-entry lands at the activating session.** References Step 5 Pass 1 sub-problem 2.1 finding plus Pass 1 Q11 reconciliation.

### Twelve event classes confirmation

Per Step 6 Pass 1 Q12 disposition. The audit visibility (5.1) workplan committed twelve event classes at Step 5 Pass 1 finding (six workplan plus five Pass 1 design refinements plus one 5.4 central-storage refinement). Confirmation of the twelve-class scope plus any additional event classes surfacing during 5.1 detailed design defers to the 5.1 detailed design session at Phase 2-A Wave 3 (P15).

**Activation trigger.** Phase 2-A P15 5.1 audit visibility detailed design session.

**The specific D-entry lands at the activating session.** References Step 5 Pass 1 sub-problem 5.1 finding.

````

**(b) Append to `charter/packages.md`** a new section for Phase 2 packages after line 20 (the Phase 1 narrative line). The Phase 1 section content remains unchanged.

````markdown

# Phase 2 Packages

Phase 2 ships methodology-as-product UX on top of Phase 1's complete substrate per D93 and per the Phase 2 design 7-Step arc at `charter/phase-2-design-7step.md`. Eight packages across two stages per Step 6 Pass 2 LVT placement. Phase 2-A delivers the operator-validated find-rhythm-and-settle-in instance (P13-P16); Phase 2-B scales to broader senior-leader-ICP (P17-P20). User segment commitment at `charter/phase-2-user-segment.md`; six architectural primitives at `charter/architecture.md` Phase 2 architectural primitives section; sixteen carry-forward question dispositions plus integrated storyline at `charter/phase-2-design-7step.md` Step 6 section.

## Phase 2-A: Operator-validated find-rhythm-and-settle-in instance

- **P13: Foundational substrate (Wave 1).** 1.3 State persistence; 1.1 manual entry cell. Latency-tier routing extension at LiteLLM port per D122; Twilio Sandbox setup plus messaging adapter scaffold per D119; Revisable Protocol defined per D114; ConversationFlow Protocol defined per D115; no-silent-operation principle commits at `charter/principles.md` per D121; tiered-by-salience plus two-vector decay plus three-tier consent-and-awareness D-entries plus architecture.md additions per D116, D117, D118. Phase 2 PRD entry at `charter/p12-phase-2-inputs.md` substrate-completion handoff.

- **P14: Core domain entities and trust substrate (Wave 2).** Six parallel work-streams. 1.1 calendar-read cells (Google, MS365); 1.1 email-read cells (Gmail, Outlook); 4.2 Goal-state tracking; 6.3 Status veracity; 5.4 Intelligence-layer guardrails action-class classification; 2.1 Methodology library core (discovery, content surface, four methodologies authored with effect-first surface and audit-trail-lineage adaptation discipline). Revisable Protocol exercised at 2.1 methodology adaptation and 4.2 goal revision.

- **P15: Messaging substrate and user-facing surfaces (Wave 3).** 1.1 Slack messaging trio (write, observe-status, observe-incoming); 1.1 WhatsApp messaging trio via Twilio Sandbox (per D119; Meta template approval calendar-time started during Wave 2); 2.1 methodology library activation (matching, recommendation, adaptation flows); 3.1 Surfacing mechanics; 5.1 Audit visibility (events accumulating from earlier waves; twelve event classes per the deferred-decisions entry). ConversationFlow Protocol exercised at 5.1 audit-conversation.

- **P16: Late user-facing surfaces (Wave 4).** 1.5 User-authored items; 3.2 Drop-decision support; 4.1 Mirror surface. ConversationFlow Protocol exercised at 4.1 mirror-conversation. Phase 2-A close: operator dogfooding instance complete across at least one week of real use; senior-leader ICP test condition validated against operator-as-first-instance; operational thresholds plus dogfooding-evidence thresholds per Step 5 substrate-completion criteria.

## Phase 2-B: Scale to broader senior-leader-ICP

- **P17: B9 elevated plus foundational substrates (Wave 1).** B9 methodology authoring extensions running in parallel (role-extensions per methodology-extension pattern plus skills-per-role surface per D120, per D123 elevation); B10 measurement substrate operationalisation (aggregation pipeline); B1 partial (highest-priority substrate expansions per dogfooding evidence); B2 partial (multi-device sync implementation kicks off); Twilio Production verified-business plus template-approval transition per D119.

- **P18: Operational delivery plus agent-runtime exercise (Wave 2).** B1 remainder; B2 remainder (conflict-resolution, audit/surfacing extensions for multi-device); B3 partial (information-based freshness per D118 information vector, identity-fork mechanism per the deferred-decisions entry); B4 partial (voice channel paired with B1 voice substrate, preference expansions, per-message review surface); B6 partial (per-action-class cadence configuration, cross-channel digest delivery, reclassification mechanism); B7 partial (per-user customised thresholds); B8 partial (per-device authoring optimisation); plus agent-runtime exercise of McKinsey 7-Step end-to-end per Step 6 Pass 1 Q15 disposition (closes the bet's higher-bar methodology-embedding claim within Phase 2 alongside criterion-4 demonstration).

- **P19: Accumulated-history wave (Wave 3).** B3 remainder (2.2 Methodology-to-item binding, 2.4 User-authored methodology surface, 6.4 Methodology-fit lifecycle activations); B4 remainder (pattern-based triggers, settle-in adaptation); B5 (reflection layer extensions; pattern surfacing per 4.4; value-versus-time accounting per 4.3; audit narrative density); B6 remainder (learned migration thresholds, sub-class granularity automation, combined-signal detection, per-class consent refinement per 3.5); B7 remainder (pattern-based status suggestions, status-narrative learning); B8 remainder (learned parsing improvements); B10 remainder (threshold monitoring and alerting, operator-facing measurement-review surface).

- **P20: Phase 2-B late or Phase 3 boundary (Wave 4).** B1 remainder (work-app cells beyond operator stack); B7 conditional (watching, delegated additions); B9 second wave (skills-per-role surface refinement if not landed earlier); B5 conditional (normalised value units if Phase 2-A per-methodology friction). Phase 2-B Wave 4 versus Phase 3 boundary settles per the deferred-decisions entry when approaching this wave.

## Phase 3 candidates (tagged at Phase 2 close)

Vertical-wedge work in financial services, legal, healthcare per senior-leader-ICP refinement at `charter/phase-2-user-segment.md`. Meta WhatsApp Cloud API direct as second messaging path per D119. Foundation-model defence work per the Nerve acqui-hire structural signal in `charter/competitors.md`. End-of-Phase-3 competitive landscape review. Sub-problems 5.2 Source attribution, 5.3 Cost transparency, 5.5 Trust history (not in Step 5's Phase 2-B map; likely Phase 3). Sub-problems 4.5, 6.1, 6.2, 6.5 (Tier 4 deferred without specific Phase 2-B trigger per Step 5 activation map).

````

### Commit 4: Bookkeeping — close marker, commit prompt preservation, session log entry

Conventional commit message: `docs(charter): mark step 6 close; preserve commit prompt; session log`

Three artefacts.

**(a) Append to `charter/current-package.md`** a new close marker paragraph after the prior marker. Append-only operation; chronological order preserved.

The new paragraph reads (adjust the date at write time):

> **Phase 2 design 7-Step arc Step 6 (Synthesise) closed** at [YYYY-MM-DD]. Full canonical Step 6 section landed at `charter/phase-2-design-7step.md`; ten D-entries (D114-D123) landed at `charter/decisions.md`; no-silent-operation principle elevated to charter-grade at `charter/principles.md` User safety section; six architectural primitives (revision-with-lineage, conversation flow, three-tier consent-and-awareness, tiered-by-salience, two-vector decay model, latency-tier inference routing) landed at `charter/architecture.md` new Phase 2 architectural primitives section plus latency-tier sub-paragraph at LiteLLM subsection; four deferred-decisions entries (Phase 2-B Wave 4 boundary, Tier 4 activation triggers, identity-fork threshold, twelve event classes) landed at `charter/deferred-decisions.md` new Phase 2 design 7-Step deferrals section; Phase 2 P13-P20 package structure landed at `charter/packages.md`; Step 6 brief preserved at `briefs/phase-2/design-7step-step-6.md`; interim record archived via header note at `briefs/phase-2/design-7step-step-6-interim.md` with content preserved as historical authoring substrate. Step 7 (Communicate) opens as the next strategic-mode block at a fresh Claude.ai conversation per arc precedent; Step 7 brief authors pre-conversation at `briefs/phase-2/design-7step-step-7.md`.

**(b) Create `briefs/phase-2/design-7step-step-6-commit.md`** with this commit-session prompt verbatim.

**(c) Append to `log/sessions.md`** a new entry matching the Pass 3 commit entry shape, scaled for four commits. Suggested structure (adjust dates and SHAs at write time):

````markdown
## [DATE] — Phase 2 design 7-Step arc Step 6 (Synthesise) full commit
roles: analyst, PM, architect, technical writer
mode: strategic (charter commit; no code changes; Step 6 canonical landing closes the substantive Step 6 work)

- Produced: Four commits closed the session.
  - Commit [SHA1] (`docs(charter)`): Step 6 section at canonical altitude appended to `charter/phase-2-design-7step.md`; Step 6 brief preserved at `briefs/phase-2/design-7step-step-6.md`; interim record archived via header note at `briefs/phase-2/design-7step-step-6-interim.md`.
  - Commit [SHA2] (`docs(charter)`): Ten D-entries (D114-D123) appended to `charter/decisions.md`; no-silent-operation subsection appended to `charter/principles.md` User safety section; six architectural primitives appended to `charter/architecture.md` as new Phase 2 architectural primitives section plus latency-tier sub-paragraph at LiteLLM subsection.
  - Commit [SHA3] (`docs(charter)`): Four deferred-decisions entries appended to `charter/deferred-decisions.md` as new Phase 2 design 7-Step deferrals section; Phase 2 P13-P20 package structure appended to `charter/packages.md`.
  - Commit [SHA4] (`docs(charter)`): `charter/current-package.md` close marker append plus commit prompt preservation at `briefs/phase-2/design-7step-step-6-commit.md` plus this session log entry.

- Decisions: Ten new D-entries (D114-D123). D114 revision-with-lineage; D115 conversation flow; D116 three-tier consent-and-awareness; D117 tiered-by-salience; D118 two-vector decay model; D119 WhatsApp via Twilio messaging-channel-and-path; D120 methodology-extension architectural shift to skills-per-role; D121 no-silent-operation as charter principle; D122 latency-tier inference routing; D123 Cluster B9 elevated to Phase 2-B Wave 1.

- Tests: None. Documentation-only changes.

- Reflection prompts answered (Step 6 substantive work closes at this commit; reflection prompts answered at Pass 3 commit per the Pass 3 commit session log entry; the full Step 6 commit session is mechanical landing of substrate prepared at Passes 1-3).

  1. *Commit-precision check.* Four commits landed in the order specified; each commit's scope held without bleed. Conventional-commit messages descriptive. The four-commit shape held legibility versus a single omnibus commit.

  2. *Verify-against-current-sources check (Twilio).* D119 text reconciled against Twilio's current WhatsApp Business Platform documentation before write. [Adjust at write time per outcome: "Pass 1 reframe held; D119 text written per the reconciliation" OR "Pass 1 reframe required adjustment for [specific drift]; D119 text adjusted to reconcile" OR "Pass 1 reframe materially incorrect against current Twilio state; Commit 2 paused; flag raised for strategic-mode disposition before write."]

  3. *Granular D-entry discipline check.* Ten separate D-entries committed rather than omnibus. Each D-entry carries a discrete decision with distinct landing surfaces. Audit-trail granularity preserved at the cost of D-entry count.

  4. *Interim archive discipline check.* Interim record preserved as historical authoring substrate via header note; not deleted. The append-only audit discipline holds; the canonical reference at `charter/phase-2-design-7step.md` Step 6 section is distinct from the authoring substrate at the interim record.

- methodology (line 1): **Step canonical landing as four-commit shape.** Substantive arc-Step canonical landings naturally separate into Step section + charter primitives + operational charter + bookkeeping. The four-commit shape carried legibility at Step 6's substantial scope. Worth observing whether Steps 1-5 close commits used the same shape (the Step 5 commit precedent referenced in this prompt's context is at the next session log to verify; if not, Step 6's shape may warrant promotion as the pattern for substantial Step canonical landings).

- methodology (line 2): **Verify-against-current-sources block as commit-prompt discipline.** Pass 1's Q6 reframe against the May 2026 WhatsApp article was the substantive substrate; the D119 text could have silently propagated inaccuracies if Twilio's offering shifted between Pass 1 and Step 6 close commit. The verify block in this commit prompt is the second instance of the S4 Langfuse precedent shape (first instance the precedent itself; second instance this commit prompt). Promotion threshold at second instance; the methodology line absorbs the discipline as charter-grade for vendor-specific-naming D-entries.

- **Phase 2 design 7-Step arc Step 6 (Synthesise) closed** at [DATE]. Step 7 (Communicate) opens as the next strategic-mode block.
````

## Acceptance criteria

1. `charter/phase-2-design-7step.md` Step 6 section appended at file tail; section structure per the Commit 1 Operation 1a template; content composed from interim record per the named structural transformations.
2. `briefs/phase-2/design-7step-step-6.md` added to git tracking; content unchanged.
3. `briefs/phase-2/design-7step-step-6-interim.md` carries the archive-note header prepended before the H1; content below the separator unchanged.
4. `charter/decisions.md` carries ten new D-entries (D114-D123) in the order specified under the Phase 2 decisions heading; format matches existing D-entry format.
5. `charter/principles.md` carries the no-silent-operation H3 subsection between "Content framing for high-stakes domains" and "Evolution discipline."
6. `charter/architecture.md` carries the new Phase 2 architectural primitives H2 section between "Domain primitives" and "The four-context substrate"; plus the latency-tier sub-paragraph at the LiteLLM subsection.
7. `charter/deferred-decisions.md` carries the new Phase 2 design 7-Step deferrals H2 section with four H3 entries.
8. `charter/packages.md` carries the Phase 2 packages section after the Phase 1 narrative; Phase 1 section content unchanged.
9. `charter/current-package.md` carries a new close marker paragraph after the prior marker; append-only operation preserves prior content unchanged.
10. `briefs/phase-2/design-7step-step-6-commit.md` exists with this commit-session prompt preserved verbatim.
11. `log/sessions.md` carries the new session entry matching the Pass 3 commit entry shape, scaled for four commits, with four reflection prompts and two methodology lines.
12. Four commits land in the order specified with conventional-commit messages as specified.
13. D119 text reconciled against Twilio's current documentation per the verify-against-current-sources block; flag raised if Pass 1 reframe is materially incorrect against current Twilio state.

## Out of scope

- Step 7 (Communicate) substantive work: opens in a subsequent Claude.ai conversation per arc precedent; opens as the next strategic-mode block immediately after this commit lands.
- Phase 2-A implementation work (P13 build sessions): opens at build-mode after Step 7 closes.
- Any Phase 1 charter file content modifications outside the named appends.
- Cluster B9 detailed design or P17 detailed scoping: defers to P17 framing strategic block at Phase 2-A close.
- Step 7 brief authoring: drafts pre-conversation per the briefs/ discipline; not part of this commit session.

## Session log entry instruction

After the fourth commit, append the build-session entry to `log/sessions.md` with the four reflection paragraphs and two methodology lines per the Commit 4 specification. Include `roles:` tag (analyst, PM, architect, technical writer; architect included given the six architectural primitives landed at architecture.md).
