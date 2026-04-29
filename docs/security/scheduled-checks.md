# Scheduled supply-chain checks

Per D25, high-velocity dependencies are checked on a recurring schedule
between sessions. Each check opens a digest-bump PR with the new digest,
the upstream changelog excerpt for the version delta, breaking-change
flags, and a security-only-vs-feature classification. The operator
reviews and decides; **no auto-merge**.

## Active schedules

| Component | Cadence | Established | First run | Notes |
|-----------|---------|-------------|-----------|-------|
| Langfuse (web + worker images) | Monthly | 2026-04-29 (S5 close) | 2026-05-29 | First instance of the scheduled-monitoring pattern. Both `langfuse/langfuse` and `langfuse/langfuse-worker` are bumped together (versions stay in lockstep upstream). |

## Operator workflow

When a scheduled check fires:

1. Review the changelog excerpt the agent posts on the PR.
2. Decide: take the bump, defer, or pin further.
3. Run `make scan` against the new digest before merging.
4. Update `charter/decisions.md` only if the bump introduces a
   behavioural change worth recording (otherwise the digest update is
   chore-shaped).

## Out of scope until production CI exists

Remote CI cron jobs that open PRs automatically. The local pattern is
operator-driven for Phase 1: the operator runs `make scan` on the
current digests, and the schedule above documents *when* that should
happen, not *who* runs it. Migration to remote CI is a Phase 2
infrastructure task.
