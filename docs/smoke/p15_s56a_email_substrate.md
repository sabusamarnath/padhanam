# P15 S56a — Email data substrate + measurement

Procedural smoke for the email data substrate. The **load-bearing
deliverable is the measurement**: the message count over the bounded
window and the full pull-store-index wall-clock (the full-pull refresh
cost). Those two numbers decide the two deferred framings — the email
sync-mechanism graduation (incremental) and the refresh-before-answer
strategy (D150 Option A vs background-sync-then-serve) — before S56b opens.

**Procedural** — operator-executed live. The agent cannot run the
measurement because there is no google-mail Nango connection yet (only
google-calendar is provisioned); provisioning google-mail is the gate,
mirroring calendar.

## Provisioning gate (operator, first)

Mirroring the calendar Nango provisioning: in the Nango dashboard, create/
connect the **google-mail** provider (`gmail.readonly` scope; proxy base
`https://gmail.googleapis.com`), complete the OAuth flow, and confirm a
`200` from a `users.messages.list` Proxy call (Bearer auth). Record the
connection id and add a `google-mail` `Connection` row for `tenant_a`
(or via the S56b wiring). **Then rebuild the baked image** (`make build-api`
+ `docker compose up -d --force-recreate padhanam-api`) — this also bakes
the S55b-2 dispatch + citation code, retiring its synced-source residue.

## Stage 1 — Verified-handles pull + the measurement (load-bearing)

Through `build_email_sync_components(tenant_id=tenant_a)`, run `sync_email`
over the bounded window (`newer_than:30d`). **Record:**
- the **message count** over the window;
- the **full pull-store-index wall-clock** end to end (list + batched get
  + store + chunk + embed + graph), with a list / get / embed breakdown if
  available — this is the full-pull refresh cost.

These two numbers feed the deferred sync and refresh decisions: does the
volume justify incremental sooner rather than later, and does the floor
kill D150 Option A in favour of background-sync-then-serve.

## Stage 2 — Store round-trip + encryption

Confirm message-id-keyed `emails` rows; subject/body/from/to/cc/snippet
encrypted at rest (`enc_*` populated, no plaintext in the row — cross-check
the `test_serialized_content_encrypts...` expectation); a no-change re-pull
is a no-op (same `content_hash`, no new rows); `email_connections.history_id`
populated (the dormant anchor).

## Stage 3 — Set-diff deletion (operator-gated)

Trash one in-window message in Gmail, re-run `sync_email`, and confirm the
stored `emails` row tombstones via set-diff (`deleted_at` set; `enc_*` +
`content_hash` NULL; its `email_chunks` rows deleted; row retained). If not
trashed, record as operator-gated (the agent is `gmail.readonly`),
mirroring calendar's cancellation gate.

## Stage 4 — Index round-trip

Confirm `email_chunks` rows carry per-chunk embeddings for changed
messages, and sender/recipient `:Person` entities + `CORRESPONDED_WITH`
relationships appear in Neo4j scoped to `tenant_a`.

## Result

Record per stage: pass/fail, **the measured message count and the full
pull-store-index wall-clock (Stage 1, load-bearing)**, the store +
encryption evidence (Stage 2), the set-diff tombstone status (Stage 3), and
the index evidence (Stage 4). The measurement is the input the email
sync-mechanism and refresh-strategy decisions are made from, ahead of S56b.

**Status: pending operator execution** (the google-mail Nango provisioning
gate is not yet complete; the agent cannot run the measurement). The email
sync and refresh decisions get made from the measurement before S56b opens.
