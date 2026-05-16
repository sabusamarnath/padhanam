# Phase 2 design — McKinsey 7-Step — Step 3 (Prioritise)

Strategic-mode conversation applying Step 3 of the McKinsey 7-Step Framework to the issue tree produced at Step 2. Third session in the multi-session arc that produces the Phase 2 strategic shape. Posture 1.5: structural dogfooding of the McKinsey 7-Step methodology template authored at S26b without agent runtime dependency. The conversation reads the Prioritiser role's specification and follows its impact-tractability discipline deliberately.

This brief is authored pre-conversation, restoring full briefs/ discipline after the synthetic-retrospective shape at Step 2's brief. The pattern-recurrence test from Step 2's session log entry passes if this brief lands before the Claude.ai conversation opens; the synthetic-retrospective-brief pattern stays at single instance.

## What this conversation produces

Three drafted artefacts that a subsequent Claude Code commit session lands as a Step 3 section at `charter/phase-2-design-7step.md`:

1. **The prioritised list of sub-problems with impact-tractability scores.** Each of the thirty sub-problems from Step 2's issue tree (six branches × five sub-branches) gets an impact score and a tractability score. The top quartile (top seven or eight sub-problems) flagged as priorities. Score rationale captured per sub-problem so the audit trail survives.

2. **Dogfooding-evidence record for Step 3 (substantive prose).** Third instance of the structural-dogfooding pattern, third instance of the methodology-template-extensibility-without-breaking test. Did the Prioritiser role's authored content work at the actual prioritisation problem, or did the conversation operate on general McKinsey framework knowledge? The dogfooding-evidence record names this honestly.

3. **Carry-forward to Step 4 (Planner).** Open questions Step 3 surfaces for the planning step's workplan construction.

## Context to read first via project_knowledge_search

Search for and read systematically:

1. `charter/phase-2-design-7step.md`. Step 1 and Step 2 sections in full. Step 1's sharpened problem statement plus context paragraphs; Step 2's six-branch × five-sub-branch issue tree plus the two cross-cutting disciplines (detection; the four-stage temporal lifecycle of find rhythm, settle in, watch, adapt).
2. `briefs/p8/mckinsey-7-step.md`. The Prioritiser role's authored specification, constraints, and expected outputs. Specifically the function-focused system_prompt: "You prioritise sub-problems from a decomposition tree... score each branch on impact (how much resolving this moves the overall problem) and tractability (how feasible resolving this is in available time and resources); produce a ranked list with the top branches flagged as priorities. You do not solve sub-problems; you order them." Plus the McKinsey override: "Use impact-tractability matrix; flag the top quartile as priorities."
3. `charter/bet.md`. Strategic intent the design serves; the bet's six success criteria are the impact-scoring backbone for sub-problems that connect to bet-level claims.
4. `charter/principles.md`. User safety section; Padhanam-as-intelligence-layer commitment; methodology-embedded-not-gated principle.
5. `charter/methodology.md`. Framework discipline including RICE convention at package-level; relevant for Decision 2 below.
6. `charter/product-methodology.md`. Four professional functions framework; relevant for Branch 2 (Pace calibration) scoring.
7. `charter/p12-phase-2-inputs.md`. Phase 2 substrate-completion candidates plus Phase 2-entry hygiene workitems; relevant for tractability scoring on Branch 1 substrate connection sub-problems.
8. `charter/decisions.md`. Specifically D44 (strategic-tree LVT pattern with reasoning categories), D82 (platform invariants and intelligence-layer commitment), D85 (McKinsey 7-Step methodology authoring placement), D93 (Phase 2 direction methodology-as-product).
9. `log/captures.md`. The mass-market-UX-as-Phase-2-commitment entry; the use-case-portfolio entry recording the eleven use cases from the rejected separate-consumer-build path.

## Pre-conversation operator decisions

Three decisions to confirm before substantive Step 3 work begins:

### Decision 1: Population scope for impact scoring

Impact assessment depends on the user population the platform serves. Three options:

(a) **Operator-only impact scoring.** Score sub-problems on what helps the operator's specific Private Assistant use cases the most. Narrower scope; sharper for dogfooding evidence; weaker for broader-population evidence.

(b) **Broader busy-professional population scoring.** Score on what helps the busy professional carrying twelve-plus hour day load most. Wider scope; weaker for operator-specific dogfooding; stronger for generalisation evidence.

(c) **Operator as first instance of broader population.** Score on what helps the operator AND generalises to the broader population. The operator dogfoods first; the impact score reflects both immediate operator value and generalisation potential.

**Recommend (c).** The bet's case-study claim (procurement-grade methodology-embedding) requires evidence that the methodology travels beyond the operator; the broader-population test condition is load-bearing. The operator's dogfooding is the first instance, not the whole. Sub-problems that serve the operator but do not generalise score lower than sub-problems that serve both. Operator decides.

### Decision 2: Scoring dimensions

The McKinsey 7-Step template specifies impact-tractability (2D matrix). The project's strategic-tree convention uses RICE (Reach, Impact, Confidence, Effort) per D44 at package-level prioritisation. Three options:

(a) **Pure impact-tractability per McKinsey template.** Score each sub-problem on impact (1-5) and tractability (1-5). Top quartile flagged. Honours the McKinsey 7-Step methodology dogfooding faithfully.

(b) **Impact-tractability-plus-confidence.** Add a confidence dimension to the McKinsey 2D matrix. Confidence captures how sure the prioritisation is, given evidence quality.

(c) **Full RICE per project convention.** Score on Reach, Impact, Confidence, Effort. Connects to the project's broader prioritisation language; RICE is what packages will be scored against at Phase 2 LVT placement.

**Recommend (a).** The conversation is dogfooding the McKinsey 7-Step Prioritiser role; layering RICE on top departs from the role's authored discipline and weakens the structural-dogfooding evidence. RICE comes in later at Phase 2 LVT placement when packages get derived from the prioritised Step 3 + 4 outputs. Operator decides; if (c) wins, the conversation must explicitly note where it departed from McKinsey discipline so the dogfooding-evidence record stays honest.

### Decision 3: Treatment of cross-cutting disciplines

The four-stage temporal lifecycle and detection apply at every sub-branch as cross-cutting disciplines per Step 2. Two scoring approaches:

(a) **Score cross-cutting disciplines as separate items.** Detection and the four-stage lifecycle each get their own impact-tractability score. The thirty sub-problems plus two cross-cutting items make thirty-two scored items. Top quartile applies across all thirty-two.

(b) **Distribute cross-cutting disciplines into sub-problems.** Each sub-problem's impact-tractability score includes the cross-cutting-discipline implications. The thirty sub-problems are the scored set; the cross-cutting disciplines are scoring inputs, not scored items.

**Recommend (b).** The cross-cutting disciplines are not separable work items; they are properties of how the sub-problems get implemented. Scoring them separately produces phantom items the Planner cannot construct a workplan against. Operator decides.

## Conversation discipline expected

The McKinsey 7-Step Prioritiser role frames "rank by impact and tractability" with specific discipline. The conversation applies this deliberately, with the assistant surfacing the methodology's scoring prompts and the operator articulating answers per sub-problem:

**Impact: how much does resolving this sub-problem move the overall problem (the calibration-breakdown-under-load problem from Step 1)?** The sub-problem's impact connects to one or more of the bet's success criteria plus the user-side measures named at Step 1's success-measurement deliverable. Sub-problems that move the calibration breakdown most score highest.

**Tractability: how feasible is resolving this in available time and resources?** Phase 2's resource envelope is the operator plus Claude Code working at the cadence of Phase 1. Sub-problems requiring substrate that does not yet exist (some integration paths; some methodology surfaces) score lower tractability. Sub-problems that build cleanly on Phase 1's substrate score higher.

**Cross-branch dependency awareness.** Branch 2 depends on Branch 1; Branch 3 depends on Branch 2; Branch 4 depends on Branches 1-3; Branch 6 depends on signal sources from other branches. Tractability scoring respects dependency or flags it explicitly when scoring out of dependency order.

**Lifecycle-stage prioritisation.** The four-stage discipline (find rhythm, settle in, watch, adapt) applies at every branch. Step 3's prioritisation produces input for Step 4's workplan. Step 3 must decide whether Phase 2 ships find-rhythm-plus-settle-in stages across all branches first, or full-lifecycle support for fewer branches first. This decision lives inside the prioritisation rationale per sub-problem.

The conversation iterates. Initial scores get challenged; revisions surface; the prioritised list converges through multiple cycles. The assistant pushes back on rankings that do not survive the scoring rationale. The operator pushes back on rankings that misread the user or the work.

## Dogfooding-evidence record discipline

Throughout the conversation, the assistant notes how the Prioritiser role's authored content informed the work. At conversation close, the assistant drafts the dogfooding-evidence record as substantive prose against the procurement-grade evidence question:

Did Padhanam's own methodology authoring (the McKinsey 7-Step Prioritiser role at S26b per D85, structured per D81's multi-role aggregate v2 shape) produce content that worked for the operator at a real Phase 2 prioritisation problem? Or did the conversation operate on general McKinsey framework knowledge irrespective of what was authored on the control plane?

The third instance of the methodology-template-extensibility-without-breaking pattern is the recurrence test. ProblemFramer at Step 1 and Disaggregator at Step 2 both had narrower authored discipline scope than work scope and accommodated extensions without breaking. The Prioritiser is the third role; the third instance either continues the pattern (procurement-grade evidence strengthens) or breaks the pattern (different signal worth recording). The dogfooding-evidence record names this honestly.

The record names specifically: which template fields informed the session, where the application worked cleanly, where it required interpretation, what gaps surfaced between the template's scope and the actual prioritisation work. Honest framing wins.

## Conversation closing

At conversation close, the assistant produces three drafted text artefacts:

1. The prioritised list (top quartile flagged; rationale per sub-problem captured) — structurally similar to the Step 2 issue tree but with scores attached and ordering applied
2. The dogfooding-evidence record (substantive prose, four to five paragraphs)
3. Carry-forward to Step 4 (open questions for Planner)

Plus a brief paragraph noting Step 4 (Plan) as the next session in the arc, plus any open questions Step 3 surfaced for Step 4 specifically. Examples of likely Step-3-to-Step-4 carry-forward questions: workplan granularity (per-sub-problem versus per-priority-cluster); resource allocation across priority items; sequencing within priorities given dependencies; whether to plan across the full top quartile or sub-prioritise the quartile further.

The drafted artefacts get committed via a subsequent short Claude Code session. The Claude Code session's commit-session brief drafts at this Claude.ai conversation's close, taking the drafted artefacts as paste-ready content inline (per the placeholder-versus-content-payload methodology-miss correction from Step 1's commit prompt).
