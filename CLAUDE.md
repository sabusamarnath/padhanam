# Claude Code Instructions

Operating manual for Claude Code working in this repo. Reading discipline matters as much as the rules themselves.

## Read at session start, in this order

1. [charter/principles.md](charter/principles.md) — engineering principles, every session
2. [charter/current-package.md](charter/current-package.md) — active package scope
3. Latest entries in [log/sessions.md](log/sessions.md) — recent context (scan the tail; do not read the whole file)

Sessions follow Design → Build → Test → Close. Do not skip steps.

## Token discipline

- Files over 200 lines: read in ranges, not whole.
- Working files (`charter/current-package.md`, session log entries) stay tight. Old content moves to [docs/archive/](docs/archive/) at audit time. Nothing is ever deleted.
- Do not enumerate the repo. Read only what the session requires.

## Commits

Conventional commits, scoped to package and session: `feat(p1/s1): ...`, `docs(p3/s2): ...`, `fix(p4/s1): ...`. The template at [.gitmessage](.gitmessage) is wired up via `commit.template`.

## Charter touch-points that must travel with the code

- **Schema changes** update [charter/schema.md](charter/schema.md) in the **same commit** as the migration.
- **New observability metrics** require a documented decision in [charter/decisions.md](charter/decisions.md) describing the action the metric will inform.
- **Architectural decisions** made during a session append a new entry to [charter/decisions.md](charter/decisions.md) before the session closes.

## Where strategy and build meet

Strategy, audits, and option-framing happen in Claude.ai. Build and test happen here. The bridge is local files — decisions written upstream are constraints downstream. If a request conflicts with a decision in [charter/decisions.md](charter/decisions.md), surface it before building.
