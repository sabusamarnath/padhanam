# Phase 2 design — McKinsey 7-Step arc

Strategic-mode arc applying the McKinsey 7-Step problem-solving methodology to Phase 2's strategic shape. Charter-grade placement per the arc-opening conversation's Decision 1: binding specification; Step 3's prioritised bets become Phase 2 LVT structure when the v6 roadmap entry lands per D44. Refreshes at phase audits per D45.

Blank-sheet discipline applies within the bet's success criteria per the arc-opening conversation's Decision 2. The bet's core claims (procurement-grade architecture, methodology-as-product, learning sprint demonstration) hold. Phase 2-specific commitments (D93 framing, three-wave sequencing, the mass-market-UX commitment in `log/captures.md`) are open to re-derivation through the arc.

Posture 1.5: structural dogfooding of the McKinsey 7-Step methodology template authored at S26b per D85, structured per D81's multi-role aggregate v2 shape with the override-mode space committed at D87. The arc reads the role specifications and holds the discipline manually; the methodology aggregate is not invoked through the agent runtime at this arc's posture.

## Step 1: Define the problem

### Problem statement

Busy professionals working twelve-plus hour days carry a portfolio of work and personal goals that need calibrated, variable pacing. Each item benefits from a different pace: urgent items move fast, patient items hold steady, some items should be dropped. The user's effectiveness depends on calibrating pace correctly across the portfolio and acting on those calibrations consistently over time. Under twelve-plus-hour-day load, the calibration breaks down. Items slip out of view. Items needing urgency get under-attended. Items needing patience get neglected because nothing surfaces them. Items that should be dropped continue to consume attention because they made noise. What is missing is not visibility or notifications, both of which the user already gets too much of. What is missing is judgment applied to the portfolio at the right moments: decisions the user can act on, drops the user can confirm, and pacing the user can trust.

### Context: the user's current substitutes

The user has already attempted to solve this with the substrates available. Calendar, AI chat assistants, note-taking apps, light EA support, and self-built structured trackers operating with daily check-ins, item logging by category, and scheduled reminders. Each substrate solves a slice. None integrates the slices. Each demands the user perform the integration in their own head, which is precisely where the twelve-hour-day load creates the breakdown. The work is not to replace these substrates with another individual tool. The work is to bring them together into something that supports the user with integrated judgment they cannot sustain unaided.

### Context: the CoS analogue and the population gap

People senior enough to employ a Personal Assistant, Executive and Personal Assistant, Private Assistant, or Chief of Staff have a partial answer. A human who holds the integrated portfolio, applies judgment, nudges items along at appropriate pace, flags what is slipping, surfaces what to drop, and plays back return on time invested against the user's stated goals. The population carrying the same load shape without this support is much larger. They absorb the load on their personal life, on the quality of their work, or on both. The shape of the problem does not differ between the CoS-supported and CoS-unsupported populations. Only the judgment layer differs.

### Dogfooding-evidence record

The bet's procurement-grade-methodology-embedding claim turns on whether the methodologies Padhanam authors on its control plane actually do work for users at real problems. This conversation is the first structural test of that claim against the McKinsey 7-Step ProblemFramer role authored at S26b per D85, structured per D81's multi-role aggregate v2 shape with the override-mode space committed at D87. Posture 1.5: structural dogfooding of the McKinsey 7-Step methodology template without agent runtime dependency. The conversation read the role's specification and held the discipline manually; it did not invoke an agent against the input.

The ProblemFramer role's function-focused system_prompt commits the role to "receive a raw problem statement or topic from the user; produce a sharpened problem statement with explicit scope (what is in and out), context (situation), complication (what makes this hard or urgent), and success criteria (what good looks like)." This shape did load-bearing work in the conversation. The problem statement above carries scope (busy professionals, twelve-plus hour days, work-life portfolio), situation (current substrates and CoS analogue), complication (calibration breakdown under load), and success criteria (verifiable at Phase 2 close per the success-measurement deliverable archived in the Step 1 conversational record). The McKinsey override layering SCQ (Situation, Complication, Question) added light discipline: the complication-shaped framing of consequence-of-persistence is SCQ-shaped output rather than scope-and-context-shaped. The role's "you do not analyse the problem yourself; you frame it" discipline held cleanly. Sub-problems surfaced naturally during conversation but the assistant resisted disaggregating them, holding them for Step 2 instead.

The conversation prompt named five ProblemFramer discipline sub-prompts: Who has the problem, What is the problem, What gets worse if the problem persists, How would success be measured, What is the problem NOT. Of these, only "What is the problem" maps directly to the template's authored discipline. The other four extend beyond what the role's system_prompt encodes. "Who has the problem" forced specificity on the user definition that the template's scope-as-what-is-in-and-out wording does not require. "What is the problem NOT" forced solution-assumption removal, which is not in the template. The user-perspective framing the conversation prompt embeds was not in the template either. The operator's general knowledge of McKinsey framing plus the conversation prompt's expanded discipline filled the gaps.

The McKinsey 7-Step ProblemFramer role as authored has narrower discipline scope than the full ProblemFramer work this conversation needed. Two responses are honest: either expand the role's system_prompt to encode the five-sub-prompt discipline explicitly, or land it via the recommended-skills-per-role surface deferred to Phase 2 per the brief at briefs/p8/mckinsey-7-step.md. The first response is more durable; the second is structurally cleaner if skills become the methodology-extension surface in Phase 2. The choice is a Phase 2 strategic-mode question, not a Step 1 deliverable. Logging it as a Phase 2 workitem candidate.

The methodology authoring earns its place at structural level. The role definition was readable, the discipline transferable, and the output is a problem statement that survives the self-challenges. This is the minimum bar for procurement-grade methodology embedding, not the maximum. Behavioural dogfooding (an actual ProblemFramer agent running against the input, producing the same problem statement) remains untested. Phase 2's UX surface for methodology adoption, plus the agent runtime exercising the McKinsey 7-Step workflow end-to-end, would close the higher bar. Until then, the bet's methodology-embedding claim has structural evidence but not agent-runtime evidence.

### Initial disaggregation (carry-forward to Step 2)

Sub-problem candidates that surfaced naturally during Step 1 but were held for Step 2's MECE disaggregation: The judgment layer (methodology-applied decisions, drops, pacing recommendations across the portfolio). The mirror function (on-demand return-on-time-invested playback against stated goals). The whisperer function (surfacing items at the right moment for the right item with appropriate judgment, not as bulk notification noise). Portfolio view persistence (state management across sessions; integrating substrate data into a single picture). User-authored methodology surface (enabling the user to bring their own methodologies, the four-functions-plus-user-authored expansion). Personal-domain integration (treating personal items with the same lifecycle dignity as professional items). Substrate integration (bringing calendar, email, notes, existing tracker data, light EA support together rather than replacing them).

Step 2 takes these and produces a MECE-decomposed issue tree, per the McKinsey 7-Step Disaggregator role's discipline. The candidates above are not yet MECE; several overlap (mirror and whisperer both touch judgment layer; substrate integration enables portfolio view persistence). The Disaggregator's work is to cut these into clean, non-overlapping branches with collectively-exhaustive coverage.

### Open questions for Steps 2 and 3

For Step 2 (Disaggregation). How to cut the substrate-integration sub-problem cleanly. Calendar, email, notes, and existing trackers are different categories with different access patterns, privacy properties, and ownership. A single "substrate integration" branch may collapse meaningful differences. Step 2 decides whether to split by substrate type or by integration function.

For Step 3 (Prioritisation). Whether the dogfooding instance (operator only) frames prioritisation, or whether the Phase 2 work also targets the broader busy-professional population at a level that affects which sub-problems are top-quartile. Operator-only dogfooding suggests a narrower sub-problem set with deeper coverage; broader-population targeting suggests wider coverage with shallower per-sub-problem depth. The strategic choice has implications for Phase 2 packaging.

### Step 1 close

Step 1 closes with the problem statement converging through five ProblemFramer sub-prompts (Who has the problem, What is the problem, What gets worse if the problem persists, How would success be measured, What is the problem NOT). The problem statement above survives the self-challenges applied at each prompt. Step 2 (Disaggregation) opens with the initial disaggregation candidates plus the two open questions named above.

## Step 2: Disaggregate

Step 2 applied the McKinsey 7-Step Disaggregator role's discipline to Step 1's sharpened problem statement. The role's function-focused system_prompt commits the role to "decompose problems into structured component trees... receive a sharpened problem from the ProblemFramer; produce a structured decomposition where each branch represents a distinct sub-problem and branches together are collectively exhaustive." The McKinsey override layered "Apply MECE (Mutually Exclusive, Collectively Exhaustive) decomposition; produce an issue tree." Posture 1.5 dogfooding continued from Step 1: the conversation read the role's specification and held the discipline manually without invoking the agent runtime.

Two structural insights emerged during the disaggregation conversation that the Disaggregator role's authored system_prompt does not encode. First, the user-faking-it problem (saying yes when meaning no; status veracity; ambivalence under load) surfaced a sub-problem the initial five-branch shape did not accommodate; the tree gained Branch 6 (Signal fidelity and methodology-fit) to host the platform-to-user signal-verification work distinct from Branch 5 (user-to-platform trust). Second, the rhythm-and-key-change framing introduced a four-stage temporal lifecycle (find rhythm, settle in, watch for key change, adapt) that elevated to cross-cutting discipline applying at every branch, not just at methodology-fit. The Disaggregator role's MECE override produces snapshot tree shape; the temporal lifecycle adds dynamic-state shape that overlays the snapshot.

### Issue tree

**Branch 1: Portfolio existence as a unified picture.**

- 1.1 Substrate connection. How items move from where they live (calendar, email, notes, trackers, head) into the platform's portfolio. Substrate type axis and integration function axis both held per Step 1.
- 1.2 Item identity reconciliation. The same item surfacing across substrates must consolidate to one portfolio entity rather than counted multiple times.
- 1.3 State persistence. The integrated portfolio survives across sessions; the user does not rebuild context each time.
- 1.4 Personal-versus-professional treatment. Personal items receive the same lifecycle dignity as professional items rather than being triaged out by default.
- 1.5 User-authored items. Items the user types directly into the platform; different ownership and lifecycle from substrate-derived items.

**Branch 2: Pace calibration for each item.**

- 2.1 Methodology library. The set of methodologies available for application. Attribution; authoring quality; the primitives-versus-templates discipline.
- 2.2 Methodology-to-item binding. Which methodology applies to which item at which moment; per-item, per-methodology mappings.
- 2.3 Pace inference per item. Given item plus methodology, what pace does the methodology imply (urgency, importance, dependencies, energy, value-of-effort).
- 2.4 User-authored methodology surface. The user authors and adapts methodologies; the authorship interface; methodology validation.
- 2.5 Calibration override mechanics. When the platform's calibration is wrong; per-item, per-methodology, global override paths.

**Branch 3: Action at the right moment.**

- 3.1 Surfacing mechanics. When and how the platform brings items to user attention; channels, frequency, urgency calibration of surfacing itself.
- 3.2 Drop-decision support. Platform-suggested drops; user-initiated drops; the conversation around dropping.
- 3.3 Defer mechanics. Deferral with reason, trigger, or review prompt; deferred state visibility.
- 3.4 Delegation support. Items handed to other people or systems; delegated-state tracking; follow-up surface.
- 3.5 Consent granularity for platform actions. Per D82's intelligence-layer commitment; per-action versus per-class versus standing-consent-with-review.

**Branch 4: Feedback on whether calibration is working.**

- 4.1 Mirror surface. On-demand retrospective on time spent versus value produced; format, depth, time-range, drill-down.
- 4.2 Goal-state tracking. User-stated goals over time; goal authorship; goal revision; goal-to-item linking.
- 4.3 Value-versus-time accounting. Aggregating time spent against value produced; value defined per methodology per item.
- 4.4 Pattern surfacing. Hot and cold spots across time; recurring stalls; types of items that consistently drop.
- 4.5 Feedback-to-platform. User shapes what feedback they receive; mirror customisation; pattern-surfacing preferences.

**Branch 5: Trust substrate for offloading.**

- 5.1 Audit visibility. What the platform did, when, why, with what inputs; user-readable; tied to the Phase 1 audit substrate.
- 5.2 Source attribution. Recommendations cite the user-authored content, methodology, or prior decisions that informed them.
- 5.3 Cost transparency. Per-action cost (LLM, computational, attention); aggregate cost over time.
- 5.4 Intelligence-layer guardrails. D82 commitments visible at user surface; no autonomous action on consequential matters; explicit consent; reversibility.
- 5.5 Trust history. Trust-building moments; trust-break events; trust recovery; visible to the user.

**Branch 6: Signal fidelity and methodology-fit.**

- 6.1 Signal verification. When the platform verifies a user signal versus accepts at face value; verification mechanics with low user friction.
- 6.2 Compliance-signal detection. Yes-when-they-mean-no; agreement under fatigue or social pattern; detection without being a nag.
- 6.3 Status veracity. Item marked done that may not actually be done; lower-pressure status options like stalled, uncertain, partial.
- 6.4 Methodology-fit lifecycle. The four-stage lifecycle applied to methodology specifically: cold-start fit, rhythm maintenance, drift and key-change detection, transition support.
- 6.5 Correction mechanics. User revises a past signal without friction; preserves history; does not punish the user for being human under load.

### Cross-cutting disciplines

Two disciplines apply at every sub-branch:

**Detection.** Each sub-branch needs internal feedback on whether the sub-branch is working: observed-behaviour-versus-stated-intent at every interface where the platform consumes user signal or produces user-facing output.

**Find rhythm, settle in, watch, adapt.** The four-stage temporal lifecycle. Each sub-branch behaves differently at each stage. Conservative defaults at find-rhythm; minimal intervention at settle-in; continuous background watch; supportive transition at adapt; then return to find-rhythm for the new state.

### Self-challenge

The tree holds MECE at sub-branch level. Each branch's five sub-branches are mutually exclusive (distinct work units; no overlap within the branch). Cross-branch overlap testing identified the closest pairs as 4.5 (feedback-to-platform) and 6.5 (correction mechanics); 1.5 (user-authored items) and 2.4 (user-authored methodology); these are distinct work units despite sharing user-authorship vocabulary.

Items deliberately not in the tree: agent runtime substrate; mass-market UX as design constraint; user onboarding as a Phase 2 deliverable concern. Solution territory remains excluded by the Disaggregator role's discipline. The bet's case-study reader audience is also absent because Phase 2's user is the busy professional running a Private Assistant per Step 1.

Thirty sub-problems at this granularity is workable for impact-tractability scoring at Step 3.

### Dogfooding-evidence record

The McKinsey 7-Step Disaggregator role authored at S26b per D85 carries a function-focused system_prompt committing the role to producing MECE issue trees. The McKinsey override added MECE plus issue-tree shape. Posture 1.5 structural dogfooding without agent runtime continued from Step 1.

What the template informed. The "you do not solve sub-problems; you structure them" discipline held cleanly. The conversation resisted moving into prioritisation language even when the operator's framing suggested implications (key-change as a transition state; the seven framework examples). The MECE override gave the explicit structural test that the conversation applied at every branch addition. Branch 6 was added because Branch 5 as user-trust did not accommodate platform-to-user signal fidelity; the operator's three questions surfaced the structural gap and the discipline produced the addition. The issue-tree shape held: hierarchical, two-level decomposition, thirty terminal sub-problems.

Where the template's scope did not cover the work. Two extensions surfaced during the conversation that the McKinsey 7-Step Disaggregator role does not encode. First, the rhythm-and-key-change framing introduced a temporal lifecycle as cross-cutting discipline; the McKinsey override's MECE produces snapshot tree shape, not temporal-mode shape. The operator's framing combined with the template's MECE produced a richer disaggregation than either alone. Second, the substrate-integration cut question called for holding orthogonal dimensions at sub-branch level rather than collapsing to one; the template's MECE override does not specify how to handle orthogonal dimensions within a sub-problem.

What this surfaces for Phase 2 methodology work. The Disaggregator role would benefit from a temporal-lifecycle discipline addition. Issue trees that ignore temporal dynamics produce static decomposition where the underlying problem has stage-dependent behaviour; the Disaggregator's output is then materially weaker than the problem deserves. Two candidate landing surfaces: addition to the Disaggregator role's system_prompt encoding "consider whether the problem has temporal-state structure and apply lifecycle discipline as cross-cutting overlay where it does," or a Phase 2 skills-per-role surface (deferred per the brief at briefs/p8/mckinsey-7-step.md) that bundles temporal-lifecycle and orthogonal-dimension-handling as Disaggregator skills.

What this tells us about the bet's claim. The methodology authoring continues to earn its place at structural level. The Disaggregator role was extensible to accommodate operator insights (rhythm/key-change, faking-it problem, methodology adaptation) without breaking; the role's structural discipline did not prevent the conversation from going where the problem required. The extensibility itself is signal worth recording. Agent-runtime evidence remains untested at Step 2; Phase 2 UX surface for methodology adoption plus agent runtime exercising the Disaggregator end-to-end would close the higher bar.

### Carry-forward to Step 3

Four open questions land at Step 3 (Prioritisation):

1. Dogfooding-only versus broader-population framing. From Step 1's carry-forward, now sharper. Step 3's prioritiser ranks sub-problems by impact and tractability; the population scope materially changes impact. Operator-only dogfooding narrows impact assessment to one user; broader-population widens it. The Phase 2 deliverable strategy depends on this choice.

2. Substrate-type × integration-function matrix at sub-branch 1.1. Both axes carry forward per Step 2. The Prioritiser decides which cells (calendar-read, email-write, notes-observe, etc.) land top-quartile. The substrate axis differences (privacy, ownership, access patterns) and the function axis differences (consent class, technical complexity) both inform impact-tractability scoring.

3. Dependency ordering across branches. Branch 2 (calibration) depends on Branch 1 (portfolio existing). Branch 3 (action) depends on Branch 2. Branch 4 (feedback) depends on Branches 1-3. Branch 6 (signal fidelity) depends on user signal sources that exist when other branches operate. The Prioritiser must respect dependency or face buildable-but-unusable sub-deliverables. Branch 5 (trust) is foundational and partially independent.

4. Lifecycle-stage prioritisation. The four-stage discipline applies at every branch. Step 3 must decide whether Phase 2 ships find-rhythm-plus-settle-in stages across all branches first (with watch and adapt later), or ships full-lifecycle support for fewer branches first. Different commercial test conditions for each choice.

### Step 2 close

Step 2 closes with the issue tree at six branches × five sub-branches, plus two cross-cutting disciplines (detection and the four-stage temporal lifecycle). The tree survived MECE self-challenge at sub-branch level. The Disaggregator role's discipline produced a usable tree that accommodated operator-driven structural insights without breaking. Step 3 (Prioritisation) opens at Claude.ai with the four open questions above as inputs plus the full thirty-sub-problem set as the impact-tractability scoring surface.

## Step 3: Prioritise

Step 3 applied the McKinsey 7-Step Prioritiser role's discipline to the issue tree produced at Step 2. The role's function-focused system_prompt commits the role to "score each branch on impact (how much resolving this moves the overall problem) and tractability (how feasible resolving this is in available time and resources); produce a ranked list with the top branches flagged as priorities." The McKinsey override layered "Use impact-tractability matrix; flag the top quartile as priorities." Posture 1.5 dogfooding continued from Steps 1 and 2. The conversation read the role's specification and held the discipline manually without invoking the agent runtime.

Three pre-conversation decisions framed the scoring approach. Decision 1 (population scope for impact): operator as first instance of broader busy-professional population, balancing operator dogfooding evidence with broader-population generalisation. Decision 2 (scoring dimensions): pure impact-tractability per the McKinsey template, holding RICE for Phase 2 LVT placement when packages get derived. Decision 3 (cross-cutting disciplines): distribute detection and the four-stage temporal lifecycle into per-sub-problem rationale rather than score them as separate items.

Two operator pushbacks during scoring sharpened the prioritised list. Sub-problem 3.4 (Delegation) scored low at first read because the scope was narrow (delegation to external humans only); the operator's reframe broadened scope to include delegation to the platform's AI agents alongside delegation to humans, lifting the score from 4 to 7. Sub-problem 5.5 (Trust history) scored lowest at first read; the operator's pushback recognised the meta-signal value (engagement evidence, trust-break learning, onboarding effectiveness) without disputing the late-stage timing, lifting the score from 5 to 6. Both pushbacks accommodated within the Prioritiser role's authored discipline without breaking.

Two scope expansions in the substrate-type matrix at sub-problem 1.1 emerged from operator review. Documents (Google Drive, OneDrive, Dropbox, Notion, local disk) and messaging (WhatsApp, iMessage, Slack, Telegram) joined calendar, email, notes, manual entry, and existing trackers as substrate types. The matrix at 1.1's sub-decomposition is now seven substrate types times four integration functions (read, observe, write, acknowledge) producing twenty-eight cells for Step 4 to sequence. Messaging additionally functions as a primary delivery interface for sub-problem 3.1's surfacing mechanics, carrying forward to Step 4 as a design constraint.

### Prioritised list

Scores reported as Impact / Tractability = Total. One-line rationale per sub-problem. Scores reflect the three pre-conversation decisions and the two operator-driven revisions noted above.

**Tier 1 (score 10): top quartile core**

- **1.3 State persistence** — 5 / 5 = 10. Portfolio-resets-each-session is exactly the Step 1 breakdown mode; database-per-tenant substrate already supports persistent state.

**Tier 2 (score 9): top quartile**

- **1.1 Substrate connection** — 5 / 4 = 9. Foundational for portfolio existence across seven substrate types; P6 ingestion substrate in place; calendar, email, and messaging MCP integrations tractable per deferred-decisions entries.
- **2.1 Methodology library** — 4 / 5 = 9. Differentiates platform from generic productivity tools; LVT, RICE, Kano, McKinsey 7-Step already authored on control plane; growth maintains primitives-versus-templates discipline.
- **3.1 Surfacing mechanics** — 5 / 4 = 9. The whisperer function lives here; messaging-first delivery as primary channel for busy-professional users; substrate-aware surfacing tractable.
- **5.1 Audit visibility** — 4 / 5 = 9. Phase 1 P10 audit substrate exists; surfacing to user is UI work; foundational for trust per D82.

**Tier 3 (score 8): top quartile inclusive cut**

- **1.5 User-authored items** — 3 / 5 = 8. CRUD-shaped input; user-authored items tend to be high-importance.
- **3.2 Drop-decision support** — 4 / 4 = 8. Where calibration becomes action; items-that-should-be-dropped is a load-bearing failure mode.
- **4.1 Mirror surface** — 5 / 3 = 8. Named in Step 1's success-measurement deliverable; depends on 4.2 and 4.3.
- **4.2 Goal-state tracking** — 4 / 4 = 8. Foundational for mirror; goals as items is tractable extension of portfolio state.
- **5.4 Intelligence-layer guardrails** — 4 / 4 = 8. D82 platform invariants exist; surfacing at decision points is structurally cheap.
- **6.3 Status veracity** — 4 / 4 = 8. Lower-pressure status options structurally simple; impact on portfolio accuracy high.

**Tier 4 (score 7): substantive but not top quartile**

- **1.4 Personal-versus-professional treatment** — 4 / 3 = 7. Design challenge more than technical.
- **2.2 Methodology-to-item binding** — 4 / 3 = 7. Critical for calibration; binding mechanics non-trivial under revision and load.
- **2.3 Pace inference per item** — 5 / 2 = 7. Rules-driven inference tractable; learned models out of Phase 2 envelope.
- **2.4 User-authored methodology surface** — 4 / 3 = 7. Bet's methodology-as-product depends on this; authorship UX non-trivial.
- **2.5 Calibration override mechanics** — 3 / 4 = 7. Override important but secondary to initial calibration quality.
- **3.3 Defer mechanics** — 3 / 4 = 7. Defer is a degenerate case of pacing; substrate exists.
- **3.4 Delegation (AI plus human)** — 4 / 3 = 7. Both delegation flavours (to platform agents; to other humans) in scope; AI delegation underpins Branch 3; human-delegation tracking is moderate complexity.
- **3.5 Consent granularity for platform actions** — 4 / 3 = 7. D82 intelligence-layer commitment requires it; mechanics nontrivial.
- **4.5 Feedback-to-platform** — 3 / 4 = 7. Preference management substrate.
- **5.2 Source attribution** — 3 / 4 = 7. P11 recommendation-with-citation substrate exists; UI extension.
- **5.3 Cost transparency** — 3 / 4 = 7. P4 cost-capture substrate exists; less critical at personal-use stage.
- **6.4 Methodology-fit lifecycle** — 5 / 2 = 7. Rhythm-and-key-change framing load-bearing for methodology-as-product claim; detection mechanics complex.
- **6.5 Correction mechanics** — 3 / 4 = 7. Low-friction correction; depends on audit substrate.

**Tier 5 (score 6)**

- **4.3 Value-versus-time accounting** — 4 / 2 = 6. Time-tracking tractable; defining value per item per methodology is hard.
- **4.4 Pattern surfacing** — 3 / 3 = 6. Useful but late-stage; needs accumulated run-history.
- **5.5 Trust history** — 3 / 3 = 6. Late-stage refinement; meta-signal value (engagement evidence; trust-break learning; onboarding effectiveness) informs other branches' improvement loops.
- **6.1 Signal verification** — 3 / 3 = 6. Important for accuracy; secondary to having signals at all.

**Tier 6 (score 5)**

- **1.2 Item identity reconciliation** — 3 / 2 = 5. Crude duplicates tolerable initially; entity resolution across heterogeneous substrates is a known hard problem.
- **6.2 Compliance-signal detection** — 3 / 2 = 5. Requires accumulated signal data; cannot bootstrap.

### Top quartile flagged

Top quartile of 30 sub-problems is 7-8 items. The score distribution produces a clean cut at five items (Tiers 1 plus 2; score ≥ 9). Extending the inclusive reading to eleven items (Tiers 1 through 3; score ≥ 8) captures the substantive priority set without diluting focus. Step 4's workplan operates on the eleven-item inclusive set as the planning surface, with the five-item core treated as the load-bearing priority.

**Top quartile, strict cut (5 items):** 1.3 State persistence, 1.1 Substrate connection, 2.1 Methodology library, 3.1 Surfacing mechanics, 5.1 Audit visibility.

**Top quartile, inclusive cut (11 items, adds Tier 3):** 1.5 User-authored items, 3.2 Drop-decision support, 4.1 Mirror surface, 4.2 Goal-state tracking, 5.4 Intelligence-layer guardrails, 6.3 Status veracity.

### Self-challenge

**Dependency awareness.** The top tier concentrates in Branch 1 foundational items (1.1, 1.3, 1.5), Branch 2 library entry-point (2.1), Branch 3 action surface (3.1, 3.2), Branch 4 feedback substrate (4.1, 4.2), Branch 5 trust foundation (5.1, 5.4), and Branch 6 status-veracity (6.3). This is consistent with the dependency ordering from Step 2: Branch 2 depends on Branch 1; Branches 3-4 depend on Branches 1-2; Branch 6 depends on signal sources from others. The ranking respects dependency naturally. Step 4 sequences within this priority set respecting both score order and dependency order.

**Operator-as-first-instance framing held throughout.** Sub-problems with high operator-specific impact and lower broader-population generalisation scored lower than sub-problems that serve both. 6.4 (Methodology-fit lifecycle) scored impact 5 because the rhythm-and-key-change framing is load-bearing for the broader-population test condition; for pure operator-only the impact would be lower.

**Rules-versus-learned tractability framing held.** Sub-problems 2.3 (Pace inference) and 6.4 (Methodology-fit lifecycle) scored tractability 2 because learned-model approaches are out of Phase 2's resource envelope; rules-driven approaches keep them tractable at the lower end. Step 4 commits to rules-driven approaches at workplan time.

**Items with disputed scoring noted explicitly.** 3.4 (Delegation) and 5.5 (Trust history) were revised mid-conversation per operator pushback; the rationale captures the scope clarification (3.4) and meta-signal recognition (5.5) so the audit trail surfaces the iteration cleanly.

### Dogfooding-evidence record

The McKinsey 7-Step Prioritiser role authored at S26b per D85 carries a function-focused system_prompt committing the role to impact-tractability scoring with top-quartile flagging. The McKinsey override added the impact-tractability matrix and top-quartile threshold. Posture 1.5 structural dogfooding without agent runtime continued from Steps 1 and 2. This is the third instance of the structural-dogfooding pattern across three distinct roles (ProblemFramer at Step 1, Disaggregator at Step 2, Prioritiser at Step 3).

What the template informed. The "score each branch on impact and tractability; produce a ranked list with the top branches flagged as priorities" discipline held cleanly. The conversation produced 1-5 scores across both dimensions for thirty sub-problems with one-line rationale per item, ranked in score order, with the top-quartile cut explicitly framed. The "you do not solve sub-problems; you order them" discipline held; the conversation resisted moving into solution architecture even when scoring rationale touched implementation considerations. The matrix shape per the McKinsey override produced clean tier clustering at scores 10, 9, 8, 7, 6, 5; the top quartile cut emerged from the tier structure rather than from arbitrary numeric threshold.

Where the template's scope did not cover the work. Five extensions surfaced during the conversation that the McKinsey 7-Step Prioritiser role's system_prompt does not encode. First, scoring-dimension choice (impact-tractability versus impact-tractability-plus-confidence versus full RICE) required an operator decision; the role's authored discipline picks one (impact-tractability) without surfacing the alternative dimensions the conversation actually has access to. Second, population-scope choice (operator-only versus broader-population versus operator-as-first-instance) required an operator decision; the role does not surface that impact scoring varies with population framing. Third, cross-cutting discipline treatment (score separately versus distribute into rationale) required an operator decision; the role does not specify how to handle cross-cutting issues within the matrix. Fourth, dependency-aware scoring across the issue tree is implicit in the conversation but not explicit in the role; tractability scores naturally lower for sub-problems with unmet dependencies, but the role's discipline does not name this. Fifth, mid-scoring revision through operator pushback (sub-problems 3.4 and 5.5) is methodologically normal but not named in the role's discipline; the role describes scoring as if it were a single pass.

What this surfaces for Phase 2 methodology work. The Prioritiser role's authored discipline is narrower than the prioritisation work this conversation needed, consistent with the pattern observed at ProblemFramer (Step 1) and Disaggregator (Step 2). The three roles together produce a coherent procurement-grade-evidence pattern: the methodology aggregate's authored content is structurally sound and extensible, but each role's authored discipline scope is narrower than the substantive discipline the conversation applies. Phase 2 methodology work has two distinct workitem candidates: short-term, expand the role system_prompts to encode the discipline-extensions explicitly (population scope, scoring dimensions, cross-cutting treatment, dependency awareness, revision mechanics); long-term, layer skills per role per the Phase 2 deferred surface, with each role gaining methodology-specific skills that encode the extensions cleanly.

What this tells us about the bet's claim. The methodology-template-extensibility-without-breaking pattern reaches three instances across three distinct roles at this Step 3 close. The bet's procurement-grade methodology-embedding claim now has substantial structural-level evidence; the pattern's consistency across roles strengthens the case that the methodology aggregate as authored on the control plane is genuinely extensible by operators and agents alike, not just operationally workable in one case. Agent-runtime evidence remains untested through all three Steps. Phase 2 UX surface for methodology adoption plus agent runtime exercising the Prioritiser end-to-end would close the higher bar; until then, three-instance structural evidence is the procurement-grade artifact.

### Carry-forward to Step 4 (Planner)

Five open questions land at Step 4:

1. **Workplan granularity.** Step 4 produces a workplan for the top quartile (strict cut: 5 items; inclusive cut: 11 items). Granularity per item: per-sub-problem versus per-priority-cluster. The strict-versus-inclusive cut choice affects this; smaller set permits per-sub-problem depth, larger set may need clustering.

2. **Substrate-type × integration-function matrix sequencing at 1.1.** The twenty-eight cells require workplan sequencing. Calendar-read and email-read might be Phase 2-A; messaging-write might wait for stronger consent substrate; document-observe might depend on additional substrate work. Step 4's workplan ranks the cells within sub-problem 1.1.

3. **Dependency versus priority within the workplan.** State persistence (1.3) and substrate connection (1.1) are top priority AND foundational; calibration and feedback sit on top of them. Step 4 sequences within the prioritised set respecting both score order and dependency order; the two ordering principles may conflict and the workplan resolves the conflict.

4. **Lifecycle-stage prioritisation strategy.** From Step 2's carry-forward, sharper now. The four-stage discipline (find rhythm, settle in, watch, adapt) applies at every prioritised sub-problem. Step 4 decides whether Phase 2 ships find-rhythm-plus-settle-in stages across all priority items first (with watch and adapt later), or full-lifecycle support for fewer items first. Different commercial test conditions.

5. **Messaging-first delivery design constraint and meta-signal observability.** Carryforward design commitments: workplan items in Branch 3 default to messaging-first delivery; trust-history (5.5) sequences as observability work informing other branches' iteration cadence rather than as standalone feature work.

### Step 3 close

Step 3 closes with thirty sub-problems scored on impact and tractability, top quartile flagged at both strict (5 items) and inclusive (11 items) cuts, dogfooding-evidence record at third-instance evidence of the methodology-template-extensibility-without-breaking pattern, and five open questions carrying forward to Step 4. The Prioritiser role's discipline produced a usable prioritisation that respected dependency, accommodated operator pushback, and held the structural test condition (operator-as-first-instance of broader busy-professional population) throughout. Step 4 (Plan) opens at Claude.ai with the top quartile as the workplan surface plus the five open questions as planning inputs. The Step 4 pre-conversation brief authors at `briefs/phase-2/design-7step-step-4.md` before the Claude.ai conversation opens, continuing the briefs/ discipline restoration test from Step 3.
