# S67 smoke — goal-aligned assessment (the moat)

Live verification of the P19 assessment build against the running stack (Docker
reachable). The api image was rebuilt and recreated before correlate (the
baked-image discipline; new digest pinned in `compose.yaml`). No migration —
the `SERVES` edge connects existing `:Unit`/`:Outcome` nodes (no new label).

## Procedure (run, this session)

1. `docker compose build padhanam-api` + `up -d` — rebuilt + recreated.
2. `python -m ops.correlate_units` — now two steps: unit correlation (D168) then
   goal-facet correlation (D169).
3. `GET /api/v1/daily-driver/assessment` — the two reads.
4. A reversible synthetic-edge round-trip to exercise the SERVES write live.

## Results (live, 2026-06-08)

- **The two-step correlate runs end-to-end.** `unit correlation complete: 979
  units written`, then `goal-facet correlation complete: 0 SERVES edges
  written` — **0 is the correct, predicted state at two seeded goals** (German
  S62 progressive, Get a job S63 sequence): the operator's calendar work
  ("3 mins Esperanto with Megan", medication reminders, …) does not title-match
  the German lever-commitment name nor keyword-match "German"/"Get a job", so
  nothing links yet. This is the build-the-logic-now, judge-at-six state.
- **Both reads compute correctly against real data.** `GET /assessment` →
  `orphan_work: 979`, `neglected_goals: ['German', 'Get a job']`,
  recommendation-shaped reasons ("“…” points at no goal you're tracking.").
- **The SERVES write + both reads, proven live (reversible round-trip).** Wrote
  one synthetic confirmed edge (a real unit → German) through the live wrapper:
  `list_goal_edges` read it back (`status: confirmed`); `GET /assessment` then
  showed **German off the neglected list** (`neglected_goals: ['Get a job']`)
  and the **linked unit off the orphan list** (979 → 978). Re-running
  `correlate-units` reset to the honest derived state (979 orphans, both goals
  neglected) — proving the SERVES MERGE, both reads' edge-sensitivity, and the
  derived-state replace, without mutating any cache.
- **Tenant isolation (D24/D63).** tenant_b token → `GET /assessment` returns
  `{orphan_work: [], neglected_goals: []}`.
- **The panel serves.** `GET /app` returns 200 and carries the "How am I doing"
  panel (`loadAssessment`, `id="assessment"`).

## Operator-gated: the moat verdict at six goals

With only German and Get a job seeded, everything else floods as orphan and both
goals read neglected — the output is **only meaningful at six goals** (the
operator's call). Seed the other four real goals (the `make seed-german` /
`make seed-get-a-job` scripts as the pattern), re-run `make correlate-units`,
and judge the moat read then: does orphan-work surface genuinely adrift work,
and does the neglected-goal read catch a goal you've stopped feeding? The
confidence-tiered inference (confirmed = unit-facet vs lever-commitment name;
candidate = lean keyword vs goal name) is unit-tested
(`tests/unit/contexts/daily_driver/test_goal_assessment.py`); the live moat
verdict is the dogfood week's, against six goals and your real corpus.
