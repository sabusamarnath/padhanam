# Phase 2 audit inputs

Accumulating substrate for the Phase 2 close audit. Audit observations surfacing during Phase 2 build sessions, strategic blocks, and arc work that warrant audit review rather than immediate fix. Mirrors the Phase 1 close audit input precedent at `charter/p12-audit-inputs.md`; entries accumulate chronologically with each entry naming the surfacing context plus the substantive observation plus the proposed audit treatment.

Reviewed at Phase 2 close audit. Entries dispositioned at audit time become either fix-now hygiene items, deferred-decisions entries with explicit activation triggers, or methodology lines folded into `charter/methodology.md`.

## D-entry cross-reference drift in charter prose usage

**Surfacing context.** Step 6 full commit landing (2026-05-20). Operator observation at session close: the new D-entries D114, D116, D118 cite "D26 (append-only audit chain)" and D114, D118 cite "D31 (revisions pattern)" matching existing charter usage at `charter/architecture.md` line 220 and `charter/principles.md` line 74. Decisions.md one-liners show D26 = "Security events log separately" and D31 = "Package-level archive document"; the append-only audit chain primitive appears at D22 per the operator's audit observation.

**Substantive observation.** The drift is pre-existing in the charter rather than introduced at Step 6; Step 6 D-entries propagated the existing usage faithfully. The terse one-line D-entry titles in decisions.md may not reflect the full scope of each numbered decision (a decision can cover multiple aspects; the one-liner captures only the lead claim). Cross-references in charter prose (architecture.md, principles.md, methodology.md, bet.md) lean on decisions.md ground truth; if the prose usage does not match the numbered decision, the cross-reference points to the wrong record.

**Proposed audit treatment.** Phase 2 close audit performs a charter-wide D-reference reconciliation pass: every cross-reference in architecture.md, principles.md, methodology.md, bet.md, and the design 7-Step arc reconciles against decisions.md ground truth. Mismatches resolve by either correcting the cross-reference (if the prose meant a different D) or expanding the decisions.md one-liner (if the prose accurately captures a decision aspect the one-liner missed). The reconciliation pass is phase-audit-scoped because it spans the full charter and produces structural corrections beyond Step 6's scope.
