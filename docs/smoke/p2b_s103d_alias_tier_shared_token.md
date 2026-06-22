# S103d smoke — align the matcher's match rule to the read-side basis rule (D204)

The first touch on matcher binding logic in the S103c sub-series. The matcher's
shared keyword/alias match rule now requires a shared significant token (the
substring branch is dropped), single-sourced to the read-side basis rule the
honest-why (S103c-fix-3) already applies — so the matcher stops creating the
binds the read side narrates as `NO_CLEAR_BASIS`.

## Step 0 findings (three brief-premise corrections)

1. **Stamping stale.** The brief's "number off S100" reflects the lagged
   strategic snapshot; live max is S103c-fix-4, so this is **S103d** / **D204**
   (S104 stays reserved for direction).
2. **`_keyword_match` is one shared function** used by *both* the keyword and
   alias tiers, not an "alias-only path" — so dropping substring aligns both
   tiers (the true single-source). The keyword tier had **zero** substring-only
   binds live, so only the alias substring-only binds change in practice.
3. **Baseline drifted** to **10 of 745** (all alias, all substring-only) from the
   brief's 12 of 839, same pattern. Single-source is **feasible** (matcher +
   read side in one module, no import boundary), so the stronger "one shared
   symbol" form was taken, not just align-and-tie-test.

## Verified this session (code + live)

- **Suite green.** `tests/unit/contexts/daily_driver` + the surface guard pass;
  `tests/_enforcement` green; **import-linter 48/0**.
- **Single-sourced.** One `significant_tokens` / `shared_significant_tokens`
  helper is the only place the non-stopword token set is computed; `_keyword_match`
  (matcher) and `binding_rationale` + `element_token_counts` (read side) all read
  through it, so they cannot drift.
- **Tie-test (the divergence guard).** `test_match_rule_ties_to_the_read_side_basis_rule`
  asserts the matcher binds a (unit, target) pair iff the read side finds a basis,
  for both the keyword and alias tiers, across exact / shared-token / substring-only
  / disjoint pairs. Precision (substring-only with no shared token does not bind)
  and recall (a genuine shared token still binds) are guarded at the helper level
  and through `infer_element_evidence`'s alias fallback.
- **Live re-measure (ids only, no content — D21).** `ops/measure_alias_basis`
  reads the live bindings through the surface read path and counts the read side's
  `NO_CLEAR_BASIS` verdicts by tier:
  - **Before** (accumulated state, old image): 745 bindings / 431 bound units /
    **10 no-clear-basis, all alias**.
  - **After** (re-correlate on the tightened matcher, idempotent across two runs):
    727 bindings / 421 bound units / **0 no-clear-basis**.
  - The baseless binds the honest-why flagged are **gone, zero residual**. The net
    drop (−18 bindings) exceeds the 10 baseless because the 745 baseline was
    accumulated live state (corrections + prior runs), not the old matcher's fresh
    fixed point; the rule change is purely subtractive (a shared-token bind cannot
    be dropped by requiring a shared token — precision + tie tests prove it, and
    the 0 residual confirms nothing baseless survived).

## Operator-gated

The live read of the bindings (no baseless alias "no clear basis" anywhere across
List, Map, CDD) is the browser pass. `make build-api` advanced the pin; the
re-correlate ran in-container via `make correlate-units`.
