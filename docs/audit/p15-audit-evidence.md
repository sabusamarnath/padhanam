# P15 Audit — Evidence Pack

Evidence-gathering pass against the live repo on branch `methodology`, HEAD `d52f6fe`.
This document surfaces and tags evidence only. It performs **no disposition** (whether a
divergence is acceptable), no remediation, and no methodology ratification — those are the
strategic read's job against this pack plus an independent pass.

Each finding is tagged exactly one of **CONFIRMED-DRIFT** / **CANDIDATE-DRIFT** /
**VERIFIED-CONSISTENT**.

## Clean-bytecode discipline (recorded)

`find . -name __pycache__ -type d -prune -exec rm -rf {} +` was run **before every** code/test
probe in this pass (three times: before import-linter, before the full suite, before each
unit+contract run). Resulting enforcement counts from cleared bytecode:

- `uv run lint-imports` → **Contracts: 41 kept, 0 broken.**
- `uv run pytest -p no:cacheprovider tests/unit tests/contract` → **exit 0** (no failures).
- Full default tier (`uv run pytest -p no:cacheprovider`) → **3 failures, all in `tests/e2e/`
  and `tests/integration/` requiring live infra** (Postgres/Ollama); none in `tests/unit`,
  `tests/contract`, or `tests/_enforcement` (see Check 6).

---

## Findings by tag (count)

- **CONFIRMED-DRIFT: 14**
- **CANDIDATE-DRIFT: 7**
- **VERIFIED-CONSISTENT: 25**

(46 findings total. Where a check had both a verified surface and a divergent one, the verified
half is recorded under its own finding ID and the divergence under another, so each finding
carries exactly one tag.)

---

## Check 1 — D-entry presence and internal consistency

### F1.1 — D142–D154 present and well-formed — VERIFIED-CONSISTENT
- Check: all P15 D-entries present, index lines included.
- Evidence: index lines `charter/decisions.md:131-143` (D142…D154); full entries
  `charter/decisions.md:207` (D142), `:209` (D143), `:211` (D144), `:213` (D145), `:215`
  (D146), `:217` (D147), `:219` (D148), `:221` (D149), `:223` (D150), `:225` (D151), `:227`
  (D152), `:229` (D153), `:231` (D154). Each carries Choice/Reasoning/Alternatives/Kano/
  References content and a `(P15, S__, date)` stamp.

### F1.2 — D149 supersedes D148 with an explicit header — VERIFIED-CONSISTENT
- Check: a later D-entry that narrows an earlier one says so.
- Evidence: D149 title (`charter/decisions.md:138`, `:221`) — "…**supersedes D148's
  receive-side sync clause**"; body: "this entry supersedes its receive-side sync clause only,
  leaving auth/scope/Meeting model/encryption/substrate-inheritance intact." The narrowing is
  logged.

### F1.3 — D153 narrows D147's THRESHOLD_CROSSED idempotency semantics without an explicit supersession header — CANDIDATE-DRIFT
- Check: hunt for a later D-entry that reverses/narrows an earlier one without saying so.
- Charter (earlier): D147 (`charter/decisions.md:217`) commits the THRESHOLD_CROSSED
  idempotency key as "composite of `matched_audit_event_id` plus `rule_id`."
- Charter (later): D153 (`charter/decisions.md:229`) replaces it: "The `THRESHOLD_CROSSED`
  idempotency key is therefore the crossing's derived-state identity …, **not a
  matched-audit-event id**." D153 references D147 and explains the change in substance, but —
  unlike D149's explicit "supersedes D148's … clause" header — carries **no** explicit
  "supersedes D147's idempotency clause" label.
- Evidence of the asymmetry: D149 title vs D153 title (`:138` vs `:142`).

### F1.4 — D152 References line cites "D53/D54 trigger infra"; D53/D54 are unrelated P5 decisions — CONFIRMED-DRIFT
- Check: resolve every cross-reference (D-n exists and says what the citation implies).
- Charter: D152 References (`charter/decisions.md:227`): "…the two-threshold rule, **D53/D54
  trigger infra**."
- As-built referents: D53 = "P5 evaluation harness framing" and D54 = "Applier port shape"
  (`charter/decisions.md:70-71`) — both P5, neither is trigger infrastructure. The intended
  referent is the **S53/S54** broadcast sessions (or D143/D145), which the *same D152 body*
  cites correctly ("reusing the **S53/S54** BroadcastDispatch infra," `:227`). The References
  line reads `D` where the body reads `S`.

---

## Check 2 — Charter-versus-code conformance on load-bearing claims

### F2.1 — THRESHOLD_CROSSED idempotency key contains no `matched_audit_event_id` — VERIFIED-CONSISTENT
- Check: idempotency key derivation carries no `matched_audit_event_id`.
- As-built: `contexts/messaging/domain/idempotency.py` — `resolve_idempotency_key` →
  `_threshold_crossed_key` (`:97-112`) consumes `metadata["crossing_identity"]`; the symbol
  `matched_audit_event_id` does not appear in the file. (But see F2.2 / F4.4 — the *docstring
  and fallback* in this same file are stale on the cancelled_at sub-shape.)

### F2.2 — Crossing identity is derived-state and **excludes** `cancelled_at`; idempotency.py docstring/fallback still assert `cancelled_at` — CONFIRMED-DRIFT
- Check: the THRESHOLD_CROSSED idempotency key shape S57 actually built.
- As-built SSOT: `contexts/threshold_briefing/domain/rule_match.py:50-71` —
  `RuleMatch.crossing_identity()` returns `rule_id:event` for a cancellation (line 71) and
  `rule_id:eventA|eventB` (sorted) for a conflict (line 69-70); docstring (`:56-66`):
  "The cancellation identity deliberately **excludes** `cancelled_at`." This value is what is
  placed on the metadata (`to_trigger_metadata`, `:91`) and consumed by the resolver.
- Stale residue in the same area: `contexts/messaging/domain/idempotency.py:21-24` docstring
  says the key is "`metadata["crossing_identity"]` (rule_id + event + **cancelled_at**, …)";
  and the fallback `_threshold_crossed_key` (`:109-112`) builds
  `f"{rule_id}:{google_event_id}:{cancelled_at}"` — both embody the pre-S57-refinement shape
  that includes `cancelled_at`. (Fix landed at commit `8fa8203` "stabilise cancellation
  crossing identity"; the docstring + fallback were not updated.)

### F2.3 — ThresholdEvaluator reads the calendar state store via a reader port, does not poll the audit chain — VERIFIED-CONSISTENT
- Check: evaluator reads state store, not audit chain.
- As-built: `contexts/threshold_briefing/application/threshold_evaluator.py:138-140` —
  `await self._state_reader.list_meetings(actor=…, include_cancelled=True)`; the only
  collaborators are the refresh/state-reader/emitter consumer ports (`:42-51`, `:82-94`); no
  `AuditPort`, no chain read. Domain rules are pure functions over `MeetingState`
  (`contexts/threshold_briefing/domain/evaluation.py:39-157`).

### F2.4 — `sync_calendar` takes no AuditPort and emits no audit events — VERIFIED-CONSISTENT
- Check: sync_calendar emits no audit events.
- As-built: `contexts/calendar/application/sync_calendar.py:67-81` signature carries
  `event_source / connections / meetings / meeting_reader / embedder / graph_index` — **no**
  AuditPort. `grep -ni audit contexts/calendar/application/sync_calendar.py` → no matches.
  Docstring confirms the scoped-full-pull-only, token-free path (D149).

### F2.5 — A fourth (synthetic) implementer registers in the BroadcastFlow contract conformance set alongside the three production implementers — CANDIDATE-DRIFT
- Check: three implementers register (daily-briefing, threshold-briefing, ThresholdEvaluator).
- As-built (production wiring): `apps/api/main.py` registers exactly three by trigger_type —
  `DAILY_SCHEDULED` (`:472-473`, daily-briefing), `SCHEDULED_EVALUATION` (`:527-528`,
  ThresholdEvaluator), `THRESHOLD_CROSSED` (`:531-532`, threshold-briefing). (The production
  three are recorded as VERIFIED under F5.1.)
- Candidate nuance: the BroadcastFlow contract conformance registry has **four**
  registrations — the three above plus a **synthetic** harness implementer
  (`tests/contract/broadcast_flow/test_synthetic_broadcast_flow.py:1-13` — "a synthetic
  implementer … carries forward as a baseline harness verifier"). Whether the close criterion
  "three implementers register" should be read against the production registry (three) or the
  conformance set (four) is a judgment call. → **CANDIDATE-DRIFT.**

### F2.6 — Two ArtefactCitation docstrings still describe a three-type union with email "future", though the enforced set is four — CANDIDATE-DRIFT
- Check: discriminator at the type count the D-entries claim (case, data_point, meeting, email).
- As-built (enforced): `shared_kernel/conversation_flow.py:149-155` —
  `KNOWN_ARTEFACT_TYPES = frozenset({CASE, DATA_POINT, MEETING, EMAIL})`; `__post_init__`
  validates against it (`:181-190`). Four types. (The four-type enforced set is recorded as
  VERIFIED under F5.6.)
- Candidate nuance: docstrings at `:26-28` ("Phase 2-A discriminator union is `case`,
  `data_point`, and `meeting`; future artefact types (`email` at S56) extend the union") and
  `:170-171` ("Phase 2-A union: `case`, `data_point`, `meeting`") describe email as future /
  omit it, though email is already in the enforced set (`:154`, and `:144` correctly notes
  "`email` added at S56a, D151"). → **CANDIDATE-DRIFT** (internal docstring staleness).

### F2.7 — email cell imports `EmailRefreshPort`, never reaches `sync_email` — VERIFIED-CONSISTENT
- Check: the email cell imports EmailRefreshPort and not sync_email.
- As-built: `contexts/email_conversation/application/cell.py:31-33` imports `EmailRefreshError,
  EmailRefreshPort`; `:144` injects `refresh_port: EmailRefreshPort | None`; `:244` catches
  `EmailRefreshError`. The only `sync_email` token in the file is the docstring (`:12`) stating
  "it never reaches through to `sync_email`." No import of `sync_email`.

---

## Check 3 — Deferred-decisions register completeness

### F3.1 — Table of contents omits four body sections, including BOTH P15 sections — CONFIRMED-DRIFT
- Check: the TOC lists the sections the body actually contains.
- Charter: TOC (`charter/deferred-decisions.md:11-21`) lists 11 sections, ending at
  "11. P13 S45 deferrals."
- As-built (body level-2 headers): 15 sections. The TOC omits **`## P14 framing deferrals`
  (`:689`), `## P14 close deferrals` (`:721`), `## P15 framing deferrals` (`:733`), and
  `## P15 S54 deferrals` (`:761`)** — i.e., both P15 deferral sections are absent from the TOC.

### F3.2 — Calendar meeting-moved threshold deferral is not in the register — CONFIRMED-DRIFT
- Check: confirm it is in deferred-decisions.md with an activation trigger, not only in a
  D-entry / session log.
- Charter: the meeting-moved deferral is named in D153 (`charter/decisions.md:229`), D154
  (`:231`), and `charter/architecture.md:455` ("meeting-moved — which needs prior-vs-current
  start retention … deferred to dogfooding").
- As-built register: `grep -ni "meeting.moved|moved" charter/deferred-decisions.md` → **no
  match**. There is no dedicated register entry with an activation trigger. (The nearest entry,
  "Stable original cancellation timestamp + cancellation-title enrichment," `:809-817`,
  concerns cancellation, not meeting-moved.)

### F3.3 — Email incremental-sync graduation deferral is not in the register — CONFIRMED-DRIFT
- Check: confirm the email incremental graduation deferral is registered.
- Charter: deferral named in D151 (`charter/decisions.md:225`, "the incremental graduation
  (volume) … decided against the S56a measured count") and D154 (`:231`).
- As-built register: `grep -ni incremental charter/deferred-decisions.md` → **no match.** The
  "Background sync for calendar and email" entry (`:737-743`) covers background sync
  (poll/webhook), not incremental-sync graduation; it references D14/D110 only.

### F3.4 — Email IMAP / provider-agnostic transport deferral is not in the register — CONFIRMED-DRIFT
- Check: confirm the IMAP / provider-agnostic transport deferral is registered.
- Charter: named in D151 (`charter/decisions.md:225`, "IMAP/provider-agnostic transport defers
  to Phase 2-B per the two-threshold rule").
- As-built register: `grep -niE "imap|provider.agnostic" charter/deferred-decisions.md` → only
  `:35` (an unrelated agent-orchestrator entry on provider coupling). No IMAP/transport
  deferral entry. (The "MCP transport swap" entry `:745-751` is about MCP, not IMAP.)

### F3.5 — `after_state` change-data-capture / provenance deferral is registered with an activation trigger — VERIFIED-CONSISTENT
- Check: the CDC/provenance question is in the register.
- As-built: `charter/deferred-decisions.md:801-807` — "### Audit-chain change-data-capture for
  substrate state changes (provenance completeness)" with "What defers" and an explicit
  "Activation trigger." References D153, D148/D149, D151, D102/D131.

### F3.6 — Portfolio-content classification is in the "Compliance and security" section as reported — VERIFIED-CONSISTENT
- Check: verify it is actually forwarded to Compliance and security.
- As-built: section `## Compliance and security` (`charter/deferred-decisions.md:407`) contains
  "### Tenant-content-at-rest encryption classification (portfolio Case titles / DataPoint
  values; intake hints; pending-clarification summaries)" (`:409-415`) with revisit triggers.

### F3.7 — "Email tool service" entry is not closed by D151 (sibling calendar entry is closed by D148) — CONFIRMED-DRIFT
- Check: confirm resolved entries gained their `Status: closed by D-n` headers; the Email tool
  service entry should be closed by D151.
- As-built: `charter/deferred-decisions.md:477` — "**Status: activated at P15 framing
  (2026-05-27)** … The specific D-entry … lands at S56." No "closed by D151" header, though
  D151 has landed (`charter/decisions.md:225`).
- Sibling contrast: the calendar entry (`:467`) reads "**Status: closed by D148, 2026-05-28.**"

### F3.8 — THRESHOLD_CROSSED metadata register entry still asserts the stale `matched_audit_event_id` shape — CONFIRMED-DRIFT
- Check: confirm the metadata entry reflects the derived-state shape S57 built, not a stale
  `matched_audit_event_id`.
- As-built register: `charter/deferred-decisions.md:787` — "THRESHOLD_CROSSED metadata commits
  at S57: fields `matched_audit_event_id`, `rule_id`, `matched_value`." None of those three is
  the as-built field set; the actual metadata (`contexts/threshold_briefing/domain/
  rule_match.py:73-92` `to_trigger_metadata`) carries `rule_id, rule_type, google_event_id,
  meeting_id, title, summary, cancelled_at, partner_event_id, partner_title, crossing_identity`
  — no `matched_audit_event_id`, no `matched_value`.

### F3.9 — Background-sync register entry does not reflect the D152 Option-A refinement — CONFIRMED-DRIFT
- Check: confirm the background-sync entry reflects the D152 Option-A refinement.
- As-built register: "### Background sync for calendar and email at messaging context"
  (`charter/deferred-decisions.md:737-743`) is the P15-framing-dated entry; it frames
  pull-on-demand-vs-background-sync and references **D14, D110 only**. `grep -ni D152
  charter/deferred-decisions.md` → **no match anywhere in the file.** The D152 refinement
  (Option A full-pull-in-turn behind the refresh port, background-sync/incremental deferred as
  measurement-gated port swaps) is not reflected in this entry.

### F3.10 — Evaluator/Scan second-instance abstraction is mentioned in passing but is not a standalone register entry — CANDIDATE-DRIFT
- Check: confirm the Evaluator/Scan second-instance abstraction deferral.
- Charter: the deferral logic appears in D153 / `charter/architecture.md:448` ("the
  two-threshold rule keeps them one context until a second proactive surface forces a split")
  and in the threshold_evaluator docstring ("the deliberate cost of reusing BroadcastDispatch
  for both the scan and the briefing," `contexts/threshold_briefing/application/
  threshold_evaluator.py:27-30`). The "second proactive surface" trigger is folded into the CDC
  entry's activation trigger (`charter/deferred-decisions.md:807`).
- As-built register: no dedicated "### …second proactive surface / Evaluator-Scan split" entry
  with its own activation trigger. Whether the in-passing coverage suffices is a judgment call.

---

## Check 4 — In-flight correction loops (code vs charter residue)

### F4.1 — D149 nextSyncToken / scoped-full-pull correction landed in code — VERIFIED-CONSISTENT
- As-built: `contexts/calendar/application/sync_calendar.py:67-91` (scoped full pull every
  call, no stored sync token, `showDeleted=true`); dormant incremental machinery preserved and
  unreferenced by the active path: `contexts/calendar/adapters/outbound/nango/
  nango_proxy_calendar_adapter.py:106` (`list_events_incremental`), `:156-158`
  (410 → `SyncTokenExpiredError`), docstring `:20-21` ("remain for the dormant incremental
  path"). Matches D149 (`charter/decisions.md:221`).

### F4.2 — D151 getProfile anchor + email-local chunker correction landed in code — VERIFIED-CONSISTENT
- As-built: `contexts/email/adapters/outbound/nango/nango_proxy_email_adapter.py:14-15,138-151`
  (`get_mailbox_history_id` reads `users.getProfile`); dormant `history_id` columns
  `contexts/email/adapters/outbound/postgres/_tables.py:35-36,56`; email-local chunker
  `contexts/email/domain/email_chunking.py` + `email_chunk.py`. Matches D151
  (`charter/decisions.md:225`).

### F4.3 — D153 audit-chain→state-store rewording landed in the epic S57 line and architecture prose — VERIFIED-CONSISTENT
- As-built: `charter/packages/p15-epic.md:35` ("**evaluates over the calendar state store**
  (not the audit chain …)"); `charter/architecture.md:453` ("**Why evaluate over state, not the
  audit chain (the S57 reconciliation correction).**"). Both carry the corrected model.

### F4.4 — D47 provenance correction on the methodology-write item is recorded — VERIFIED-CONSISTENT
- As-built: `charter/methodology.md:593` (v6 entry) — "*Provenance note (the D47 correction).*
  The S55b-1 build prompt directed this promotion as a build task, which is the wrong authority
  under D47 … ratified strategic-mode as of 2026-06-02; only its provenance was mislabelled …"

### F4.5 — cancelled_at idempotency fix (identity stable, window lower-bound only) landed correctly in code — VERIFIED-CONSISTENT
- As-built: identity stable — `rule_match.py:50-71` excludes `cancelled_at` (F2.2). Window
  lower-bound only — `contexts/threshold_briefing/domain/evaluation.py:46-59` (`del window_end
  # not an upper bound`; match on `cancelled_at >= window_start`, `:64`). Matches D153's
  live-smoke refinement (`charter/decisions.md:229`) and architecture.md:455.
  (NOTE: the *docstring/fallback* residue in idempotency.py is F2.2, CONFIRMED-DRIFT.)

### F4.6 — `matched_audit_event_id` pre-correction shape persists in `shared_kernel/broadcast_flow.py` docstring — CONFIRMED-DRIFT
- Charter/code (code surface): `shared_kernel/broadcast_flow.py:67-72` — "the THRESHOLD_CROSSED
  trigger carries `threshold_rule_id` plus **`matched_audit_event_id`**."
- As-built metadata: neither key exists; the actual metadata uses `rule_id` (not
  `threshold_rule_id`) and has no `matched_audit_event_id` (`rule_match.py:81-92`).

### F4.7 — `matched_audit_event_id` persists in schema.md — CONFIRMED-DRIFT
- Charter: `charter/schema.md:1397-1398` — "THRESHOLD_CROSSED at S57 uses a composite of
  **`matched_audit_event_id` plus `rule_id`**."
- As-built: derived-state identity, no `matched_audit_event_id` (`rule_match.py:50-71`).

### F4.8 — `matched_audit_event_id` persists in architecture.md, internally contradicting the same file — CONFIRMED-DRIFT
- Charter: `charter/architecture.md:487` — "THRESHOLD_CROSSED at S57: composite of
  **`matched_audit_event_id` plus `rule_id`**." This **contradicts** `charter/
  architecture.md:455` in the same document — "the crossing's derived-state identity
  (cancellation: `rule_id` + `google_event_id`; conflict: `rule_id` + the unordered event
  pair) … The cancellation identity **excludes `cancelled_at`**." The S57 correction updated
  the threshold-briefing subsection (`:446-455`) but not the older idempotency subsection
  (`:487`).
- As-built: `rule_match.py:50-71` agrees with `:455`, not `:487`.

### F4.9 — `matched_audit_event_id` test fixture in the broadcast unit test — CANDIDATE-DRIFT
- Evidence: `tests/unit/shared_kernel/test_broadcast_flow.py:48` uses `"matched_audit_event_id":
  str(uuid4())` as example THRESHOLD_CROSSED metadata. Harmless to the green suite (metadata is
  an open dict), but it perpetuates the pre-correction key name as a worked example.

### F4.10 — architecture.md carries the D150-superseded calendar refresh-floor figures — CONFIRMED-DRIFT
- Charter (later/superseding): D150 (`charter/decisions.md:223`) — "artifact-verified at the
  S55b-1 close smoke … **~250 ms steady, 524 ms cold** — superseding the synced-source
  S55a-fix figures of 340–400 ms steady / 513 ms cold."
- Charter (stale residue): `charter/architecture.md:306` — "the measured refresh floor
  (**340–400 ms steady, 513 ms cold; S55a-fix smoke**)." The living architecture prose still
  cites the figures D150 explicitly superseded.

### F4.11 — Enforcement-masking affected-window annotation not found in `phase-2-audit-inputs.md` — CANDIDATE-DRIFT
- Check: the enforcement-masking affected-window annotation in `phase-2-audit-inputs.md`.
- As-built: `charter/phase-2-audit-inputs.md` (71 lines; headers enumerated) contains a
  *migration*-masking entry (`:47-49`) and a Revisable-harness entry (`:55-59`), but **no**
  entry annotating the S55a-fix enforcement-masking finding (host-port-binding contract red
  from stale `.pyc`) or its affected window. The finding is recorded elsewhere —
  `charter/methodology.md:593` (v6) and `Makefile:106-109` — but not as an affected-window
  annotation in the audit-inputs document where this check expected it. Whether
  phase-2-audit-inputs.md is the required home is a judgment call.

---

## Check 5 — Close-claims verification (D154's nine criteria)

D154 (`charter/decisions.md:231`) and the epic close verdict
(`charter/packages/p15-epic.md:71-78`) assert all nine met, two with dogfooding-gated
qualifications.

### F5.1 — Criterion 1 (three implementers register) — VERIFIED-CONSISTENT
- See F2.5: three production registrations (`apps/api/main.py:472,527,531`). (Test-set fourth =
  synthetic, F2.5 candidate.)

### F5.2 — Criterion 2 (ChannelResolver operational; static-config adapter) — VERIFIED-CONSISTENT
- As-built: `contexts/messaging/application/ports/channel_resolver.py` (Protocol) +
  `contexts/messaging/adapters/channel_resolver/static_config_channel_resolver_adapter.py:31`
  (`StaticConfigChannelResolverAdapter`).

### F5.3 — Criterion 3 (HTTP trigger endpoint; BROADCAST_INITIATED chains) — VERIFIED-CONSISTENT
- As-built: `apps/api/routers/triggers.py` (`POST /api/v1/internal/triggers/fire`);
  BROADCAST_INITIATED event module `contexts/messaging/application/audit_events.py:62`
  (`ACTION_BROADCAST_INITIATED = "messaging.broadcast.initiated"`), `:252-309`
  (`draft_broadcast_initiated_event`). fired_triggers idempotency via Alembic `0025`. Live
  chain correctness is smoke-attested (`docs/smoke/p15_s54_daily_briefing.md`,
  `docs/smoke/p15_s57_threshold_briefing.md`; commit `d52f6fe` records the S57 smoke executed).

### F5.4 — Criterion 4 (five-way meta-classifier; five ConversationFlow implementers; both gold sets) — VERIFIED-CONSISTENT
- As-built: `CellIdentifier` carries MANUAL_ENTRY / AUDIT_CONVERSATION / MIRROR_CONVERSATION /
  CALENDAR_CONVERSATION / EMAIL_CONVERSATION (+ DISPATCH_CLARIFICATION) —
  `contexts/messaging/adapters/rule_based_meta_classifier.py:83-131`. Five ConversationFlow
  conformance registrations: `tests/contract/conversation_flow/` —
  manual_entry, audit_conversation, mirror_conversation, calendar_conversation,
  email_conversation.

### F5.5 — Criterion 5 + 7 email entry stated as wiring-proven, not volume-proven — VERIFIED-CONSISTENT
- Charter: epic close verdict (`charter/packages/p15-epic.md:75`) and D154
  (`charter/decisions.md:231`) state in plain language: "met by the email wiring-proof against
  tenant_a's n=1 mailbox … recorded as **wiring-proven, not volume-proven**," with the volume
  path/measurement/incremental/email-thresholds/meeting-moved mapped to the dogfooding gate.
  Not rounded up to green.

### F5.6 — Criterion 6 (ArtefactCitation extended to four types) — VERIFIED-CONSISTENT
- See F2.6 (enforced four-type set). (Docstring staleness is the candidate sub-note.)

### F5.7 — No criterion claimed met that the evidence does not carry — VERIFIED-CONSISTENT (within this pass's reach)
- Criteria 1–7 each have corroborating as-built evidence above. Criterion 8 (charter
  touch-points) is the surface where this pack found the most residue (Checks 3 and 4): the
  touch-points were updated but several living surfaces retain pre-correction shapes — see the
  CONFIRMED-DRIFT findings. Criterion 9 (dogfooding-*ready* substrate, not a completed week) is
  consistent with the qualification stated at `charter/packages/p15-epic.md:76`. The
  representative-volume email path is a known, documented gap, not a hidden one.

---

## Check 6 — Tests, contracts, enforcement (from clean bytecode)

### F6.1 — Import-linter: 41/41 contracts kept — VERIFIED-CONSISTENT
- Reproduced: `uv run lint-imports` → "Contracts: 41 kept, 0 broken" (includes
  `Email-conversation layers`, `Threshold-briefing layers`, and the cross-context independence
  + vendor-confinement contracts). Matches the S57 session-log claim "import-linter 41/41 kept"
  (`log/sessions.md:2754,2777`).

### F6.2 — Unit + contract suite green from clean bytecode — VERIFIED-CONSISTENT
- Reproduced: `uv run pytest -p no:cacheprovider tests/unit tests/contract` → **exit 0** (no
  failures). The exact passed/skipped tally line could not be captured in this non-TTY
  environment (a pytest-on-Python-3.14 quirk suppresses the final summary line under
  redirection/pipe), but exit 0 confirms zero failures. Session log reports **2190 passed, 12
  skipped, 0 failed** (`log/sessions.md:2754,2777`); the exit-0 result is consistent with it.

### F6.3 — Three full-tier failures are live-infra-dependent, outside unit/contract/_enforcement — VERIFIED-CONSISTENT
- Reproduced: full default tier had exactly 3 failures —
  `tests/e2e/agent/test_create_from_methodology_flow.py::…_against_live_stack`,
  `tests/integration/contexts/methodology/test_lvt_round_trip.py::…`,
  `tests/integration/contexts/tools/adapters/outbound/postgres/test_tool_repository.py::…`.
  All in `tests/e2e/` and `tests/integration/` (one literally named `…_against_live_stack`),
  none in `tests/unit`, `tests/contract`, or `tests/_enforcement`. Matches the session log's
  "three known docker-dependent environmental failures carry forward, not in scope, not
  introduced" (`log/sessions.md:2777`).
- Method note: the initial full-suite run was piped through `tail`, which masked pytest's
  non-zero exit (pipe exit = tail's 0). Re-run isolating `tests/unit tests/contract` returned
  exit 0 directly. No green-via-skip/stub was found in the unit/contract set; the cancelled_at
  trap's sibling risk (a green stub a runtime path falsifies) is addressed in code by the
  live-smoke-driven fixes at `rule_match.py`/`evaluation.py` (F4.5).

---

## Check 7 — Schema versus migrations

### F7.1 — Calendar substrate = Alembic 0026; Email substrate = Alembic 0027; fired_triggers = 0025 — VERIFIED-CONSISTENT
- As-built migrations: `alembic/tenant/versions/2026_05_28_0026_calendar_substrate.py`,
  `2026_06_03_0027_email_substrate.py`, `2026_05_28_0025_fired_triggers.py` — matching the
  numbers the D-entries/schema cite (D147/D148/D151; `charter/schema.md:1402` cites
  `0025_fired_triggers`).

### F7.2 — Schema-documented calendar/email tables exist in the migrations (spot-check) — VERIFIED-CONSISTENT
- Calendar: `charter/schema.md:1421` "## Calendar context tables (per-tenant)"; `meetings`
  table with `google_event_id` (`:1456`), UNIQUE `(tenant_id, google_event_id)` (`:1475`),
  dormant `sync_token` — present in migration `0026` (`create_table` at `:44,:73`; columns
  `google_event_id` `:78`, `sync_token` `:52`, five `enc_*` columns `:90-94`, `start_at/end_at`
  `:80-81`).
- Email: `charter/schema.md:1501` "## Email context tables (per-tenant)"; `email_chunks` with
  `vector(768)` + HNSW (`:1548-1559`); dormant `history_id` — present in migration `0027`
  (`_tables.py:35-36,56`).
- Scope note: this is a spot-check on the load-bearing P15 tables/columns (meetings,
  email/email_chunks, fired_triggers, the dormant-anchor columns), not an exhaustive
  column-by-column reconciliation of every column in both directions.

---

## Check 8 — Principle contradictions

### F8.1 — "Audit trail as source of truth / every state change emits an audit event" vs sync_calendar/sync_email emitting no audit events — CONFIRMED-DRIFT
- Principle: `charter/principles.md:125` (Phase 2 principles, "Audit trail as source of truth")
  — "**Every state change emits an audit event before persistence completes.** … The audit
  trail is queryable, immutable, and hash-chained." Stated as a charter-grade discipline that
  "binds every subsequent surface design decision."
- As-built practice: `sync_calendar` upserts/tombstones the meetings store and emits **no**
  audit events (F2.4); D153 (`charter/decisions.md:229`) makes this explicit: "`sync_calendar`
  … emits **no** audit events." Email sync (`sync_email`) is symmetric. So calendar/email
  substrate state changes are not in the chain.
- Acknowledged-but-unqualified: the gap is forwarded as a deferred-decisions entry
  (`charter/deferred-decisions.md:801-807`, CDC/provenance) — but the principle text at
  `principles.md:125` stands unqualified. The contradiction between the standing principle and
  the as-built substrate is present. (Disposition — whether the deferral makes this acceptable
  — is out of scope here.)

### F8.2 — "Originals never erased" vs calendar tombstone purging meeting content for uncited meetings — CANDIDATE-DRIFT
- Principle: `charter/principles.md:129-133` ("Originals never erased") — persisted artefacts
  "are never deleted … user-initiated removal marks artefacts as archived but does not erase
  them."
- As-built practice: the calendar tombstone NULLs encrypted content + embedding on cancellation
  (`charter/deferred-decisions.md:813-815`: "`tombstone_meeting` NULLs the encrypted content
  (title/description/location) and the embedding"). D148 (`charter/decisions.md:219`) reconciles
  this — "consistent with originals-never-erased because the *original* is the audit snapshot;
  the live row is explicitly a mutable cache." But the audit snapshot exists only for **cited**
  meetings (`meeting_citation` emitted on a user turn). For an **uncited** meeting that is
  cancelled, content is purged with no snapshot retained — so D148's "the original is the audit
  snapshot" reconciliation does not cover that case. Whether this is a genuine contradiction or
  an accepted cache-eviction boundary needs judgment (the deferred entry at `:809-817` is the
  related forward-tracking surface).

---

## Probes that returned "none found" (hunt visible)

- `matched_audit_event_id` in code: present **only** as stale docstring/test residue
  (`shared_kernel/broadcast_flow.py:70`, `tests/unit/shared_kernel/test_broadcast_flow.py:48`)
  — never in the active idempotency derivation path (F2.1/F4.6/F4.9). Searched
  `contexts apps shared_kernel tests charter`.
- `meeting.moved|moved`, `incremental`, `imap|provider.agnostic`, `D152` in
  `charter/deferred-decisions.md`: hunted via grep; absences recorded as F3.2/F3.3/F3.4/F3.9.
- Green-via-skip/stub in unit+contract: none surfaced; the cancelled_at-trap sibling risk is
  closed in code by the live-smoke fixes (F4.5).

---

## Tag tally (authoritative)

| Tag | Count |
|-----|-------|
| CONFIRMED-DRIFT | 14 |
| CANDIDATE-DRIFT | 7 |
| VERIFIED-CONSISTENT | 25 |
| **Total** | **46** |

- **CONFIRMED-DRIFT (14):** F1.4, F2.2, F3.1, F3.2, F3.3, F3.4, F3.7, F3.8, F3.9, F4.6, F4.7,
  F4.8, F4.10, F8.1.
- **CANDIDATE-DRIFT (7):** F1.3, F2.5, F2.6, F3.10, F4.9, F4.11, F8.2.
- **VERIFIED-CONSISTENT (25):** F1.1, F1.2, F2.1, F2.3, F2.4, F2.7, F3.5, F3.6, F4.1, F4.2,
  F4.3, F4.4, F4.5, F5.1, F5.2, F5.3, F5.4, F5.5, F5.6, F5.7, F6.1, F6.2, F6.3, F7.1, F7.2.

The CONFIRMED-DRIFT set clusters: (a) the `matched_audit_event_id` pre-correction shape
surviving across four living surfaces after D153 moved to derived-state identity (F3.8, F4.6,
F4.7, F4.8 — plus the F4.9 test fixture and the F2.2 idempotency.py docstring/fallback); (b) the
deferred-decisions register missing three named P15 deferrals, a sibling-asymmetric closure, and
a TOC that omits both P15 sections (F3.1, F3.2, F3.3, F3.4, F3.7, F3.9); (c) two single-surface
stale-residue items (F4.10 latency floor, F1.4 cross-reference); (d) one standing
principle-vs-practice contradiction (F8.1).
