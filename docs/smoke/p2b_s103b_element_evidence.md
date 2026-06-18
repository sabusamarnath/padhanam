# S103b smoke — the element-evidence matcher (D202)

Signal binds to authored elements, not goals. Lexical+alias per-element recall,
multi-attach, goal-level derived on read (SERVES retired), unbound bucket parked.
No direction (S104), no embedding tier (S100 empty corpus).

## Verified this session (code + live re-match on the personal tenant)

- **Suite green.** `tests/unit` passes; `tests/_enforcement` green; **import-linter
  48/0**. New domain tests (binding tiers, multi-attach, derive, conservation,
  summarise) + the two correlate tests moved to the element model.
- **Migration 0006 applied** on the live graph (the `EVIDENCES` relationship
  range index; idempotent — re-run is a no-op).
- **Live binding + isolation (AC8).** The in-container contract guard binds a
  unit to an authored lever via `EVIDENCES`, reads the binding + its `outcome_id`
  + the derived goal edge, and tenant B reads none. 4/4 tenant-isolation contract
  tests pass on the rebuilt image (`d5f7197`).
- **The one-time re-match (AC5, conservation).** `make correlate-units` rebuilt
  1359 units and wrote **847 `EVIDENCES` edges**; `SERVES_remaining = 0` (retired).
  **428 units bound, 931 unbound — conserved: 428 + 931 = 1359, none lost.**
- **The goal level derives on read.** `list_goal_edges` rolls element evidence up
  to one edge per (unit, goal), strongest binding wins; the coverage/grouping
  readers are byte-unchanged (they take `edges` as a parameter).

## The live read (the reflection data)

- **Unbound rate: 68.5%** (931 / 1359).
- **Tiers:** 681 `lexical_keyword`, 166 `lexical_exact`, **0 `alias`** — the
  goal-name recall is fully subsumed by element-keyword matching (an element
  always matched first, so the alias fallback never fired).
- **By element kind:** 361 Lever, 297 Outcome, 189 Intermediary, **0 External**
  (one external authored, nothing matched it — externals are emergent, S104).
- **Multi-attach:** 276 of 428 bound units (64%) evidence ≥2 elements (deg2=161,
  deg3=91, deg4=22, deg6=2) — multi-attach is the common case, not the exception.
- **Diagnosis (reflection 1):** of the 931 unbound, **44% share a token with some
  element label** (matcher-crudeness / thin vocabulary — embedding-tier
  candidates) but **56% share nothing** — much of it genuinely uncovered work the
  model has no element for. The sample's "3 mins Esperanto with Megan" (a recurring
  series with **no authored goal**) is the clean case: correctly parked unbound,
  the coverage-honest read, not a matcher failure.

Benign: the authored-outcome read logs a Neo4j `UnknownPropertyKeyWarning` for
`authored_outcome_origin` / `_proof_state` on outcomes never proofed (the null
coalesce handles it) — the S102 `INFLUENCES`-warning precedent.

## Operator-gated

The full browser eyeball of the element-evidence display (per-element counts + the
unbound bucket on the CDD lens) is operator-gated (Google login). `make build-api`
advanced the pin to `d5f7197`; the lens serves the evidence summary.
