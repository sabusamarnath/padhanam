# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## Between packages

P3 closed at S12. P3-close-adjacent reframe-and-rename work landed at S13 (the project is now padhanam, a personal learning sprint under enterprise-realistic constraints; see D38 for the reframe and the rename of the Python package namespace `vadakkan/` → `padhanam/`). Archive at [docs/archive/packages/p3.md](../docs/archive/packages/p3.md).

P4 framing is the next strategic activity in Claude.ai. The pattern matches the post-P2 between-packages state: this block is a placeholder until P4 opens with its session breakdown.

Carryover items from P3 close to P4 open:

- Production-shaped tenant onboarding workflow (full D13 implementation) deferred until production deployment context arrives. Adding a third tenant in P3 still requires editing Compose; recovery path lands when infrastructure-as-code is real.
- Cross-replica cache invalidation for the routing layer remains deferred (D36); single-replica dev makes this a non-issue.
- Hash chain caching as a performance optimisation deferred per D37 until measurement justifies.
- Load testing of the chain-concurrency posture pre-committed to whichever future session has multi-writer load (likely Phase 2).
