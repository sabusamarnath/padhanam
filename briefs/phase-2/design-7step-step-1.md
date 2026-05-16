Phase 2 design — McKinsey 7-Step — Step 1 (Define the problem)

Strategic-mode conversation applying Step 1 of the McKinsey 7-Step Framework to Padhanam's Phase 2 design problem. First session in a multi-session arc that produces the Phase 2 strategic shape. Posture 1.5: structural dogfooding of the McKinsey 7-Step methodology template authored at S26b without agent runtime dependency. The conversation reads the template, follows its ProblemFramer role discipline deliberately, and produces a problem statement that does not assume D93's methodology-as-product framing forecloses creative space.

What this conversation produces

Three drafted artefacts that a subsequent Claude Code commit session lands as files:

Problem statement (one paragraph plus one or two paragraphs of context). Articulated from the user's perspective; names affected users explicitly; names consequence of the problem persisting; testable (a future audit can verify whether the problem was solved); does not embed solution assumptions in problem language.
Dogfooding-evidence record (substantive prose, not a checklist). Names which fields of the McKinsey 7-Step methodology template informed the conversation; how the conversation applied the ProblemFramer role's discipline; whether the template's scope accommodated the work; what the dogfooding tells us about the bet's procurement-grade-methodology-embedding claim.
Initial disaggregation (optional). If sub-problems surface naturally during Step 1 conversation, capture them. This is Step 2 territory; may carry to Step 2's session if it does not surface here.

Context to read first via project_knowledge_search

Search for and read systematically:

The McKinsey 7-Step methodology template content. The template was authored on the control plane at S26b per D85; search project knowledge for the template's ProblemFramer role definition, constraints, and expected outputs. If the template content is not findable via project knowledge search, surface this finding explicitly and proceed with the documented McKinsey 7-Step framework content (the absence-from-read-surface is itself signal worth recording).
charter/bet.md — strategic intent the design serves
charter/principles.md — binding rules including User safety section
charter/architecture.md — what the substrate supports
charter/methodology.md — v3 build discipline; particularly the Foundation hypothesis-iteration framing
charter/product-methodology.md — what the platform encodes for users; the four professional functions framework
charter/p12-phase-2-inputs.md — Phase 2 candidates and architectural rework observations; useful as context but not as framing constraint
log/captures.md — particularly the mass-market-UX-as-Phase-2-commitment entry
charter/decisions.md — particularly D77 (consumer-direction placement), D78 (personal-use deployment), D85 (McKinsey 7-Step methodology authoring placement), D93 (Phase 2 direction methodology-as-product)

Pre-conversation operator decisions

Two decisions to confirm before substantive Step 1 work begins:

Decision 1: Charter-grade versus notes-grade placement of the 7-Step arc record.

(a) docs/notes/phase-2-design-7step.md notes-grade. Consultative; outputs feed Phase 2 packaging without binding subsequent work.
(b) charter/phase-2-design-7step.md charter-grade per D91's precedent. Binding specification; Step 3 prioritised bets land as Phase 2 LVT structure; document refreshes at phase audits per D45 cadence.

Recommend (b). The 7-Step arc outputs become Phase 2's strategic structure; the bets identified at Step 3 are binding for Phase 2 packaging. Operator decides.

Decision 2: Blank-sheet discipline scope.

Blank-sheet means the conversation questions framing-by-existing-charter-commitment. Specifically: D93's methodology-as-product framing, D77's consumer-direction placement, the captures-entry mass-market-UX commitment. The conversation may surface that one or more of these does not survive Step 1 scrutiny.

Two scopes available:

(a) Apply blank-sheet discipline within the bet's success criteria. The bet's core claims (procurement-grade architecture, methodology-as-product, learning sprint demonstration) hold; the specific Phase 2 framing (D93's three-wave sequencing, the mass-market-UX commitment) is open to re-derivation.
(b) Apply blank-sheet discipline including the bet. If the conversation surfaces that the bet's framing itself does not survive scrutiny, that lands as the Step 1 finding.

Recommend (a). The bet is the load-bearing claim that Phase 1 was substrating against; revisiting it at Step 1 reframes the entire conversation arc. The Phase 2-specific commitments (D93 framing, three-wave sequencing, mass-market UX) are the layer worth questioning. Operator decides.

Conversation discipline expected

The McKinsey 7-Step ProblemFramer role frames "define the problem" with specific discipline. The conversation applies this discipline deliberately, with the assistant surfacing the methodology's framing prompts and the operator articulating answers:

Who has the problem? Phase 2's users named specifically. Not "users" in the abstract but the actual people. The bet names senior product leaders; Phase 2's UX direction may broaden (consumer-grade UX implies broader audience) or narrow (specific roles within the four professional functions). The conversation names the audience explicitly.

What is the problem? From the user's perspective, not the builder's. Not "Padhanam lacks a UI" but the underlying frustration the UI would address. The problem is articulated in language a non-Padhanam reader would recognise as their problem.

What gets worse if the problem persists? Consequence of inaction. If Phase 2 does not ship, what does that mean for the bet's commercial test condition; for the operator's professional learning sprint; for the procurement-readiness claim; for the dogfooded methodology evidence. The consequence is testable.

How would success be measured? What evidence at Phase 2 close would let a procurement reader (or the operator at the Phase 2 audit) verify the problem was solved. Success criteria that connect to the bet's success criteria but are specific to Phase 2.

What is the problem NOT? Solution assumptions to surface and remove. If the problem statement reads as "users need a methodology-as-product UI," the conversation interrogates whether "methodology-as-product UI" is the problem or one solution to a more fundamental problem. Blank-sheet discipline applies.

The conversation iterates. Initial articulations get challenged; revisions surface; the problem statement converges through multiple cycles. The assistant pushes back on framing that smuggles solution assumptions into problem language. The operator pushes back on framing that misreads the user or the consequence.

Dogfooding-evidence record discipline

Throughout the conversation, the assistant notes how the McKinsey 7-Step methodology template's content informed the work. At conversation close, the assistant drafts the dogfooding-evidence record as substantive prose against the procurement-grade evidence question explicitly:

Did Padhanam's own methodology authoring (the McKinsey 7-Step template at S26b per D85, structured per D81's multi-role aggregate v2 shape) produce content that actually worked for the operator at a real Phase 2 design problem? Or did the conversation operate on general McKinsey framework knowledge irrespective of what was authored on the control plane?

The answer is the load-bearing evidence point. If the template's content informed the conversation usefully, the bet's methodology-embedding claim has structural-level evidence even before agent-runtime-level evidence accumulates. If it did not, the methodology authoring needs revision and that revision becomes a Phase 2 workitem.

The record names specifically: which template fields informed the session, where the application worked cleanly, where it required interpretation, what gaps surfaced between the template's scope and the actual work. Honest framing wins; performative dogfooding is signal the operator does not need.

Conversation closing

At conversation close, the assistant produces three drafted text artefacts:

The problem statement (with context paragraphs)
The dogfooding-evidence record (substantive prose)
Initial disaggregation if it surfaced

Plus a brief paragraph noting the next session in the arc (Step 2 disaggregation if it did not surface at Step 1; Step 3 prioritisation if Step 1 produced natural disaggregation) and any open questions Step 1 surfaced for subsequent steps.

The drafted artefacts get committed via a subsequent short Claude Code session. The Claude Code session's brief drafts after this conversation closes, taking the drafted artefacts as paste-ready content.
