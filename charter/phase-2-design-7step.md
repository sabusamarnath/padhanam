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
