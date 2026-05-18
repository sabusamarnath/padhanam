# Phase 2 design — McKinsey 7-Step — Step 4 (Plan)

Strategic-mode conversation applying Step 4 of the McKinsey 7-Step Framework to the prioritised list produced at Step 3. Fourth session in the multi-session arc that produces the Phase 2 strategic shape. Posture 1.5: structural dogfooding of the McKinsey 7-Step methodology template authored at S26b without agent runtime dependency. The conversation reads the Planner role's specification and follows its workplan discipline deliberately.

This brief is authored pre-conversation, continuing the briefs/ discipline restoration test validated at Step 3.

## Three methodology streams operating in parallel

The Step 4 conversation touches three distinct methodology streams that share the word "methodology" but are structurally separate. Naming them explicitly at the brief opening prevents conflation.

**Build methodology** at `charter/methodology.md`. How Padhanam itself is built. The 7-Step arc is a build-methodology instance. Audience: senior product leaders adopting the discipline per `bet.md` line 67.

**Product methodology** at `charter/product-methodology.md`. What the platform encodes for users at the agent layer. The thirty sub-problems and top quartile from Step 3 sit in this stream. Audience: busy professionals running a Private Assistant per Step 1.

**Methodology aggregate as control-plane construct** at `contexts/methodology/` per D86. The technical substrate the build-methodology uses to design product-methodology capabilities. The McKinsey 7-Step methodology at S26b lives here.

Step 4's workplan touches all three. Workplan items are build-methodology work; their deliverables are product-methodology capabilities; the control-plane aggregate is the substrate. The conversation holds all three streams distinct and surfaces interactions explicitly.

## What this conversation produces

Three drafted artefacts that a subsequent Claude Code commit session lands as a Step 4 section at `charter/phase-2-design-7step.md`:

1. **The workplan for the prioritised sub-problems.** For each priority sub-problem (top quartile per Step 3, either strict 5-item cut or inclusive 11-item cut per Decision 1 below): hypothesis, analyses to be run, data needed, owner, deadline, deliverable. The workplan feeds Step 5 (Analyse) for execution-equivalent in Phase 2 framing.

2. **Dogfooding-evidence record for Step 4 (substantive prose).** Fourth instance of the structural-dogfooding pattern, fourth instance of the methodology-template-extensibility-without-breaking test. The pattern is at three-instance evidence after Step 3; this Step's outcome either continues the pattern (procurement-grade evidence strengthens further) or breaks the pattern (different signal worth recording).

3. **Carry-forward to Step 5 (Analyse).** Open questions Step 4 surfaces for the analysis step's evidence-gathering and finding-production work.

## Context to read first via project_knowledge_search

1. `charter/phase-2-design-7step.md`. Steps 1, 2, and 3 sections in full.
2. `briefs/p8/mckinsey-7-step.md`. The Planner role's authored specification.
3. `charter/bet.md`. Strategic intent; success criteria.
4. `charter/principles.md`. User safety section; intelligence-layer commitment.
5. `charter/methodology.md` (build methodology).
6. `charter/product-methodology.md` (product methodology).
7. `charter/architecture.md`.
8. `charter/p12-phase-2-inputs.md`.
9. `charter/decisions.md`. Specifically D44, D80, D82, D85, D86, D93.
10. `log/captures.md`.

## Pre-conversation operator decisions

Five decisions to confirm before substantive Step 4 work begins.

### Decision 1: Strict versus inclusive top quartile cut for workplan surface

(a) Strict cut, 5 items: 1.3, 1.1, 2.1, 3.1, 5.1.
(b) Inclusive cut, 11 items: adds 1.5, 3.2, 4.1, 4.2, 5.4, 6.3.

Recommend (b). Operator decides.

### Decision 2: Workplan granularity

(a) Per-sub-problem.
(b) Per-priority-cluster.
(c) Hybrid.

Recommend (a). Operator decides.

### Decision 3: Dependency-versus-priority sequencing approach

(a) Strict dependency-first ordering.
(b) Score-first within dependency constraints.

Recommend (b). Operator decides.

### Decision 4: Lifecycle-stage prioritisation strategy

(a) Find-rhythm-plus-settle-in stages across all priority items first.
(b) Full-lifecycle support for fewer items first.

Recommend (a). Operator decides.

### Decision 5: Owner framing for workplan items

(a) All items owned by operator.
(b) Owner by role-function distribution.

Recommend (b). Operator decides.

## Conversation discipline expected

The McKinsey 7-Step Planner role frames "produce workplan" with specific discipline. The conversation applies this deliberately, with the assistant surfacing the methodology's planning prompts and the operator articulating answers per priority sub-problem.

**Hypothesis.** What does the workplan item produce evidence for or against?

**Analyses to be run.** What work does the item require? At Step 4 altitude, "analyses" maps to architectural work, build work, and validation work.

**Data needed.** What inputs does the work require?

**Owner.** The role-function the operator wears for the item per Decision 5.

**Deadline.** When the item completes. Step 4 produces relative ordering rather than absolute calendar dates.

**Deliverable.** The artefact the item produces.

The conversation iterates per sub-problem. Initial workplan entries get challenged; revisions surface; the workplan converges through multiple cycles.

The conversation holds the three methodology streams distinct throughout, surfacing whenever a substantive build-methodology versus product-methodology distinction arises.

## Reflection prompts at session close

The conversation produces operator-recorded reflections that feed the eventual session log entry. The discipline matches Steps 1, 2, 3 reflection prompts.

1. **Methodology-template fidelity check.** Did the McKinsey 7-Step Planner role's discipline hold for the eleven priority sub-problems? Where did the template's discipline match the work? Where did it fall short?

2. **Methodology-template-extensibility-without-breaking test.** Did the template handle the workplan construction without forcing capability changes? This is the fourth instance of the structural-dogfooding test.

3. **Posture 1.5 sustainability check.** Did Posture 1.5 (structural dogfooding without agent runtime) deliver substantive value at Step 4? Or did the absence of agent runtime constrain the workplan in ways worth noting?

4. **Briefs/ discipline restoration test follow-through.** Step 3 restored the briefs/ discipline by authoring the brief before the Claude.ai conversation opened. Step 4 brief is authored before substantive Step 4 work begins. Does the pattern hold? Should it become a methodology line?
