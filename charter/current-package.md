# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## Between packages

P3 closed at S12. P3-close-adjacent reframe-and-rename work landed at S13 (the project is now padhanam, a public case-study demonstration of senior-product-leader-directed AI-assisted development under enterprise-realistic constraints; see D38 for the reframe and the package-namespace rename, and D39 for the case-study framing). Archive at [docs/archive/packages/p3.md](../docs/archive/packages/p3.md).

A P3→P4 boundary strategic session landed D41 through D48 (cost capture as a Phase 1 commitment, decision-discipline frameworks Kano and RICE, living-document discipline for PRDs and epic notes and PRFAQ, the living roadmap, role-function audit categories, two-surface mode-declaration discipline, and the mid-session capture surface). The new artefacts ([roadmap.md](roadmap.md), [phase-1-prd.md](phase-1-prd.md), [prfaq.md](prfaq.md), [log/captures.md](../log/captures.md)) are the canonical living surfaces from P4 forward; PRFAQ and Phase 1 PRD operator-voice rewrite is a follow-on strategic session.

P4 framing is the next strategic activity. The pattern matches the post-P2 between-packages state: this block is a placeholder until P4 opens with its session breakdown.

Carryover items from P3 close to P4 open:

- Production-shaped tenant onboarding workflow (full D13 implementation) deferred until production deployment context arrives. Adding a third tenant in P3 still requires editing Compose; recovery path lands when infrastructure-as-code is real.
- Cross-replica cache invalidation for the routing layer remains deferred (D36); single-replica dev makes this a non-issue.
- Hash chain caching as a performance optimisation deferred per D37 until measurement justifies.
- Load testing of the chain-concurrency posture pre-committed to whichever future session has multi-writer load (likely Phase 2).

Carryover items added at the P3→P4 boundary strategic session:

- Per-tenant cost-attribution column lands in P4 setup as an early Alembic migration on the tenant registry (D41). This is a retrofit relative to the preference for landing it at P3 open and the cost is acknowledged in D41's reasoning.
- Pricing table at `padhanam/config/inference.py` and OTel cost attribute extension on the inference adapter land in P4 framing (D41).
- P4 epic note at `charter/packages/p4-epic.md` is the first instance of the package-epic-note convention from D43, written at P4 open.
- PRFAQ operator-voice rewrite is a follow-on strategic session, sequenced before P4 opens or alongside P4 framing at operator discretion.
- Phase 1 PRD operator-review of the problem-statement and target-user sections is a follow-on strategic session on the same cadence.
- The methodology document at `charter/methodology.md` committed by D39 has not yet been authored. Surfacing as a carryover so that the gap is visible at the next strategic conversation; authorship is operator-led in strategic mode per D47, not in build-mode sessions.
