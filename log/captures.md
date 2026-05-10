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
