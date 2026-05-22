# Pre-S45 hygiene — Revisable Protocol contract-test harness

This is the v1 brief preserved per the briefs/ discipline (D43; methodology
document "Session brief preservation"). Deviations are recorded in the
session-log entry, not in-place here.

## Goal stated as artefacts at session close

At session close the repository carries:

- `tests/contract/revisable/` exists with conformance tests verifying signature
  shape, return type, and append-only semantics for the Revisable Protocol. The
  harness is parametrised so future Revisable implementers (P14
  methodology-application revision; future Case-level revision) register via the
  same conftest mechanism without harness modification.
- DataPoint.revise verified against the contract as the first registered
  implementer; all scenarios pass.
- Contract tests integrated into the existing test suite; full suite runs
  cleanly at CI.
- `charter/phase-2-audit-inputs.md` updated: the Revisable contract-test harness
  entry moves from "forwarded" to "resolved" with this commit's SHA reference;
  `apps/cli/_cross_context.py` (1704 lines) added to the Phase 2-A close hygiene
  list per principles assessment finding SRP3 with cross-reference to
  `audits/p13-principles-baseline.md`.
- `charter/current-package.md` transitions from "Pre-S45 principles assessment
  closed; S45 next" to "Pre-S45 Revisable harness closed; S45 next".
- Session log entry at `log/sessions.md` capturing the load-bearing-finding-
  closure outcome plus cross-reference to LSP1 and LSP2 from the principles
  assessment.
- `briefs/p13/pre-s45-revisable-harness.md` preserved.

No D-entry additions; this session closes existing charter commitments at D114
and D125 rather than making new architectural commitments. No methodology
document additions; all methodology promotions surfaced by the principles
assessment defer to Phase 2-A close hygiene per the disposition. No new pre-write
reconciliation surfaces; no new brief-format additions.

## Context to read first

1. `charter/decisions.md` — D114, D125.
2. `charter/architecture.md` line 274 — the prose asserting "CI-enforceable
   conformance via contract tests at `tests/contract/revisable/`".
3. `charter/schema.md` Revisable sub-section.
4. `shared_kernel/revisable.py` — the Protocol definition.
5. `contexts/portfolio/domain/data_point.py` — the one current implementer.
6. `tests/contract/http/` and `tests/contract/tenant_isolation/` — existing
   contract-test conventions.
7. `audits/p13-principles-baseline.md` LSP1 and LSP2 sections.

## Pre-write reconciliation

Five narrowly-scoped surfaces: current `tests/contract/` structure; the Revisable
Protocol docstring and signature; DataPoint.revise's current signature (the
intake_id extension per LSP2); existing contract-test conventions; file topology
budget for the new harness files.

## Substantive work

Five commits: (1) charter touchpoint — phase-2-audit-inputs resolution plus SRP3
hygiene-list addition, current-package in-flight marker, brief preservation;
(2) `test(contract)` harness scaffold — `__init__.py` plus `conftest.py` with the
implementer-registration mechanism; (3) `test(contract)` contract scenarios —
`test_revisable_contract.py` with five parametrised scenarios (signature, return
type, append-only, ordering, genesis); (4) `test(contract)` DataPoint implementer
registration — `test_data_point_revisable.py`; (5) `docs` session log entry plus
close marker, transitioning current-package to "Pre-S45 Revisable harness
closed; S45 next".

## Acceptance criteria

1. `tests/contract/revisable/` exists with the four-file structure.
2. The five contract scenarios pass for DataPoint as the registered implementer.
3. The harness's parametrisation mechanism accepts additional implementer
   registrations without harness code modification.
4. The full test suite passes including the new contract tests.
5. `charter/phase-2-audit-inputs.md` accurately reflects the resolved Revisable
   harness debt and the new SRP3 hygiene-list addition.
6. `charter/current-package.md` transitions cleanly across commit 1 and
   commit 5.
7. No D-entry additions, no methodology document additions, no new pre-write
   reconciliation surfaces, no new brief-format additions.

## Out of scope

D-entry additions or supersession; methodology document additions; the YAGNI
monitoring discipline addition; the CP1/CP2 audit-input cluster entries;
retroactive Expected-exercise lines on D124-D128; the file splits SRP1/SRP2/SRP3
(SRP3 newly listed at commit 1, not executed); the other material findings
D1+D2/D3/D4/D7. All deferred to Phase 2-A close hygiene; findings documented in
`audits/p13-principles-baseline.md`.
