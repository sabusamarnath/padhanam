# Phase 2 design — McKinsey 7-Step — Step 6 (Synthesise)

Strategic-mode conversation applying Step 6 of the McKinsey 7-Step Framework to the findings produced at Step 5. Sixth session in the multi-session arc that produces the Phase 2 strategic shape. Posture 1.5 continues: structural dogfooding of the McKinsey 7-Step methodology template authored at S26b without agent runtime dependency. The conversation reads the Synthesiser role's specification and follows its synthesis discipline deliberately.

This brief is authored pre-conversation in the Step 5 close thread, continuing the briefs/ discipline test from Steps 3, 4, and 5. Step 5's fresh-thread element strengthened the pattern to three-instance evidence. Step 6 authoring in the Step 5 close thread tests whether brief-authoring discipline carries regardless of which thread produces it, provided the Step 6 substantive conversation opens in a fresh standalone thread without inheriting prior conversation context.

## Three methodology streams operating in parallel

The Step 6 conversation touches three distinct methodology streams that share the word "methodology" but are structurally separate. Naming them explicitly at the brief opening prevents conflation.

**Build methodology** at `charter/methodology.md`. How Padhanam itself is built. The 7-Step arc is a build-methodology instance. Audience: senior product leaders adopting the discipline per `bet.md` line 67.

**Product methodology** at `charter/product-methodology.md`. What the platform encodes for users at the agent layer. The thirty sub-problems from Step 2, the top quartile prioritisation from Step 3, the eleven workplan entries from Step 4, and the eleven sub-problem findings plus cross-cutting work from Step 5 all sit in this stream. Audience: senior leaders at established firms augmenting human EA/CoS plus founders at early-stage tier or Series A/B scale-ups per the Step 5 ICP commitment at `charter/phase-2-user-segment.md`.

**Methodology aggregate as control-plane construct** at `contexts/methodology/` per D86. The technical substrate the build-methodology uses to design product-methodology capabilities. The McKinsey 7-Step methodology at S26b lives here.

Step 6 touches all three. Synthesis work runs at build-methodology altitude; the integrated storyline informs product-methodology shape; the control-plane aggregate is the substrate. The conversation holds all three streams distinct and surfaces interactions explicitly.

## What this conversation produces

Three drafted artefacts that a subsequent Claude Code commit session lands as a Step 6 section at `charter/phase-2-design-7step.md`:

1. **Sixteen carry-forward question dispositions.** For each of the sixteen carry-forward questions Step 5 surfaced, Step 6 produces a decision: commit at Phase 2-A as architectural primitive, defer to Phase 2-B operational delivery, carry to Phase 3, or close-as-confirmed (where Step 5 produced a clear read and Step 6 confirms without revision). Decisions land with explicit reasoning. Where the disposition is "commit," the landing surface is named (D-entry, principles.md addition, architecture.md addition, new charter file). Where the disposition is "defer" or "carry," the activation trigger or activation timeline is named.

2. **Integrated storyline addressing the Step 1 problem statement.** Pyramid principle structure per the McKinsey override on the Synthesiser role. Top-line answer to the Step 1 problem (busy professionals with portfolio of work and personal goals; calibration breakdown under load; missing judgment applied to the portfolio at the right moments). Supporting arguments. Evidence trail citing Step 2 disaggregation, Step 3 prioritisation, Step 4 workplan, Step 5 findings. The storyline becomes Step 7 (Communicate) input.

3. **Phase 2 LVT placement plus Phase 2 package structure.** Phase 2 as initiative in the LVT per D44. Phase 2-A and Phase 2-B as sub-initiatives or single initiative with package structure (Step 5's read on Q5 is single initiative with package structure reflecting four sequencing waves; Step 6 confirms or revises). Package structure within Phase 2 aligned with the four sequencing waves from Step 5 Work-stream 3, with each package's epic-level deliverables named. Cluster B9 (methodology authoring extensions) sequencing independence per Step 5's Q7 read confirmed or revised. Phase 2-B Wave 4 versus Phase 3 boundary decided per Step 5's Q8.

Plus two close deliverables:

4. **Dogfooding-evidence record for Step 6 (substantive prose).** Sixth instance of the structural-dogfooding pattern. Sixth instance of the methodology-template-extensibility-without-breaking test. The pattern is at five-instance firmly-evidenced after Step 5 (the strongest single piece of evidence for the bet's procurement-grade methodology-embedding claim accumulated to date). Step 6's outcome either continues the pattern (six-instance firmly-evidenced; Cluster B9 commitment becomes Phase 2-B priority) or breaks it (different signal worth recording at Phase 2 audit time; Cluster B9 sequencing reconsidered). Step 6 also tests cross-role coordination at structural altitude (Synthesiser takes Analyst findings as input; the multi-role workflow exercise even without agent runtime).

5. **Carry-forward to Step 7 (Communicate).** Open questions Step 6 surfaces for the communicate step's narrative-shaping work. Possible questions: stakeholder audience for the storyline (case-study reader per bet versus senior leader deciding adoption versus engineering team executing); narrative density (executive summary versus full storyline); supporting artefact set (charter pointers; diagram set if any; methodology-as-product pitch shape).

## Context to read first via project_knowledge_search

In order:

1. `charter/phase-2-design-7step.md`. Steps 1, 2, 3, 4, 5 sections in full. Particularly the eleven sub-problem findings from Step 5 Pass 1, the five architectural patterns from Step 5 Pass 2 Work-stream 2 (revision-with-lineage saturated; conversation flow across-the-board; three-tier consent-and-awareness framework with native specification at sub-problem 5.4; tiered-by-salience candidate at six instances; two-vector decay model candidate at three instances operator-articulated), the four Phase 2-A sequencing waves from Work-stream 3, the ten Phase 2-B clusters with four sequencing waves and Tier 4 activation map from Work-stream 4, the dogfooding-evidence record from Pass 3, and the sixteen carry-forward questions including the late-added Q14 latency-tier inference routing.

2. `charter/phase-2-user-segment.md`. The senior-leader ICP commitment per Step 5 Decision 1. Three-population segment; vertical-wedge candidates for Phase 3; Phase 2-A substrate priorities derived from segment.

3. `briefs/p8/mckinsey-7-step.md`. The Synthesiser role's authored specification, constraints, and expected outputs. Function-focused system_prompt commits the role to integrating findings into coherent narratives with explicit logical flow; passing storyline to the Communicator; not producing new analyses. McKinsey override layered pyramid-principle discipline.

4. `charter/bet.md`. Strategic intent; success criteria; case-study-reader audience commitment at line 67; the agent-layer-meets-users framing that the integrated storyline must address.

5. `charter/principles.md`. User safety section; intelligence-layer commitment; consent-granularity principle. Step 6 candidate additions surface from architectural pattern commit decisions.

6. `charter/methodology.md` (build methodology). Brief-authoring discipline candidate for promotion to charter-grade methodology line.

7. `charter/product-methodology.md` (product methodology). Four professional functions framework; the surface the integrated storyline shapes.

8. `charter/architecture.md`. The substrate Phase 2 package structure builds on. Architectural pattern landing-surface candidates.

9. `charter/packages.md`. Existing LVT package structure; Phase 2 placement candidates.

10. `charter/decisions.md`. Specifically D4 (LiteLLM gateway; latency-tier routing question's home), D14 (customer-deployment; latency-tier routing's procurement-grade implication), D24 (tenant isolation), D26 (append-only audit), D31 (revisions pattern), D32 (database-per-tenant), D44 (RICE plus living roadmap; LVT placement substrate), D75 (agent aggregate), D77 (calendar/email tool service deferred entries), D78 (personal-use deployment), D80 (four-layer constraint stack; latency-tier routing's architectural-layer placement), D81 (methodology aggregate v2), D82 (intelligence-layer commitment plus platform invariants), D85 (McKinsey 7-Step methodology authoring placement), D86 (role-first model), D87 (override-mode space), D93 (Phase 2 direction methodology-as-product), D102 (audit context), D113 (latest entry).

11. `charter/competitors.md`. Twenty-two-entry competitor catalog. Reference for storyline's market-positioning framing. Distinguishes assistant-layer from infrastructure-layer (where Doubleword research from Step 5 close thread would land if vendor-level disposition were picked up; currently pending).

12. `charter/deferred-decisions.md`. Phase 3 candidates including potential Doubleword catalog addition. Reference for Q8 Phase 2-B Wave 4 versus Phase 3 boundary decisions and Q14 carry-to-Phase-3 option.

13. `log/captures.md`. Mass-market-UX commitment; use-case-portfolio entry; primitives-versus-templates throughline; consumer-direction architectural-exploration historical context.

14. `log/sessions.md`. Latest entry is the Step 5 commit (sixteen carry-forward questions; five-instance methodology-extension evidence). Reflection prompts (five answered) and methodology lines (four observed). The five-instance methodology-extension evidence claim sits in this entry.

## Pre-conversation operator decisions

None. Step 6 is synthesis work end-to-end. All sixteen carry-forward questions are analytical work for the conversation. Step 5's Decision 1 (ICP landing surface) was pre-conversation because the answer shaped how Step 5's analytical work surfaced ICP-related findings; Step 6 has no structurally analogous decision. The integrated storyline plus carry-forward dispositions plus Phase 2 LVT placement all emerge from the synthesis discipline running over the Step 5 inputs.

## Conversation discipline expected

The McKinsey 7-Step Synthesiser role frames "integrate findings into coherent narrative with explicit logical flow" with specific discipline. The conversation applies this deliberately, with the assistant surfacing the methodology's synthesis prompts and the operator articulating answers per work-stream.

The pyramid principle override drives storyline construction top-down: top-line answer to the Step 1 problem given Step 5 findings; supporting arguments below; evidence trail at the base. This is the McKinsey-specific synthesis discipline that distinguishes Step 6 from a generic "summarise and conclude" pattern.

Three analytical work-streams the conversation produces findings on.

### Work-stream 1: Sixteen carry-forward question dispositions

The conversation walks through the sixteen Step 5 carry-forward questions in groups. For each question: confirm Step 5 read (where Step 5 produced one) or run synthesis-altitude work to produce decision; name landing surface for commits (D-entry, principles.md addition, architecture.md addition, new charter file); name activation trigger or timeline for defers.

Groups for sequencing:

(a) **Architectural patterns (Q1-Q4).** Five patterns to dispose: revision-with-lineage; conversation flow; three-tier consent-and-awareness framework; tiered-by-salience candidate; two-vector decay model candidate. Step 5 read: commit all five. Step 6 confirms or revises; names landing surface per pattern; settles standard-interfaces-versus-descriptive-patterns question for revision-with-lineage and conversation flow; names patterns (three-tier consent-and-awareness and tiered-by-salience both flagged as wordy at Step 5).

(b) **Sequencing and clustering (Q5-Q9).** Phase 2-A as single initiative or two sub-phases; WhatsApp template approval timing; Cluster B9 sequencing independence; Phase 2-B Wave 4 versus Phase 3 boundary; Tier 4 sub-problem activation triggers. Step 5 reads largely lean toward Step 6 confirmation; Step 6 confirms or revises.

(c) **Operator refinements (Q10-Q14).** Identity-fork schema-based threshold; methodology authoring scope sequencing; twelve event classes confirmation; no-silent-operation as charter-grade principle; latency-tier inference routing as Phase 2-A architectural primitive. The latency-tier question is the substantial one; Step 6 decides commit at Phase 2-A, defer to Phase 2-B operational delivery, or carry to Phase 3. Step 6 also weighs Phase 1 retrofit consideration versus Phase 2 architectural extension; the LiteLLM abstraction at D4 has the slot but does not fill it.

(d) **Bet-level (Q15-Q16).** Five-instance structural-dogfooding evidence plus agent-runtime evidence untested; Cluster B9 elevation above other Phase 2-B clusters. Step 6 decides whether agent-runtime exercise of McKinsey 7-Step is in Phase 2-B scope or defers to Phase 3, and whether Cluster B9 elevation above other Phase 2-B clusters is warranted given the bet's procurement-grade methodology-embedding claim depends on it.

### Work-stream 2: Integrated storyline construction

Pyramid principle from the McKinsey override. Top-down construction.

(a) **Top-line answer.** What is the integrated answer to the Step 1 problem statement (busy professionals with portfolio of work and personal goals; calibration breakdown under load; missing judgment applied to the portfolio at the right moments) given Step 5 findings plus Step 6 carry-forward dispositions? Single sentence or short paragraph. This is the storyline's apex.

(b) **Supporting arguments.** Three to five arguments that, together, support the top-line answer. Each argument grounds in Step 5 findings (Pass 1 sub-problem analyses) and Step 2-4 substrate (disaggregation, prioritisation, workplan). Arguments structure the middle layer of the pyramid.

(c) **Evidence trail.** What in Step 5 findings, Step 4 workplan, Step 3 prioritisation, Step 2 disaggregation, Step 1 problem framing supports each argument. The base of the pyramid; the substrate Step 7 (Communicate) draws from when shaping narrative for stakeholder consumption.

The storyline becomes the Step 7 input. Step 7 shapes it for specific stakeholder audiences (case-study reader, senior leader deciding adoption, engineering team executing); Step 6 produces it at canonical altitude.

### Work-stream 3: Phase 2 LVT placement plus package structure

Phase 2 as initiative in the LVT per D44. The placement decision: where does Phase 2 sit within the broader Padhanam LVT structure (Phase 1 closed; Phase 2 active; Phase 3 candidate)?

Phase 2 package structure: aligned with the four sequencing waves from Step 5 Work-stream 3 (Wave 1 foundational; Wave 2 calendar/email/methodology core; Wave 3 messaging plus user-facing surface; Wave 4 surfacing/drop/mirror). Each package's epic-level deliverables named from the Step 5 work-stream output. Cluster B9 (methodology authoring extensions) treatment as parallel work-stream alongside engineering or as part of engineering package structure per Step 5 Q7.

Landing surface for the LVT placement record: candidate `charter/packages.md` updated with Phase 2 package structure; candidate new D-entry in `charter/decisions.md` committing Phase 2 LVT placement; candidate Step 6 section content at `charter/phase-2-design-7step.md` as primary record with `charter/packages.md` reference.

## Reflection prompts at session close

Six reflection prompts plus optional methodology lines worth observing.

1. **Methodology-template fidelity check.** Did the McKinsey 7-Step Synthesiser role's discipline hold for the synthesis run at Step 6? Did the "integrate findings into coherent narrative; do not produce new analyses; pass storyline to Communicator" framing match the work? Where did the template's discipline fall short?

2. **Methodology-template-extensibility-without-breaking test.** Sixth instance. Pattern continuation produces six-instance firmly-evidenced pattern (the strongest evidence accumulating); pattern break produces different signal worth Phase 2 audit treatment. Step 6 is where cross-role coordination becomes most acute (Synthesiser receives Analyst findings; the multi-role workflow exercise even without agent runtime tests cross-role coordination feasibility).

3. **Pyramid principle application check.** Did the storyline construction hold the pyramid principle (top-line answer first; supporting arguments; evidence trail)? Or did the storyline drift to problem-first or solution-first or evidence-first construction? McKinsey override discipline test.

4. **Posture 1.5 sustainability check.** Did Posture 1.5 deliver substantive synthesis value at Step 6? The Synthesise step is where Posture 1.5's structural-only test condition is most acute on the multi-role coordination dimension (agent runtime would enable Planner-to-Analyst-to-Synthesiser workflow exercise; structural dogfooding cannot test that workflow). Where did Posture 1.5 deliver? Where did absence of multi-role workflow exercise constrain the synthesis?

5. **Briefs/ discipline check.** Brief authored before substantive Step 6 work AND in the Step 5 close thread (not a fresh standalone thread). Step 6 substantive conversation opens in fresh thread without inheriting prior conversation context. The four-instance pattern (Steps 3, 4, 5, 6 author brief pre-substantive-work) plus Step 5's fresh-thread + Step 6's Step-5-close-thread test the discipline's flexibility about which thread produces the brief.

6. **Sixteen carry-forward disposition completeness check.** Did Step 6 dispose of all sixteen Step 5 carry-forward questions (commit/defer/Phase 3/close-confirmed for each)? Or did some carry to Step 7 (Communicate) unresolved? Disposition completeness is the Synthesise step's primary deliverable test.

Plus optional methodology lines worth observing: any structural or procedural patterns the conversation surfaces that warrant methodology document treatment. Candidate observations: pyramid-principle-application discipline; carry-forward-disposition-as-synthesis-substrate pattern; multi-pass synthesis (carry-forwards first, storyline second, package structure third) versus single-pass synthesis.

## What this conversation does not do

- Run agent-execution analyses (deferred to Phase 2 build sessions per Posture 1.5).
- Communicate the storyline to stakeholders (Step 7 Communicate output).
- Author the Step 7 brief (separate work; pre-Step-7).
- Modify Step 5 findings or Step 4 workplan entries (Step 5 and Step 4 sections are inputs; Step 6 synthesises across them but does not edit them).
- Dispose of the pending Doubleword vendor-level captures (competitors.md addition; deferred-decisions.md Phase 3 capture). These were deferred at Step 5 close thread; Step 6 may reference them as context but does not land them as part of Step 6 commit.
- Pick up the stale "P11 framed; S39 next" header at `charter/current-package.md` line 5 (pre-existing structural drift; out of scope per cleanup-session pattern).
- Decide Phase 3 strategic shape (Phase 3 strategic-mode block; not Phase 2 design work).
- Commit Step 6 charter edits directly (Claude Code commit session after Step 6 substantive conversation closes; matching Steps 1-5 pattern).
