# Product Methodology

What the Padhanam platform encodes for its users.

This document is distinct from `charter/methodology.md`. The methodology document covers how Padhanam itself is built (start simple, refactor often; framing-prompt-as-recommendation; structural-promotion threshold). This document covers what the platform's agent layer encodes for the professional functions it demonstrates against.

## The core commitment

Methodology is embedded, not gated. Defaults encode the right thing for the chosen methodology; overrides at decision points are cheap and non-punitive. Methodology activates at decision points, not as workflow gates. Old enterprise SaaS treats the methodology as the product's wireframe and makes the user traverse it; this platform inverts that, treating user intent as primary and methodology as the smart default that the user can override without friction.

See `charter/principles.md` for the architectural commitment that backs this surface; see `charter/bet.md` for the strategic positioning.

## Functional domains

Four professional functions the platform demonstrates against. Methodology selection per domain is a selection space at this stage; per-domain methodology decisions land as each domain enters package scope.

### Product Management

Stage-specific methodologies (selected per product lifecycle phase):

- PoC: Lean Startup, Customer Development, Jobs to be Done, Google Ventures Design Sprint.
- Prototyping: Design Thinking, Double Diamond, Lean UX, Design Sprint.
- Enterprise-grade products: Stage-Gate, Pragmatic Institute framework, SAFe Lean Portfolio Management.

Cross-cutting methodologies (selected independently, applied across stages):

- Strategy: Lean Value Tree, North Star Framework, OKRs, Wardley Mapping.
- Prioritisation and validation: Kano, RICE, MoSCoW, ICE, Opportunity Solution Tree.

Decision Intelligence and the Causal Decision Diagram (CDD) join the stack at D156 as the
causal-reasoning methodology: mapping actions and circumstances through intermediate factors to
desired outcomes, so a change in one factor's status surfaces its ripple to the outcomes that
depend on it. The CDD is the structural core of the Phase 2 daily driver and the form the
observability and optimization differentiator takes at the human level.

### Marketing

1. Marketing Audit: Kotler's Marketing Audit Framework, SOSTAC, Forrester Marketing Maturity Model.
2. Content Generation: StoryBrand, Content Marketing Institute pillar-and-cluster, AIDA, PAS, BAB, buyer journey mapping (TOFU, MOFU, BOFU), Nielsen Norman tone-of-voice dimensions.
3. Product Launch and Go-to-Market: April Dunford positioning, Pragmatic Marketing launch model, Product Marketing Alliance launch tiering.
4. Customer Advocacy and Reference Programs: Forrester reference program model, advocate tiering, case study narrative structures.
5. Account-Based Marketing: ITSMA tiered model (1:1, 1:few, 1:many), Forrester ABM framework, Demandbase playbooks.

### Learning and Development

1. Learning Design: ADDIE, SAM, Action Mapping, 70-20-10.
2. Knowledge Management: SECI, Knowledge-Centered Service, Communities of Practice.
3. Content Creation and Curation: Bloom's Taxonomy, Mayer's principles of multimedia learning, microlearning frameworks, Search-Sense-Share curation.
4. Learning Analytics and Measurement: Kirkpatrick's Four Levels, Phillips ROI Methodology, Brinkerhoff Success Case Method.
5. Audit: ISO 30414, Brandon Hall maturity framework, ATD Capability Model.

### Project and Programme Management

Four delivery methodology options that cascade through every sub-workflow:

- PRINCE2.
- Waterfall.
- Agile (Scrum, Kanban).
- SAFe.

Sub-workflows that inherit the chosen methodology: planning and scoping, execution and tracking, governance and reporting, risk and change management, stakeholder communication.

## Methodology shape diversity

The methodologies in the lists above are not all the same architectural shape, and the diversity is intentional. Stage-Gate is a process methodology with gates and phase reviews; ADDIE is a sequence; Kano is a classification model; AIDA is a copywriting structure; SECI is a knowledge-creation cycle; April Dunford positioning is a worksheet shape; ABM tiering is a customer-segmentation rubric. These embed differently in the product. An agent that defaults to Lean Value Tree shapes its planning. An agent that defaults to AIDA shapes its outputs. The implementation pattern per methodology shape is part of what the demonstration surfaces and is settled per domain as the domain enters package scope.

## Build sequence

1. **Product Management** first. Operator's deepest expertise; senior product leaders are the primary audience; demonstration value is highest.
2. **Learning and Development and Marketing** next. Operator has direct user access in both domains for validation, which is the surface that exposes whether methodology embedding works in practice.
3. **Project and Programme Management** last. PgM remains a live burden for enterprise customers, and an AI workflow that surfaces senior-stakeholder visibility as new issues and risks emerge is a category-shifting capability. PgM is also the hardest test of the methodology-embedded-not-gated commitment, because procedural methodologies resist embedding without becoming gates. The order places it last so prior domains accumulate the embedding-pattern discipline before the hardest test runs.

## Selection discipline

Methodology selection within each domain stays as a selection space at this stage. Pre-committing to specific methodologies before consumer evidence drives the choice is the same shape of overreach the architecture rejected for the within-tenant segmentation primitive. Per-domain methodology decisions land as each domain enters package scope, with the consumer-evidence-needed posture per the methodology document. The selection space documented above is the candidate set; the active set is whatever the package-scoped framing settles on.

## The goal taxonomy

Any goal the daily driver holds is placed on three axes before it is modelled: engine, target, and control. The placement decides how progress is read and which remedy applies when the goal falls behind. The shapes, boundaries, variant, higher layer, and mechanics are as recorded in D163. The taxonomy exists to do one thing a tracker cannot: tell the system where to switch its machinery off (the atomic one-off), where it cannot yet engage (the exploratory phase), and which of three different remedies a falling-behind goal actually needs.

**The three axes.** The *engine* is cadence (repetition) or sequence (a dependency chain). The *target* either maintains a level (homeostatic), advances a level (progressive, with a ratcheting target), or reaches a point once (terminal). *Control* says whether the actor's own levers determine the outcome, or the actor only influences it while another party determines it.

**The three core shapes** follow from engine crossed with target, and each carries its own reading of "behind" and its own remedy. Homeostatic cadence repeats to hold a level — behind is drift, the remedy is to re-establish the rhythm. Progressive cadence repeats to raise a level — behind is not advancing, the remedy is to adjust the target. Sequence releases tasks toward a terminal — behind is blocked, the remedy is to unblock or drop. Real goals are hybrids; the placement names the dominant shape so the right remedy fires.

**The two boundaries** bound where the machinery applies. Below the model, the atomic one-off is too small for an outcome — it is a tick with no machinery; a multi-step errand stays a tick unless a seam between its steps can stall, and is promoted to a tracked chain on the stall, not on the decomposition. Before the model, the exploratory phase has no defined outcome yet — the work is to converge on the outcome, not advance toward it, and the causal graph begins only once the outcome is named.

**The variant and the higher layer.** Avoidance is a variant of homeostatic, maintained by not acting and measured in streaks and lapses, where behind is a discrete lapse rather than drift. Balance is the one higher layer above all goals: the allocation across competing outcomes — a property of the whole set and the morning decision, not a goal-shape.

**The three mechanics.** The adjustable target makes progressive cadence a live expected-versus-observed loop — the target is the expectation, progress is the observed, the gap moves the target; it is qualitative, not numeric (quantitative inference stays deferred per D156). Remedies must read the shape, because the wrong remedy deletes the wrong things — the S61 drop-if-quiet nudge is a sequence remedy and must not fire on a cadence goal. The subject, self or other, usually decides the control axis.

**The model is a graph, not a list.** A goal can be a lever toward a higher goal, so the higher layer has two faces: the vertical (goals laddering to life aims, held natively by the graph) and the horizontal (balance across the top nodes). S62 instances only the progressive-cadence / self-control / self-subject shape, through German; every other value is schema-present and uninstanced, awaiting the session that instances a goal of that shape.

## The plan-side work-unit model

Padhanam assembles a unit of work from up to four facets scattered across the user's tools and its own graph: the message that requested it, the task that tracks it, the calendar block that times it, and the native goal it serves. It correlates them into one unit, suggests the facets that are missing, and assesses the unit against the goal. The block also serves as the time-expectation that the execution loop later reads observed completion against, linking the plan facet to the expected-versus-observed machinery already built for goals.

This section is the working-model framing; D166 is canonical. Do not derive a divergent version here.

**The four facets.** Origin (a message that requested the work), tracking (a task that tracks it), time (a calendar block that times it), purpose (a native goal it serves). The first three are ingested read-only from the user's own tools per the assess-not-replace principle and the D148/D155 external-cache model; the fourth is the layer no external source holds, supplied by Padhanam.

**Correlation, then conditional suggestion.** The sources share no identifier, so a unit is assembled by proposing high-precision title-and-time links that confirm rather than assume — a wrong link that fuses two unrelated things is worse than no link, and the link is a Padhanam-native edge, never written back. Where a facet is missing, Padhanam assesses whether it should exist and suggests it recommendation-shaped: a substantial task with no time earns a block suggestion (an atomic one-off does not — that is the reverse-Kano nag); an event with no task earns a suggestion for the satellite work it implies, the preparation before and the actions after, not a duplicate of the event itself.

**The differentiating read is goal-aligned, not time-blocking.** The two assessments only the goal facet makes — orphan work (a correlated unit pointing at no named goal) and the neglected goal (an outcome the user says matters that nothing in the plan advances) — are what separate Padhanam from the time-blockers the market already sells. Purpose is broader than goal-advancement: maintenance work and owed work serve a real purpose, so the orphan read must not flag homeostatic or owed work as purposeless.

**The plan is a constrained graph of units, not a bag of complete units.** Beyond the single unit the model carries dependency (the sequence engine at plan altitude, crossing goal boundaries), the deadline (a constraint distinct from the block — the dated-terminal shape), capacity (the balance layer made concrete — the whole-plan feasibility check, assessed through the goal so that the work which gives when over capacity is the orphan and low-goal work), recurrence (the cadence engine at plan altitude), and waiting-on-others (the influence axis at plan altitude — units another party owns, nudged but not scheduled). Effort, fixed-versus-movable, and priority feed capacity; they are not separate facets. Which of these dimensions builds first is gated on the Phase 2-A dogfooding week — the model is recorded now, the build follows the week.
