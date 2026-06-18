# S101 smoke — the Map's first slice + the List/Map toggle (D199)

Read-and-render build: the assess surface ("How am I doing") gains a List/Map
toggle, and the Map renders the live goals as goal-anchored, depth-two,
read-only causal nodes. **No migration, no graph write** — the Map is a
read-time projection over the existing `SERVES`/`LEVER_FOR` edges + the
`goal_status` verdict.

## Verified this session (code + test, up to the operator's live gate)

- **Suite green.** `tests/unit` **2292 passed**; `tests/_enforcement` +
  `tests/contract` green. **import-linter 48 contracts kept, 0 broken.** AST
  enforcement (no-vendor-in-domain, no-raw-neo4j-session, no-getenv, host-port
  bindings, dockerfile-workspace) green.
- **The read extension is thin propagation, not a new query (Step-0 finding).**
  The grouped read already fetches the `:Outcome` node via `list_goals`
  (`_LIST_OUTCOMES` returns `mode/ladder/current_target_level/terminal_target/
  terminal_state`); commit 2 carries those onto `GoalGroup` + `GoalGroupDTO`.
  Levers were already present (`GoalGroupDTO.levers`, D191).
- **The render's data contract is proven against the read shape**
  (`tests/unit/apps/api/routers/test_daily_driver_dto_map.py`): the
  measurable-outcome fields reach the wire per mode; the verdict is **copied
  from `goal_status`**, recomputed nowhere; **no DTO field links a unit to a
  specific lever** (the decisive Step-0 invariant, honest on the wire).
- **The render surface is asserted** (`test_daily_driver_surface.py`): the dash
  carries the List/Map toggle over one source (`assessData`, re-rendered on
  toggle — no second data path); the Map render functions draw levers + serving
  work as **sibling feeders** with a **single** intermediary platform-limit
  note. Embedded script passes `node --check`.
- **The live stack serves.** `GET /app` → **200** on the running api
  (`127.0.0.1:8000`); the grouped-read endpoint is live (`401`, auth-gated and
  healthy). The substrate the Map renders is up and intact.

## The live browser pass is operator-gated (the S58/S59/S97b pattern, D189 precedent)

Two properties of the running dogfood instance make the live render
operator-gated, not self-verifiable this session:

1. **Baked image.** The api container has no code/static mounts; it runs a
   2-day-old image. The new render + DTO land at the **next image re-pin** (the
   same baked-image discipline as S68 / the S100 re-pin note).
2. **Google login (D161).** The instance is wired for the Google OIDC verifier,
   not the dev passphrase — so there is no dev-token backdoor to read the authed
   corpus headlessly. The operator's signed-in session is the only path to the
   live read.

D189's own precedent for "browser-verified" is the operator reading the live
surface (S93/S98: the operator, reading it live, corrected the placement). This
session closes at code+test level with the live browser pass operator-gated,
consistent with that precedent and with S58/S59/S97b.

## Operator procedure for the live pass (≈60 seconds, at the next re-pin)

1. `docker compose build padhanam-api && docker compose up -d padhanam-api`
   (re-pin the baked image; no migration to run).
2. Sign in at `/login`, open **How am I doing**, click the **Map** segment.
3. Confirm on the real 8-goal corpus:
   - all 8 goals render as outcome nodes, each with a verdict pill (from
     `goal_status`) and a measurable-outcome chip (progressive: aiming-level;
     sequence: terminal · state; homeostatic: "rhythm held");
   - expanding a goal shows its **levers** (with cadence status) and its
     **serving work** (folded by source type) as **sibling feeders**, never
     work nested under a lever;
   - the **one** platform-limit note about the un-modelled intermediary layer is
     present; **no** per-goal "no path" alarm fires;
   - unlinked work is **off** the Map (a count links to Coverage);
   - the Map reads in seconds; the List/Map toggle flips without a refetch.
4. The live-surface check: if any node reads wrong on the real corpus, that is
   the principle working again — capture it (the S98/S100 pattern).
