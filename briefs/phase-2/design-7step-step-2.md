# Phase 2 design — McKinsey 7-Step — Step 2 (Disaggregate)

**This brief is a synthetic retrospective construction.** Drafted at the Step 2 commit session rather than before the Step 2 conversation. Unlike the Step 1 brief at `briefs/phase-2/design-7step-step-1.md`, which was a formal opening prompt the Claude.ai conversation read before substantive work began, Step 2 transitioned from Step 1 close to Step 2 open within the same Claude.ai conversation. No separate opening prompt existed. To honour the briefs/ preservation discipline restored at Step 1 (after a three-block lapse since P9 open), this retrospective brief documents Step 2's intent, inputs, and discipline. The synthetic nature is flagged here as honest framing; future Step briefs should be authored before the corresponding Claude.ai conversation opens to avoid the retrospective shape.

## Intent

Apply Step 2 of the McKinsey 7-Step Framework (Disaggregation via the Disaggregator role authored at S26b per D85) to Step 1's sharpened problem statement, producing a MECE issue tree with branches and sub-branches at granularity workable for Step 3's impact-tractability scoring. Posture 1.5: structural dogfooding without agent runtime dependency. The conversation reads the Disaggregator role's specification and holds the discipline manually.

## Inputs

The three Step 1 artefacts at `charter/phase-2-design-7step.md` Step 1 section:

1. The sharpened problem statement (problem paragraph plus two context paragraphs)
2. The initial-disaggregation paragraph (seven sub-problem candidates) plus Step 2 disaggregator handoff note
3. The two open questions for Steps 2 and 3 (substrate-integration cut at Step 2; population scope at Step 3)

Plus the McKinsey 7-Step methodology template at `briefs/p8/mckinsey-7-step.md`, specifically the Disaggregator role section.

## Discipline

The Disaggregator role's system_prompt: "You decompose problems into structured component trees. Your job: receive a sharpened problem from the ProblemFramer; produce a structured decomposition where each branch represents a distinct sub-problem and branches together are collectively exhaustive. The decomposition is the input the Prioritiser uses to rank tractability. You do not solve sub-problems; you structure them."

The McKinsey override: "Apply MECE (Mutually Exclusive, Collectively Exhaustive) decomposition; produce an issue tree."

The conversation iterates through structural refinements as operator insights surface; the assistant resists moving into solution territory and resists pre-emptive prioritisation; the issue tree converges through multiple cycles. Blank-sheet discipline within the bet's success criteria continues per Step 1's Decision 2.

## Dogfooding-evidence record discipline

Same shape as Step 1's dogfooding-evidence record. The assistant notes throughout the conversation how the Disaggregator role's content informed the work; at conversation close, drafts the dogfooding-evidence record as substantive prose against the procurement-grade evidence question: did Padhanam's own methodology authoring (the McKinsey 7-Step Disaggregator role) produce content that worked at a real Phase 2 disaggregation problem, or did the conversation operate on general McKinsey framework knowledge irrespective of what was authored on the control plane?

## Conversation closing

At Step 2 close, the assistant produces:

1. The disaggregated issue tree (branches plus sub-branches with one-sentence definitions)
2. Cross-cutting disciplines section if any surfaced
3. Self-challenge summary (MECE check; exclusions; altitude check)
4. The dogfooding-evidence record (substantive prose)
5. Carry-forward to Step 3 (open questions for prioritisation)
6. Step 2 close paragraph

Plus a brief paragraph naming the next session in the arc (Step 3 Prioritisation) and any open questions Step 2 surfaced for Step 3 specifically.

The drafted artefacts get committed via a subsequent short Claude Code session whose brief takes the artefacts as paste-ready content inline (per the placeholder-versus-content-payload methodology miss flagged at Step 1).
