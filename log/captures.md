# Captures

Mid-session catch surface per D48. Append-only. Stray thoughts during sessions go here so they neither derail the current session nor get lost.

Triage at session close (or at package close for less time-critical captures): each entry classified into one of five impact types, then either acted on, deferred, or archived.

Triage taxonomy:

- **quick task** — small enough to handle this session.
- **inject** — insert into the current package's session sequence.
- **defer** — forward to the next package or to `charter/deferred-decisions.md`.
- **replan** — large enough to warrant rethinking scope; trigger course-change in `charter/roadmap.md`.
- **note** — record only; no action implied.

Format per entry:

```
- YYYY-MM-DD [session-id] capture text
  - triaged: <classification> on YYYY-MM-DD
  - resolution: <what was done, or where it was forwarded>
```

---

[Captures begin below this line.]

## 2026-05-07 — Enterprise multi-agent QA system case study

Source: enterprise case study presented at the 2025 LangChain interrupt conference. Approach diagram and full transcript captured by the operator.

Architectural shape observed: domain-specific QA system with hierarchical multi-agent topology, intent-based routing to specialised sub-agents, runtime personalization conditioned on user role, reflection/judge gating before answer ships, memory layer for cross-conversation continuity, and human-in-the-loop escalation.

Observations and where each lands:

- **Hierarchical multi-agent topology with intent-routed subgraphs.** Design-session candidate; queued at P8 framing or as pre-P8 strategic block.
- **Personalization as a runtime concern** (same data renders differently based on user role). Landed as deferred-decisions entry this commit.
- **Build pattern: start simple, refactor often.** Landed as methodology discipline this commit.
- **Data retrieval as a multi-path architectural concern**, with each path having distinct evaluation needs and architectural posture. Design-session candidate; queued after P6 close, scope possibly large enough to earn package status on the roadmap.
  - triaged: design-session candidate on 2026-05-07
  - resolution: data-retrieval design session held 2026-05-07 between P6 close and P7 framing; output landed as D66 (hybrid composition architecture) and D67 (filter expression architecture); no package elevation needed because implementation lands in P7 (agent config schema) and P8 (runtime orchestrator and filter translator); retrieval-evaluation surface deferred to its own strategic-mode session ahead of P11 on Kano-versus-RICE asymmetry grounds.
- **Memory as a first-class agent surface.** Deferred-decision candidate; activates when an agent runtime use case demands cross-conversation context the audit and trace substrates cannot synthesise cleanly.
- **Runtime reflection as an orchestration node.** Deferred-decision candidate; activates when an agent runtime use case requires answer-quality gating before user surfacing.
- **Evaluation-driven development with sub-agent independent evaluation.** Corroborates Padhanam's eval-before-agent sequencing (P5 closed before P8 ships); no new commitment.

Bet corroboration: an enterprise of the kind Padhanam's bet names as the procurement test condition shipping this shape publicly is signal that the procurement-grade orchestration posture Padhanam architects toward is what enterprise teams actually deploy in 2025-2026. Worth citing at the Phase 1 close audit as enterprise reference architecture. Padhanam's own architecture may end up looking different; the corroboration value is in the procurement-grade posture, not in the specific implementation choices.

## 2026-05-09 — P7 mid-package strategic block — Architectural-mapping exercise for customer customisation

Source: P7 mid-package strategic block on consumer-direction placement.

Architectural exercise surfaced for any future customer customisation conversation. Classify each customisation requirement:

- **Configuration** (changes a tenant registry value or methodology template content) → no code change anywhere
- **Tool** (calls an external service to do something Padhanam doesn't natively do) → tool service lives outside Padhanam in its own codebase, configuration points to it
- **Extension** (logic running inside Padhanam at one of the named interfaces per D14) → bounded extension, sandboxed, per-tenant
- **Platform change** (none of the above fit) → upstream contribution to public Padhanam, no forking

Most things should fit in #1 or #2. Few in #3. Almost nothing should fit in #4 if the platform is well-designed; if many things fit in #4, the platform's customisation surface has gaps requiring architectural attention.

  - triaged: methodology-pattern candidate on 2026-05-09
  - resolution: noted at the strategic block's reflection section as a reusable architectural exercise; not promoted to methodology document at this commit because single-instance observation. Recurrence test continues at the next strategic block touching customer customisation; promotion threshold is two further instances per the existing methodology-promotion convention.

## 2026-05-09 — P7 mid-package strategic block — User-driven course-correction sixth instance

Source: P7 mid-package strategic block on consumer-direction placement.

Sixth named instance of the user-driven course-correction Patterns-observed entry from P6 close. Two course-corrections fired during this strategic block:

1. Operator caught the "Padhanam-lite as separate consumer build" framing accumulating across early conversation turns and pulled the framing back to "personal use as own instance of public Padhanam," reconnecting the conversation to D14's customer-deployment model. Without the catch, the strategic block would have produced a separate-build commitment despite the substrate-mismatch and attention-split concerns.

2. Operator caught the "private fork" recommendation surfaced mid-conversation and pulled it back to D14's no-fork architectural commitment by asking the broader client-customisation question. The catch surfaced the principle's overclaim ("forbidden" as performative rather than enforceable), triggered the principle revision now landing as D76, and clarified that the personal-use case is fully covered by the configuration + tools + bounded-extensions model without any need to fork.

The pattern continues to do load-bearing work at strategic-mode conversations and remains the most frequently-firing methodology pattern of the run. Recommend formal promotion to a methodology document entry at the next phase audit (P7 close), with the recurrence-test now satisfied at six instances across distinct strategic moments.

  - triaged: methodology-recurrence note on 2026-05-09
  - resolution: surfaced at the strategic block's reflection section as continuing pattern. Phase audit promotion candidate.

## 2026-05-10 — Consumer-direction architectural exploration (historical context for D77's alternatives-considered)

Source: OpenClaw analysis triggered post-S23/S24 brief drafting; multi-day strategic exploration spanning 2026-05-09 to 2026-05-10. The exploration considered a separate-consumer-build path before the strategic block landed D77; D77 superseded that path by placing the consumer-direction thread within D14's customer-deployment model rather than as a separate build (commit 1fb7712, P7 mid-package strategic block on consumer-direction placement). The architectural details below are recorded as historical context for the alternatives D77's alternatives-considered section names — specifically alternative (a) "Separate consumer build (Padhanam-lite as standalone product)" and alternative (c) "Bet expansion to second methodology demonstration." Not load-bearing for public Padhanam.

### Architectural shape (rejected separate-consumer-build path)

The separate-consumer-build path would have shaped as M3 hybrid (on-device plus hosted), three-tier with deterministic core dominant:

- **Architecture:** Tier 0 deterministic core (scheduler, integrations, templates, structured logging) handling the majority of routine interactions; Tier 1 local LLM (Apple Intelligence on capable iPhones, Gemini Nano on capable Androids) augmenting where available; Tier 2 hosted LLM for complex reasoning. Device-fragmentation constraint dissolves at Tier 0 in this shape; the product would have addressed the full mobile install base.
- **Mobile:** design constraint not initial scope. Architecture would have supported eventual mobile clients without retrofit.
- **Push:** Shape M2 server-side scheduler with FCM. Phone-triggered local LLM for routine proactive cases (no platform push infrastructure required); FCM-mediated server-push for hosted-LLM cases.
- **Privacy:** user-controlled tier. Closed mode (no LLM outside container; local LLM only), Sandboxed mode (hosted LLM with confidential-computing guarantees), Standard mode (hosted LLM with opt-in feedback). Default-candidate from the exploration: Sandboxed where device and provider supported confidential-computing guarantees; Standard otherwise.
- **LLM economics:** tiered approach was the resolution to the consumer adoption problem. Most interactions would invoke no LLM; Tier 2 would justify cost when invoked. Pricing candidate: freemium with premium tier for T2-heavy use cases.
- **Iteration loop:** methodology-as-iteration-unit with local replay against user history. Structured failure signals (decision-points tagged, inputs typed, outputs scored on dimensions, failures classified) would aggregate to platform without exposing user content. LLM-augmented operator analytics would propose specific changes with rationale and projected impact.
- **Distribution:** standalone app primary; MCP secondary surface for Claude users (a possible fourth distribution channel).
- **Design philosophy:** default-quiet, escalate-gracefully, do-not-over-prompt. "Staying human" as constraint on all agent behaviour, not a separate feature.

### Use case portfolio (rejected separate-consumer-build path)

Eleven real-life use cases stress-tested the rejected architecture across goal-driven, habit-driven, relational, reflective, and operational personas (reading a book a week, learning a new language, learning work-related, applying for a new role, managing family life, assisting friends, day-to-day job, meds, health, catching up with friends, staying human):

- T0-dominant (7 of 11): reading, meds, health, social catch-up, day-to-day job, family life, assisting friends.
- T2-weighted (2 of 11): language conversation practice, work-learning curriculum design.
- T2-heavy outlier (1 of 11): job applications. Would have implied a separate pricing tier or BYOK.
- Boundary case (1 of 11): staying human. Treated as design constraint rather than feature.

Pattern observed: agent-persona spectrum implies N agents per user sharing substrate, methodology-driven differentiation, cross-agent context as second-order value driver. The pattern is recorded as historical context only; it is not load-bearing for public Padhanam under D77.

### Strategic placement outcome

Placement landed as personal-use deployment of public Padhanam per D77 and D78. The four options framed during the strategic exploration (adjacent exploration, second methodology demonstration, pivot to consumer, MCP-layer agent platform) plus the separate-consumer-build path that this capture records were each weighed against the bet's load-bearing claims. D77 records the rationale for each rejection and the structurally honest answer (placement within D14's customer-deployment architecture).

### Methodology observations

- **Pre-build review with code-reading verification and deliberate-silence-detection** fired its third instance, this time against operator-uploaded OpenClaw documents containing fabricated specifics (founder status, infostealer targeting framing, valuation claims). The first two instances landed in build-session brief reviews (S23, S24); this third instance fires in a strategic-mode context against external source documents, suggesting the pattern's load-bearing scope extends beyond brief review to any source-document review where load-bearing technical or factual commitments are present. Recurrence test positive across two distinct contexts; recommend promotion to a methodology-document Patterns-observed entry at the next phase audit (P7 close).
- **Polished-AI-output-as-failure-mode**: progressive hallucination under pressure for "comprehensive" output without source-verification discipline. Distinct from the 2026-05-06 fabrication-class-drift Failure modes entry (which covered model-drafted vendor-voice content) because the new pattern is about polish-pressure-driven fabrication during multi-turn exploration rather than vendor-voice path-of-least-resistance fabrication during artefact drafting. New pattern; first observation; awaiting recurrence before phase-audit promotion.
- **Strategic-placement-deferred-to-allow-architectural-settlement**: sequencing pattern. Separate "what is true" from "what should we do" when reversibility differs sharply across options. Held during the strategic exploration that produced this capture: architectural outcomes settled across multiple turns before the placement question converged on D77 and D78 in the parallel placement-strategic block. New sequencing-pattern candidate; first observation; awaiting recurrence before phase-audit promotion.

  - triaged: historical-context note on 2026-05-10
  - resolution: architectural details preserved as historical context for D77's alternatives-considered section, specifically the separate-consumer-build alternative; not load-bearing for public Padhanam under D77's placement; no deferred-decisions entries land for the consumer-direction architectural questions because they would re-elevate architectural details that D77 superseded.
