# Claude Code Instructions

Operating manual for Claude Code working in this repo. Reading discipline matters as much as the rules themselves.

## Read at session start, in this order

1. [charter/principles.md](charter/principles.md) — engineering principles, every session
2. [charter/current-package.md](charter/current-package.md) — active package scope
3. [charter/packages/](charter/packages/) — package-level epic note for the active package per D43, when present
4. Latest entries in [log/sessions.md](log/sessions.md) — recent context (scan the tail; do not read the whole file)
5. [log/captures.md](log/captures.md) — outstanding captures (scan for items relevant to the current session)

Sessions follow Design → Build → Test → Close. Do not skip steps.

## Mode declaration at conversation start (per D47)

Every conversation opens with a one-line mode statement: "strategic session, deliverable is a charter edit," or "build session for SN, executing the prompt below." The line is binding. Strategic conversations produce charter edits, session prompts, or roadmap version updates. Build sessions produce code commits and session-log entries.

The two-surface model is conceptual, not UI-bound. Mode separation is maintained by the declaration line, by distinct deliverables, and by distinct commit conventions (`docs(charter): ...` or `docs(pN/<boundary-name>): ...` for strategic; `feat(pN/sN): ...` and `docs(pN/sN): ...` for build). The charter files are the bridge between modes regardless of which UI is active.

Browser interactive verification is the success criterion for any acceptance criterion that involves a UI surface, not CLI smoke. The lesson lands from S4 (Langfuse trace UI display correctness) and reinforces every session that touches a user-visible surface. CLI smoke alone passes while the user experience is broken; both must be verified.

## Token discipline

- Files over 200 lines: read in ranges, not whole.
- Working files (`charter/current-package.md`, session log entries) stay tight. Old content moves to [docs/archive/](docs/archive/) at audit time. Nothing is ever deleted.
- Do not enumerate the repo. Read only what the session requires.

Configuration values that appear in multiple files (package name, compose project name, default model, port numbers) are discovered from a single source rather than hardcoded. The rename session caught the AST enforcement test having hardcoded the package name; the lesson generalises. When writing tests, contracts, or scripts that reference such values, read from `padhanam/config/`, `pyproject.toml`, or the appropriate configuration surface.

## Decision discipline (per D42)

- Strategic placement uses the bet → phase → package → session tree at [charter/roadmap.md](charter/roadmap.md). Used at framing.
- Option assessment uses Kano. D-entries that select between alternatives carry a Kano category field at the bottom (must-have, performance, delighter, indifferent, reverse).
- Sequencing uses RICE. Recorded explicitly on packages and on implementation backlog items where sequencing involves real choice.
- Each framework operates at its own moment of the work. Conflating them produces ceremony without reasoning value.

## Commits

Conventional commits, scoped to package and session: `feat(p1/s1): ...`, `docs(p3/s2): ...`, `fix(p4/s1): ...`. Strategic-mode work that doesn't fit a session number uses `docs(charter): ...` or `docs(pN/<boundary-name>): ...` per D47. The template at [.gitmessage](.gitmessage) is wired up via `commit.template`.

## Charter touch-points that must travel with the code

- **Schema changes** update [charter/schema.md](charter/schema.md) in the **same commit** as the migration.
- **New observability metrics** require a documented decision in [charter/decisions.md](charter/decisions.md) describing the action the metric will inform.
- **Architectural decisions** made during a session append a new entry to [charter/decisions.md](charter/decisions.md) before the session closes. Entries that select between alternatives carry a Kano category field per D42.
- **Course changes** that affect package sequence, scope, or dependency update [charter/roadmap.md](charter/roadmap.md) with a new version stamped with reasoning category (discovery, capacity, signal, hedge) per D44.

## Per-session role-function tag (per D46)

Each session-log entry header carries a one-line `roles:` tag naming which of the five role-functions were exercised this session: analyst, PM, architect, engineer, technical writer. Distribution over time is signal at phase audits.

## Reflection density by conversation type (per D47)

Strategic conversations produce shorter session-log entries focused on what was decided. Build sessions produce longer entries with substantive reflection on what was learned. The mix of types over time is itself signal.

## Captures discipline (per D48)

Mid-session stray thoughts go to [log/captures.md](log/captures.md) rather than derailing the current session. Triage at session close (or at package close for less time-critical captures) classifies each entry per the taxonomy in `captures.md`.

## Methodology capture

The product-leader-and-implementer pattern is documented in [charter/methodology.md](charter/methodology.md) (pending operator authorship per D39; the gap is tracked as a carryover in `current-package.md`). When a session surfaces something about the pattern itself (a brief format that worked or didn't, a class of drift the product leader caught and corrected, a moment where the model and product leader diverged on approach, a discipline added or relaxed), surface it briefly in the session-log entry under a `methodology:` line. Keep it to one or two sentences. The operator promotes accumulated observations into [charter/methodology.md](charter/methodology.md) at audit boundaries from a strategic-mode conversation per D47; build-mode sessions do not write to that document directly.

## Where strategy and build meet

Strategy, audits, framework-driven option assessment, and charter authorship happen in strategic-mode conversations and produce charter artefacts. Build and test happen in build-mode sessions and produce code commits. The bridge is the charter files; decisions written in strategic mode are constraints in build mode. If a build request conflicts with a decision in [charter/decisions.md](charter/decisions.md), surface it before building.


## Enforcement layer naming

When a session establishes architectural enforcement (import-linter contracts, AST tests, integration tests asserting an invariant), name the enforcement layer explicitly in the session log entry: which contracts, which tests, what they prevent. Future sessions inherit the enforcement and need to know what is already guaranteed by tooling versus what still requires review.
