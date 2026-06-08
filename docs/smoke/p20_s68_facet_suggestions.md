# S68 smoke — missing-facet suggestions (the runway terminus)

Live verification of the P20 suggestion engine against the running stack (Docker
reachable). The api image was rebuilt + recreated (baked-image discipline; new
digest pinned). No migration, no graph write — suggestions are a read-time
computation.

## Procedure (run, this session)

1. `docker compose build padhanam-api` + `up -d` — rebuilt + recreated.
2. `GET /api/v1/daily-driver/suggestions` — the engine at the current state.
3. A reversible synthetic-edge round-trip to exercise a live suggestion.

## Results (live, 2026-06-08)

- **Correctly silent at 0 SERVES edges.** `GET /suggestions` → `[]`. The
  credulity gate is goal-serving (D170): with no goal facets yet (the two-goal /
  0-edge state from S67), the engine surfaces nothing — silence is the default,
  not a bug.
- **The credulity gate + the satellite-work remedy, proven live (reversible).**
  Linked one **meeting** unit (no task facet) to German via the live wrapper;
  `GET /suggestions` then returned **exactly one** suggestion —
  `satellite_work | Want to add prep or follow-up work for "Megan's articulation
  warm-ups"?` — and **only** for that goal-served unit (the other 978 stayed
  silent). The remedy is satellite work phrased as a question (the
  private-assistant suggestion-as-question), **not** an event mirror. Re-running
  `correlate-units` reset to 0 edges and `/suggestions` went silent again
  (read-time, derived).
- **The panel serves.** `GET /app` returns 200 and carries the Suggestions panel
  (`loadSuggestions`, `id="suggestions"`).

## Operator-gated: the suggestion verdict at six goals + real use

The engine fires only on goal-serving units, so with two goals seeded it is
correctly near-silent. The credulity verdict — does it suggest the *right* facet
*rarely* and *confidently*, or does it nag — is the dogfood week's, against six
goals and the operator's real correlated corpus (task ⊕ calendar ⊕ email units
serving real goals). The three remedies (block for a substantial task with no
time; satellite-work for an event with no task; candidate task for an email) and
the one-per-unit / atomic-one-off / goal-served gates are unit-tested
(`tests/unit/contexts/daily_driver/test_facet_suggestion.py`).

## Runway terminus

P20 is the last package of the Phase 2-A Wave 2 runway (P17→P20). With the
suggestion engine live, the dogfoodable core is built (task ingestion →
correlation → the moat assessment → suggestions). **Next is the dogfood gate** —
a week of real use plus the senior-leader read — not a further surface. The six
real goals are seeded for it (the operator's data step); the constraint
dimensions and the rest of Phase 2-B wait for the dogfood verdict.
