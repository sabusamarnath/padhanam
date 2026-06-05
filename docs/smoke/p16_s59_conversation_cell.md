# P16 / S59 — Live conversational-turn-over-HTTP cell surface (procedural smoke)

The daily driver's open-into-cell becomes a **live conversation** (D158):
opening a Case runs the existing portfolio mirror-conversation cell over
HTTP and the operator continues a grounded, cited conversation about it.
This smoke is **operator-driven against the live stack**: the build
environment cannot reach docker, and per the CLAUDE.md discipline a UI
acceptance criterion is met by **browser interactive verification**, not
CLI smoke. Run the stages below against the running Compose stack and
record the outcome in the session-log close.

This is the **first web render of D131/D138 citation discipline** and it
exercises the cell's real LLM intent extraction (REAL_TIME_REQUIRED,
D122), so the api container must have a working inference model configured
(the same one the WhatsApp mirror cell uses).

Tenant: `tenant_a` = `00000000-0000-4000-8000-00000000a001`
(jurisdiction `eu-west`).

---

## Stage 0 — bring the code up

```bash
make sync-code            # copy contexts/apps/etc into the api container
# (or `make build-api && docker compose up -d --force-recreate padhanam-api`
#  for the production-shaped image path — required for the FastAPI server to
#  pick up the new conversation router, since the server imports at boot)
```

No migration this session — the web adapter is stateless per turn (no new
table). Confirm the new routes are mounted:

```bash
docker compose exec padhanam-api python -c \
 "from apps.api.main import build_app; app = build_app() if False else None; \
  import apps.api.routers.conversation as c; \
  print([r.path for r in c.router.routes])"
```

Expect `/api/v1/daily-driver/conversation/open` and `.../turn`.

## Stage 1 — mint a dev token + ensure a Case with data points exists

```bash
docker compose exec padhanam-api python -c \
 "from padhanam.security.auth import issue_dev_token; \
  print(issue_dev_token(subject='operator-001', \
  tenant_id='00000000-0000-4000-8000-00000000a001', roles=['operator']))"
```

Ensure tenant_a has at least one **OPEN Case** with a couple of data points
(create via the portfolio surface or the manual-entry WhatsApp cell if
needed) so the opening turn has something to cite.

## Stage 2 — CLI wiring-proof (open + one turn)

A pre-browser sanity check that the round-trip is wired (not a substitute
for Stage 3):

```bash
TOKEN=...      # the JWT from Stage 1
CASE_ID=...    # an OPEN tenant_a case id

# open: runs the cell's open + opening turn on the focus Case
OPEN=$(curl -sk -X POST https://localhost/api/v1/daily-driver/conversation/open \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"focus_kind\":\"CASE\",\"focus_id\":\"$CASE_ID\"}")
echo "$OPEN" | python -m json.tool

# turn: thread the returned state back, ask a follow-up
STATE=$(echo "$OPEN" | python -c "import sys,json;print(json.dumps(json.load(sys.stdin)['state']))")
curl -sk -X POST https://localhost/api/v1/daily-driver/conversation/turn \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"state\":$STATE,\"text\":\"list my cases\"}" | python -m json.tool
```

Expect: the `open` response carries `reply` (the cell's opening text naming
the Case), `state` (conversation_id, turn_count 1, is_open true,
`cell_payload.current_focus_artefact`), and `citations` (source-typed
chips with human labels, **no raw UUID** in `reply`/`label`/`ref`). The
`turn` response advances `turn_count` to 2.

## Stage 3 — browser interactive verification (the success criterion)

Open `/app` in a browser, paste the token, click **Use token**. Then:

1. **Open a Case** → the side panel opens as a **conversation thread**, not
   a read-only context panel; the opening assistant bubble names the Case
   and lists its data points.
2. **Citations render** beneath the assistant bubble as chips
   (`CASE · <title>`, `DATA POINT · <label>`); **no raw UUID** is visible.
3. **Type a follow-up** (e.g. "what data points does it have?" or a
   drill-down like "tell me about <a data point>") and **Send** → the reply
   renders in the thread. *This is the felt deliverable — judge whether it
   reads as continuing a grounded conversation about the item, the thing
   the S58 view-only open could not do.*
4. **Drill-down threads statelessly:** after the cell shows a case, ask a
   relative follow-up ("drill into <child>"); the focus follows (the
   client-threaded `cell_payload`, no server thread).
5. **Ambiguous reference → clarification:** if two cases share a title (seed
   a duplicate if needed), opening/asking for it surfaces a numbered
   clarification ("Which did you mean? 1. … 2. …"), **not** a silent pick;
   replying with a number resolves it.
6. **Read-only discipline holds:** no write or communication action fires
   from a turn without being surfaced first.

## Stage 4 — tenant isolation

Mint a token for tenant_b (`...0000b002`); with it, calling `open` on a
tenant_a `focus_id` returns **404** (no turn runs on another tenant's
item). The wiring-level isolation invariant is also covered by
`tests/unit/apps/api/test_conversation_cell.py::test_turn_cannot_open_a_case_outside_the_actors_tenant`.

---

## Record at close

- Did opening a Case render a live conversation thread (AC2)? yes/no.
- Did citations render as source-typed chips with human labels, no raw
  UUID (AC3)? yes/no.
- Did a typed follow-up render a reply — the round-trip live (AC2)? yes/no.
- Did an ambiguous reference route to clarification, not a silent default
  (AC4)? yes/no.
- Did tenant_b's open on a tenant_a case 404 (AC6)? yes/no.
