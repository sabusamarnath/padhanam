# Meridian

Meridian is an agentic workflow SaaS platform whose core differentiator is the observability and optimization layer that production agentic systems need but most teams do not build. A NotebookLM-plus-Gems agent surface sits on top.

## How to read the charter

The charter under [charter/](charter/) holds design intent. Read in this order:

1. [bet.md](charter/bet.md) — strategic intent and what success looks like
2. [principles.md](charter/principles.md) — engineering rules, read every session
3. [decisions.md](charter/decisions.md) — append-only architectural decisions log
4. [packages.md](charter/packages.md) — Phase 1 work breakdown, then [current-package.md](charter/current-package.md) for active scope

History lives separately under [log/](log/) (sessions, packages, audits) and old material is moved to [docs/archive/](docs/archive/) at audit boundaries — never deleted.

## Claude.ai vs Claude Code

Strategic work — bets, audits, package planning, decisions framed against Kano — happens in Claude.ai, where breadth of context and reasoning matter more than tool access. Build and test work — implementation, schema migrations, tests, commits — happens in Claude Code against this repo. The two surfaces meet through the local files: decisions written in Claude.ai land in [decisions.md](charter/decisions.md), and Claude Code reads them as constraints. Audit findings flow back the same way.

## Where new contributors look first

Start with [charter/bet.md](charter/bet.md), then [charter/principles.md](charter/principles.md). [CLAUDE.md](CLAUDE.md) describes how Claude Code is expected to operate inside the repo.
