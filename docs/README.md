# Docs

Lean, append-only documentation for the Meridian build. Optimized for Claude Code to read selectively without burning tokens on irrelevant context.

## Structure

```
docs/
├── README.md                    you are here
├── session-prompt.md            paste at the start of every Claude Code session
├── brief.md                     per-session context (changes each session)
├── charter/
│   ├── bet.md                   strategic intent, rarely changes
│   ├── principles.md            engineering principles, read every session
│   ├── decisions.md             architectural decisions, append-only
│   ├── packages.md              Phase 1 work breakdown
│   ├── current-package.md       active package, archived at package close
│   └── schema.md                database schema, updated on schema change
├── log/
│   ├── sessions.md              session entries, append-only
│   ├── packages.md              package retrospectives, append-only
│   └── audits.md                phase audits, append-only
└── archive/
    └── README.md                what gets archived and how
```

## How sessions use these files

The read order and session structure are defined in `session-prompt.md`. That file is the authority. This README only describes what each file holds.

## How audits use these files

Audits read everything in `charter/` and `log/`. They check decisions against current code, schema against the documented schema, session reflections for drift signals, and operating model for adjustments needed.
