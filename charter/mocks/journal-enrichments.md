# Journal enrichments — captured

Context: design-track capture from the daily-driver UI work. Feeds the journal section of the design-language spec. Two items are flagged for their own design pass because they touch the causal graph; the rest commit to the spec as written. Dispositions use the project's capture vocabulary.

## Governing principle

The enrichments that matter are the ones only Padhanam can do, because the journal sits on the causal graph; everything else is table stakes worth having but not the reason anyone stays. Every enrichment is opt-in and off by default. The fastest way to kill a journal is to turn it into a form, and the journal is the surface most likely to curdle into daily guilt, which is the same restraint test the charter applies to the morning BEHIND row: does the feature keep earning its place, or does it become a chore the user learns to dismiss.

## Commit to the journal spec now

**Work / personal separation.** An optional split of the entry into two streams. Opt-in, off by default. The product already tiers work and personal, so the split is nearly free, but the default stays one space because the bet is that causation crosses the boundary and a forced split re-teaches siloed thinking. Kano: indifferent for most, performance for the subset who want it, hence optional.

**Gratitude prompt and soft nudge.** A gratitude prompt the user can take or skip, with an occasional, gentle nudge rather than a daily one. A mandatory daily gratitude field breeds performative entries; a nudge that fires every day becomes noise. Kano: delighter when light, reverse if forced.

**Adaptive prompts.** The seed prompt reads the day instead of staying fixed, turning reflection toward what mattered ("you cleared a blocker that sat two weeks, what unblocked it"). Dismissible. This uses the active-not-passive knowledge the product already holds. Kano: performance.

**Weekly and monthly review, seeded by what moved.** Padhanam assembles the period's wins, slips, and decisions automatically; the user reflects on the assembled picture. The research is blunt that the insight comes from the reviews, not the daily entries, so this is the single highest-value enrichment and pairs directly with the dashboard. Kano: delighter crossing into performance.

## Needs its own design pass (touches the causal graph)

**Decision log linked to the CDD.** A stream for decisions made, the reasoning, and the lever or outcome the decision touched, revisitable later to see whether it held. The most on-brand enrichment, mirroring the product's decision-intelligence core, but it reads and writes against the causal graph, so it needs a design pass before build. Kano: delighter, and the spine that lifts the journal above mood logging.

**Mood or energy correlation.** A one-tap mood or energy mark, correlated against what the day actually held, so over weeks the journal shows patterns (energy dips on heavy-meeting days). Distinct from a standalone mood log because the correlation is the point; needs the graph join designed. Kano: delighter, the thing no flat journal has.

## Queued — table-stakes warmth

**On this day.** Resurface a past entry from a month or a year ago. Cheap, and it is the feature people cite when they say they love a journal.

**Low-friction capture.** A quick jot or voice note from anywhere that lands in today's entry. The habit lives or dies on friction; this also reuses the capture-then-triage pattern already dogfooded in the operating model.

**Light themes over time.** Soft auto-tags so recurring threads (a project, a person, a stress) surface across months without a Notion-style database setup.

## Guardrails (explicit no)

**No hard streaks or consistency scores.** They look motivating and reliably become guilt, the exact failure the charter names. If a consistency signal is wanted, keep it warm and shameless ("four of the last seven days"), never a breakable chain.

**No AI-drafted entries.** The system seeds context and offers prompts; the user writes the reflection. Drafting the entry defeats the cognitive purpose and fosters dependence. This is a hard line.

## Parked unknown — conversation cell (not the journal)

**Cross-task reference from a task panel.** Once chat lives inside one task's panel, the other tasks sit behind it; referencing or jumping to them without losing place is unsolved. Likely direction: an at-mention inside the cell resolving to a link chip with peek/jump, a back-stack so the panel remembers where you came from, and the routing input as the escape hatch. Tackled when the conversation cell is built; task-level chat is the accepted approach until then.

## How this lands

Work/personal split, gratitude, adaptive prompts, and the weekly review enter the journal section of the design-language spec as written. The decision log and mood correlation get a short design pass first because they touch the causal graph. The cross-task reference question rides with the conversation cell, not the journal.
