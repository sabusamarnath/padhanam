# P12 audit findings

This document is the Phase 1 close audit's consolidated deliverable. Findings are organised into three sections: top-down findings from D-entry verification, bottom-up findings from the codebase tour, and audit-inputs dispositions for the 14 entries at `charter/p12-audit-inputs.md`.

Each finding cross-references where its resolution lives (D-entry number for charter amendments, principle reference for principle modifications, deferred-decisions entry for Phase 2 deferrals, methodology section for methodology updates, or explicit non-action with reasoning). Code-level corrections from audit findings land at follow-on sessions; this document is the synthesis artefact.

The audit reads against the canonical charter set at the time the file landed (D1 through D112; principles.md including the User safety section per D82 and the Vendor flexibility principle per D111; schema.md at the post-S41 + post-S42 state; deferred-decisions.md including the graph-extract reliability entry per pre-P12 hygiene Finding 1) and against the as-built reality at `contexts/`, `apps/`, `padhanam/`, `tests/` at pre-P12 hygiene close (commit afabe7a). The 14 audit-inputs entries are quoted by index from `charter/p12-audit-inputs.md`.

## Section 1: Top-down findings (D-entry verification)

D-entries D1 through D112 verified against as-built. Findings below capture drift requiring disposition; D-entries that verified cleanly are not enumerated. Substantive drift is rare; most P11 D-entries shipped tightly against their commitments.

### Finding T1: D109's "S39 implementation correction" preserves audit trail of pre-write reconciliation miss

D109 commits the gold-set domain shape and includes a strategic-mode plan for compute_chained_payload_hash extraction inside `contexts/audit/domain/events.py` (commit 2.5 in the S39 brief). The plan did not ship. Mid-build reconciliation surfaced the existing `padhanam/security/hash_chain.py` primitive (promoted from `contexts/methodology/` at S24 commit 8 per D75) and the gold-set substrate reuses it directly without triggering an audit-context refactor.

The D-entry handles the drift correctly: the body of D109 stands as the strategic-mode plan; an explicit "S39 implementation correction (appended at session close, 2026-05-15)" section names the three concrete corrections (the audit-context refactor did not land; the primitive already existed at the platform layer; substitution rule for the body) and provides cross-references to the methodology line in the S39 session log entry and the smoke document's "Deviations from the brief" section.

**Disposition.** Non-action at P12. The append-only correction discipline is the structurally honest pattern; the body-plus-correction shape is what the audit-trail commitment requires. The methodology surface absorbs the pattern (mid-build pre-write reconciliation as a distinct sub-pattern of pre-write reconciliation) at Section 3 entry 1's disposition.

### Finding T2: D39 stale framing "(pending operator authorship)" remains active across charter files despite methodology.md being authored and actively maintained

D39 (P3-era) committed methodology.md as a deliverable pending operator authorship. Methodology.md exists, was authored at v1 (P3 post-close per its own version log), and has been the canonical surface throughout Phase 1. The pre-P12 hygiene README expansion repositioned the language from "pending operator authorship per D39" to "methodology framing as living hypothesis" but did not propagate the rebrand into the rest of the charter.

As-built drift sites where the stale "(pending operator authorship per D39)" framing remains:
- `charter/principles.md` line 45 (in the Engineering practice section: "Methodology is measured against DORA and CORE4 per D40. Definitions and cadence will live in `charter/methodology.md` (pending operator authorship per D39).").
- `CLAUDE.md` "Methodology capture" section (refers to "pending operator authorship per D39" and the gap "tracked as a carryover in `current-package.md`"; no such carryover exists post-P11).
- `charter/deferred-decisions.md` "Methodology metrics" entry (refers to "the tagging format that will be specified in `methodology.md` (pending operator authorship per D39)").
- `charter/deferred-decisions.md` "Methodology mechanical-enforcement upgrades" preamble naming `methodology.md` content as the principle landings.
- `charter/methodology.md` version log v1 entry self-referentially names "fulfilling the methodology-document commitment in D39."

**Disposition.** Charter amendment via a new D-entry confirming methodology.md is the active living-hypothesis surface forward, superseding D39's "pending operator authorship" framing without rewriting D39. The principles.md line 45 amends in place at the same commit. Other sites (CLAUDE.md, deferred-decisions.md preamble) update at hygiene moments rather than as part of P12 since they are doc-content rather than binding-specification surface; the new D-entry is the binding correction. Resolution at Section 3's audit-amendments commit chain (commits 5 and 6 in the audit's commit-shape sequence).

### Finding T3: D66's three-strategy catalogue versus the two-strategy as-built adapter — already dispositioned at D110 + deferred-decisions

D66 catalogues three retrieval strategies (vector_only, graph_only, parallel_rrf); the `AgentRetrievalClientAdapter` ships two; `parallel_rrf` is unimplemented at the adapter. D110 alternative (i) explicitly rejected rewriting D66, and the `parallel_rrf` deferred-decisions entry holds the gap with activation trigger language.

**Disposition.** Non-action at P12. The charter-track resolution is already in place via D110 alternative (i) plus the deferred-decisions entry. The audit-inputs entry 9 disposition (Section 3) confirms the parked state holds and refreshes the activation trigger language with the P12-audit-completed verdict on procurement-grade need for three-strategy comparison: not surfaced at Phase 1 close, deferral continues to Phase 2.

### Finding T4: D14's "Forking the platform codebase is forbidden" phrasing was superseded explicitly by D76

D14 originally carried "Forking the platform codebase is forbidden" as a principle. D76 (P7 mid-package strategic block, 2026-05-09) refined the phrasing to "The platform is designed so forking is unnecessary; observed forks signal extension surface failure to be addressed upstream." The principles.md file at line 16 carries the refined wording.

**Disposition.** Non-action at P12. Supersession was explicit, the refinement holds, and the audit trail is preserved. No drift.

### Finding T5: D89's "per-tenant tool authoring deferred to Phase 2" — tool storage at control plane, not per-tenant, despite P8 epic note framing

D89 commits tools and tool_revisions to the control-plane Postgres instance, against the P8 epic note's "per-tenant per D32 (tenants configure their own tools per D14)" framing. D89's reasoning paragraph explicitly resolves the cross-plane reference problem: control-plane `role_revisions.tool_allowlist` cannot durably pin per-tenant tool UUIDs. The per-tenant tool authoring lift defers to Phase 2 via consumer-evidence-driven trajectory.

**Disposition.** Non-action at P12. The deferral was explicit at D89 alternative (h); the architectural reasoning was sound; D78's personal-use deployment provides the eventual consumer-evidence path. No drift.

### Finding T6: D90's streaming-only `AgentExecutor` shipped against the original D88 sync `AgentExecutor` signature with explicit revision

D88 (S27b) committed `AgentExecutor.execute(context) -> AgentResult` as the original Protocol shape. D90 (S29b) revised to `execute(context) -> AsyncIterator[AgentEvent]` with the method name preserved. The revision is documented in D90's body and the as-built `contexts/agent/ports/executor.py` carries the streaming signature.

**Disposition.** Non-action at P12. The revision was explicit; D88 stands with the substrate intent; D90 carries the streaming-only refinement under explicit supersession framing. No drift.

### Finding T7: D107 session-log archival cadence — bootstrap landed, per-package archival on P11 close is in flight at P12

D107 commits per-package session-log archival on package close, forward from P11 close, with a one-time S38b bootstrap covering P0 through P10. The bootstrap shipped at S38b (verified). P11's session entries (S39 through S42 plus pre-P12 hygiene plus the upcoming P12 entry) remain in the live `log/sessions.md` and archive at P11 close, not before.

**Disposition.** Non-action at P12. The cadence is honoured; P11 close lands at the audit-close commit chain. The audit's own session log entry lands in the live file and travels with the rest of P11 to the package archive at the package-close commit.

### Finding T8: D111's MetricCalculator and RecommendationRule pluggable domain abstractions operationalise the vendor-flexibility principle at consumption-pattern granularity

D111 ships pluggable RecommendationRule and MetricCalculator Protocol abstractions; the vendor-flexibility principle at `charter/principles.md` landed alongside D111 with explicit "Procurement-grade commitment: vendor lock-in is not architectural" language and naming of MetricCalculator + RecommendationRule as the operationalisation pattern. The audit-inputs entry 4 frames the verdict and proposes either explicit principle paragraph addition or session-log evidence reliance.

**Disposition.** Non-action at P12. The principle text in place at S41 is structurally honest and already names the operationalisation; no further amendment needed at audit time. The methodology document captures the pattern at Section 3 entry 4's disposition.

### Finding T9: D112's flat-module router convention reinforced as principle-versus-framing-drift instance

D112 explicitly committed the flat-module router convention against the brief's per-context-subdirectory framing (Finding 5 deviation caught at session open). The convention reinforcement is recorded in D112's body and alternatives (a)/(b)/(c) of D112 explicitly reject the subdirectory shape. The methodology candidate at audit-inputs entry 2 (principle-versus-framing drift) absorbs this as the third P11 instance.

**Disposition.** Non-action on the D-entry; the methodology candidate carries forward per Section 3 entry 2's disposition.

### Findings not surfaced: D-entries that verified cleanly without drift

D1 through D108 (excluding D14/D39/D66/D88 noted above) verified cleanly against as-built. The bet's substrate commitments (hexagonal architecture per D16, no-vendor-SDKs-in-domain per D4, audit-as-bounded-context per D26, database-per-tenant per D32, jurisdiction-as-first-class per D12, tenant-isolation contract tests per D24, charter touch-points per CLAUDE.md, append-only logs per D29, decision discipline per D42, methodology-aggregate evolution from D74 → D81 → D86 → D87 → D89, agent runtime architecture per D88 → D90, four-context P11 substrate per D108 → D109 → D110 → D111 → D112) all ship in code matching the D-entry shape.

The four-context P11 substrate scaffold is structurally complete (`contexts/retrieval_evaluation/`, `contexts/run_history/`, `contexts/audit/`, `contexts/optimization/`) and the consumer HTTP surface for all four ships at S34, S37, and S42. The bet's success criterion 4 (the trace capture layer surfaces optimization recommendations, not just data) holds end-to-end at substrate level; the Phase 2 UX deliverable closes the criterion fully per D93.

## Section 2: Bottom-up findings (as-built tour)

[entries land here as audit progresses]

## Section 3: Audit-inputs dispositions

[14 entries from charter/p12-audit-inputs.md get dispositions here]

## Section 4: New entries audit-surfaced

[entries the audit itself surfaces beyond the original 14 land here]

## Cross-reference index

[mapping from finding to resolution location lands here once sections are populated]
