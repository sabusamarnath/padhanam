# Software engineering principles — baseline assessment (Phase 2-A, P13)

A code-altitude assessment of the Phase 2-A codebase against seven software
engineering principles: KISS, DRY, the five SOLID letters individually, YAGNI,
and Tell Don't Ask. Conducted at the pre-S45 hygiene boundary, 2026-05-22,
against the working tree at S44b close (commit `59bf205`).

## What this document is and is not

This is an **evidence document**, not a verdict. Each finding cites file paths
and line numbers; absent evidence is cited as such. Disposition of findings into
charter additions, hygiene items, methodology promotions, or deferred-decisions
entries happens at the subsequent disposition conversation, not here.

The seven principles assessed are **not** in `charter/principles.md`. They sit at
audit altitude as measurement axes only. The assessment respects that
distinction: it does not propose elevating any of them to charter-grade
principles. Several overlap existing methodology-document discipline (the file
topology budget relates to SRP; the substrate-application boundary check and
pre-write reconciliation relate to KISS and DRY at the discipline altitude; the
consumer-port pattern at 12-plus reinforcements is a Dependency Inversion
pattern). Overlaps are cited, not duplicated.

## Scope

The brief scopes the assessment to "the Phase 2-A codebase." Phase 2-A is P13:
the `contexts/portfolio/` and `contexts/intake/` bounded contexts, the
`shared_kernel/` additions (`actor_context.py`, `authorisation.py`,
`revisable.py`, `actor_reference.py`), and the `apps/api/` and `apps/cli/`
write-and-read transport surfaces for those contexts. Where the file size
distribution or import analysis surfaces a Phase 1 file (the agent context, the
composition layer), it is assessed and flagged explicitly as Phase 1 vintage so
the disposition session can scope correctly.

## Method and tools

Static analysis tooling available in the environment was verified at pre-write
reconciliation:

- **`import-linter`** — installed (`.venv/bin/lint-imports`). Used directly. 29
  contracts, 29 kept, 0 broken.
- **`pytest`** — installed. Not re-run for this assessment (S44b reported 1746
  passing).
- **AST enforcement tests** — 9 files at `tests/_enforcement/`.
- **`radon`, `mypy`, `ruff`** — **not installed**. No operator approval was
  sought to install new tooling per the brief. The cyclomatic-complexity
  dimension was instead measured with a throwaway stdlib-`ast` sampler
  (decision-point count per function); the substitute covers the CC dimension
  but not type-coverage (`mypy`) or lint-surface (`ruff`) measurement. Those two
  remain measurement gaps, named here so a future principle assessment can close
  them.

Quantitative metrics are reported where tooling supports them; qualitative
findings carry specific code evidence where quantitative measurement is not
feasible. The assessment is honest about which dimension each finding rests on.

## Severity taxonomy

Per the brief, every finding carries one of three severities:

- **Load-bearing** — threatens the substrate's structural integrity.
- **Material** — warrants disposition (charter touch, hygiene item, methodology
  promotion, deferred-decisions entry) but does not threaten structural
  integrity.
- **Marginal** — worth noting, below the disposition threshold.

Finding IDs (`K1`, `D1`, `SRP1`, …) are referenced from the synthesis at the
document tail.

---

# Section 1: KISS

**Methodology.** KISS is assessed across four dimensions. First, file size
distribution as a proxy for code-altitude complexity (extending the file
topology budget discipline). Second, abstraction layer counts for a sample write
path and read path. Third, decision-point density per function (cyclomatic
complexity via the stdlib-`ast` sampler). Fourth, the
substrate-depth-overrides-YAGNI cumulative pattern across the Phase 2-A D-entries
(this dimension produces KISS-relevant findings independently of Section 4).

## Quantitative metrics

**File size distribution** (441 non-test code files across `contexts/`, `apps/`,
`shared_kernel/`, `padhanam/`):

| Bracket | Files |
|---|---|
| < 100 lines | 289 |
| 100–199 | 87 |
| 200–399 | 41 |
| 400–599 | 15 |
| 600–799 | 4 |
| 800+ | 5 |

87% of files are under 200 lines. The 24 files at 400+ lines are addressed under
SRP (Section 3.1).

**Cyclomatic complexity** (stdlib-`ast` sampler, 1284 functions across
`contexts/` + `apps/` + `shared_kernel/` + `padhanam/`):

| CC bracket | Functions |
|---|---|
| 1–5 | 1178 (92%) |
| 6–10 | 77 |
| 11–15 | 21 |
| 16–20 | 5 |
| 21+ | 3 |

The three CC-21+ functions are all vendor-integration adapter code:
`contexts/inference/adapters/outbound/litellm/adapter.py:214` `stream_complete`
(CC 35), `contexts/agent/adapters/outbound/agent_loop_executor.py:121` `execute`
(CC 25), `contexts/ingestion/adapters/outbound/extraction/litellm_extractor.py:265`
`_build_domain_objects` (CC 21). None are Phase 2-A.

**Phase 2-A code in isolation** (`contexts/portfolio/` + `contexts/intake/`, 87
functions): 82 at CC 1–5, 4 at CC 6–10, exactly one above CC 10 —
`contexts/portfolio/adapters/outbound/postgres/portfolio_reader.py:177`
`list_cases` at CC 11. `shared_kernel/` peaks at CC 6
(`actor_context.py:52` `__post_init__`).

**Abstraction layer counts.** The Phase 2-A write path for
`POST /api/v1/portfolio/cases` traverses, in order: FastAPI route
([portfolio.py:218](../apps/api/routers/portfolio.py#L218)) → `record_intake_and_create_case`
orchestration → `record_intake` use case → `IntakeRepository` port →
`IntakeRepositoryAdapter` wiring → `PostgresIntakeRepository` → SQLAlchemy →
Postgres; and in parallel `PortfolioWriter` port → `PortfolioWriterAdapter`
wiring → `create_case` use case → `PortfolioRepository` port →
`PostgresPortfolioRepository` → SQLAlchemy → Postgres; with an `AuditPort` hop on
each of the two writes. A single POST produces four rows (one IntakeRecord, one
Case, two audit events) across two transactions through roughly ten named
application/port/adapter hops. The read path (`GET /api/v1/portfolio/cases`) is
shallower — route → query parser → `list_cases` use case → `PortfolioReader`
port → `PortfolioReaderAdapter` wiring → `PostgresPortfolioReader` → SQLAlchemy —
about six hops.

## Findings

### K1 — Phase 2-A code-altitude simplicity is strong (positive)

The Phase 2-A substrate is, by every quantitative measure, simple. The portfolio
and intake contexts hold no file over 400 lines (largest:
`portfolio/adapters/outbound/postgres/portfolio_reader.py` at 303); 82 of 87
functions sit at CC ≤ 5; domain entities are 64–123 line frozen dataclasses with
`__post_init__` validation and nothing else. Use cases are one-file-per-use-case
(`create_case.py` 71 lines, `create_data_point.py` 100, `revise_data_point.py`
86). This is the file topology budget discipline producing the result it was
designed to produce. **Severity: positive finding, no action.**

### K2 — Write-path layer depth is high but each layer is charter-mandated

The ten-hop write path is deep for an operation that inserts four rows. Each
layer earns its place against a binding commitment: the hexagonal layering
(route → use case → port → adapter) per D16; the second use-case/port/adapter
triple because the orchestration drives two bounded contexts and cross-context
application-to-application imports are forbidden by the import-linter
"Cross-context: application layers are independent" contract (D16/D17/D28),
forcing the consumer-port-plus-wiring-adapter indirection (D127 alternative (e));
the intake write itself because D128 commits intake-canonical entry. No layer is
gratuitous. The KISS observation is honest rather than critical: the architecture
pays a real, conscious layer-count cost for cross-context independence and
audit-trail canonicity, and the deepest single contributor is the consumer-port
indirection that the import-linter contract requires. **Severity: marginal
(observation; no action — the depth is the cost of charter-grade commitments).**

### K3 — `actor.tenant_context` extraction verbosity reads as boundary, not noise

D126 / S44a Item 1 acknowledged a trade-off: every use case extracts
`tenant_context = actor.tenant_context` before adapter calls because ActorContext
composes rather than subsumes TenantContext. The brief asks whether this has
drifted into invisible noise. Code-altitude reading: it has not. The extraction
appears exactly once per use case (`record_intake.py:42`, `create_case.py:48`,
`create_data_point.py:59`, `revise_data_point.py:61`) and at each site the next
line derives `ActorReference(user_id=actor.actor_id)` — the two lines together
read as a deliberate "unpack the request envelope into the narrow value objects
the adapter and the audit draft each need." The verbosity is structural boundary
visibility, as S44a claimed. (The repetition itself is treated as a DRY
observation — see D6.) **Severity: marginal (no action; S44a trade-off holds at
the larger S44b surface).**

### K4 — Audit-event drafts compute a placeholder hash that is always discarded

`draft_intake_record` ([intake/application/audit_events.py:47](../contexts/intake/application/audit_events.py#L47))
and the portfolio `_draft` helper
([portfolio/application/audit_events.py:55](../contexts/portfolio/application/audit_events.py#L55))
both call `compute_event_hash(...)` with `previous_event_hash=GENESIS_HASH` to
produce a `draft_hash`, then construct the `AuditEvent` with
`this_event_hash=draft_hash`. Both docstrings state the Postgres audit adapter
recomputes `previous_event_hash` and `this_event_hash` inside its locking
transaction (D37) — so the computed `draft_hash` is known-throwaway at the moment
it is computed. The draft computes a value it knows is wrong because `AuditEvent`
requires `this_event_hash` as a non-optional field at construction. The honest
shape would be a separate draft type without the hash, or a lazily-computed
hash. This is a small KISS smell driven by the `AuditEvent` constructor's
required-field shape. **Severity: marginal.**

### K5 — Substrate-depth-overrides-YAGNI cumulative pattern (cross-reference)

The Phase 2-A D-entries D126, D127, D128 are all Kano must-have and each carries
explicit cost-now-versus-cost-later or cost-of-pivot reasoning under Decision 7's
substrate-depth framing. Code-altitude reading finds the substrate-depth
arguments **load-bearing, not marginal overrides**: D127's intake substrate is
the literal foundation P14's calendar-read and email-read paths land on; D128's
canonical→optional relaxation argument is sound; D126's authorisation decorator
is a genuine single grep-able surface. The KISS-relevant residue is that the
depth produces forward-compat affordances that are inert at Phase 2-A — assessed
in full under YAGNI (Y1, Y2, Y3). The KISS verdict on the override pattern: the
overrides were not marginal; the depth bought real structural simplification of
future work. **Severity: marginal (cross-referenced to Section 4).**

---

# Section 2: DRY

**Methodology.** DRY is assessed across three dimensions. First, cross-file
pattern duplication identified by structural reading and `diff`. Second, repeated
constants and identifiers. Third, the three intake orchestrations specifically,
compared line-by-line.

## Quantitative metrics

- Cursor codec: 7 near-identical files across 7 contexts (118–172 lines each).
- Pagination value objects (`*ListCursor`, `MalformedCursorError`,
  `PAGE_SIZE_CEILING`): duplicated per context.
- Audit-event draft helper: reimplemented per context; portfolio factored a
  `_draft` helper, intake re-inlined the equivalent boilerplate.
- Per-tenant-resolving wiring adapter shape: 12 inner `_session_factory_for_tenant`
  closures in `apps/api/_agent_runtime_wiring.py` alone.
- Route-level tenant-mismatch rewrap block: 10 occurrences across three routers.
- Three intake orchestrations: ~7-line shared prologue, structurally identical.

## Findings

### D1 — Cursor codec duplicated across seven contexts, with divergent evolution

`diff contexts/intake/application/cursor.py contexts/portfolio/application/cursor.py`
returns only docstring and identifier substitutions (`IntakeListCursor` ↔
`CaseListCursor`, `encode_intake_cursor` ↔ `encode_case_cursor`) — the
~110 lines of base64/JSON encode-decode logic, the `MalformedCursorError`
handling, and the schema validation are identical. The pattern now exists in
**seven** files: `run_history` (123 lines), `audit` (124), `ingestion` (124),
`retrieval_evaluation` (156), `optimization` (172), and the two Phase 2-A
additions `portfolio` (118) and `intake` (118).

P12 audit Finding B5 already observed this for four contexts and dispositioned it
"non-action … structural consistency is the success criterion," noting the
singular/plural naming inconsistency as "hygiene noise." Phase 2-A added two more
copies. Two things sharpen the finding beyond P12's snapshot: the count has grown
from 4 to 7, vastly past the methodology's own three-instance structural-
promotion threshold; and the copies have **diverged** — the Phase 2-A
`portfolio`/`intake` codecs refactored `decode` into a lower-complexity `_decode`
plus `_require_keys` helper (CC 6) while the Phase 1 `run_history`/`audit`/
`ingestion` codecs retain a CC-15 monolithic `decode`. The duplication is no
longer "structurally consistent" — it is copy-and-independently-improve, which is
the worse failure mode because fixes do not propagate. A generic base64-JSON
cursor codec parameterised over the cursor dataclass is the textbook resolution.
**Severity: material.**

### D2 — Pagination value objects duplicated per context (same cluster as D1)

`contexts/portfolio/domain/query_filters.py` and
`contexts/intake/domain/query_filters.py` each independently define
`PAGE_SIZE_CEILING = 50`, a `MalformedCursorError(Exception)`, and a
`*ListCursor` frozen dataclass over `(created_at, id, page_size)` with a
byte-identical `1 <= page_size <= PAGE_SIZE_CEILING` `__post_init__` check
([portfolio query_filters.py:58-63](../contexts/portfolio/domain/query_filters.py#L58-L63)
≈ [intake query_filters.py:51-56](../contexts/intake/domain/query_filters.py#L51-L56)).
The intake docstring states outright: "Mirrors the portfolio query-filter
pattern." The pagination *machinery* — cursor value object, error type, ceiling
constant — is duplicated alongside the codec of D1. This is one DRY cluster:
the whole pagination apparatus is reimplemented per context. **Severity: material
(disposition jointly with D1).**

### D3 — Audit-event draft boilerplate: portfolio factored it, intake re-inlined it

`contexts/portfolio/application/audit_events.py` extracts a private `_draft(...)`
helper ([lines 43-81](../contexts/portfolio/application/audit_events.py#L43-L81))
that the three `draft_*` functions delegate to — good DRY within the context.
`contexts/intake/application/audit_events.py`, written one session later (S44b),
**inlines the full `compute_event_hash(...)` + `AuditEvent(...)` construction**
([lines 47-73](../contexts/intake/application/audit_events.py#L47-L73)) rather
than mirroring the `_draft` helper. Two sibling contexts in the same package,
one session apart, made opposite factoring choices. Intake's single event type
makes a one-off inline defensible at one instance — but the boilerplate it
inlined is the same shape that recurs in `portfolio`, `optimization`,
`retrieval_evaluation`, and `run_history` audit-event modules. Note also a
within-function duplication present in every variant: the 11-argument list is
written twice per draft — once into `compute_event_hash`, once into
`AuditEvent` — because the two are constructed separately (see K4).
**Severity: material.**

### D4 — Per-tenant-resolving wiring-adapter boilerplate repeated ~15 times

The "build a fresh repository bound to the request tenant via a session factory
plus a trivial resolver closure" shape recurs throughout the composition layer.
`apps/api/_agent_runtime_wiring.py` contains 12 inner
`async def _session_factory_for_tenant` closures — one per `build_*` function.
`apps/api/_intake_wiring.py` repeats the four-line resolver shape three times
(`IntakeRepositoryAdapter._build`, `PortfolioWriterAdapter._repo`,
`PortfolioWriterAdapter._reader` — [lines 102-113, 163-187](../apps/api/_intake_wiring.py#L102-L113)).
`_intake_wiring.py` *did* factor a `_session_factory_for_tenant_builder`
([lines 245-262](../apps/api/_intake_wiring.py#L245-L262)) — the newer file
improved on the older one — but the older 912-line `_agent_runtime_wiring.py`
still inlines the closure 12 times. The per-request-tenant-routing adapter is a
genuine shared-primitive candidate. **Severity: material.**

### D5 — The three intake orchestrations share an identical prologue

`record_intake_and_create_case`, `record_intake_and_create_data_point`, and
`record_intake_and_revise_data_point` each contain the same `record_intake(...)`
invocation block — five identical lines
(`repository=intake_repository, audit_port=audit_port, actor=actor,
intake_source=IntakeSource.MANUAL_ENTRY, payload=payload`) — followed by a single
differing `portfolio_writer.<method>(...)` call. Each file is ~25 lines, of which
the shared prologue plus the dual-decorator idiom is ~12. D127 alternative (d)
consciously reasoned the three constitute "one architectural concern, not three"
and kept them unfactored. The duplication is real and sits exactly at the
methodology's three-instance promotion threshold; D127(d)'s reasoning addressed
*whether they form a new bounded context*, not *whether the shared prologue
should be a primitive*. A minor corroborating detail: `record_intake_and_revise_data_point.py`
places its `from uuid import UUID` / `from typing import Any` imports after the
`shared_kernel` imports (lines 34-35) while `record_intake_and_create_data_point.py`
places them at the top (lines 27-28) — evidence of hand-copying.
**Severity: marginal (D127(d) consciously left them; the prologue, not the
file count, is the residual question).**

### D6 — Use-case ActorContext-unpack prologue repeated ~7 times

`tenant_context = actor.tenant_context` followed by
`authored_by = ActorReference(user_id=actor.actor_id)` appears verbatim in
`record_intake`, `create_case`, `create_data_point`, and `revise_data_point`,
and the `tenant_context` half appears again in `PortfolioWriterAdapter`'s three
methods. S44a Item 1 documented this as deliberate boundary visibility (see K3).
The repetition is by-design per that reasoning; a helper (`actor.unpack()` or an
`ActorContext.as_actor_reference()` method) would trade the visible boundary for
brevity. **Severity: marginal (by-design per S44a; cross-referenced to T2).**

### D7 — Route-level tenant-mismatch rewrap block repeated 10 times via message-sniffing

Every Phase 2-A write and read route wraps its use-case call in:

```python
except ValueError as exc:
    if "tenant" in str(exc):
        raise BoundTenantIdMismatchError(exc) from exc
    raise
```

This block appears 10 times: `apps/api/routers/portfolio.py` (5),
`apps/api/routers/intake.py` (3), `apps/api/routers/run_history.py` (2). It is
both a DRY violation (the 3-line block is copied 10×) and a robustness smell: the
control-flow decision is keyed on a substring match against an exception
*message* — if an adapter's `ValueError` text ever omits the literal word
"tenant," the route silently mis-routes the error. The honest shape is a typed
exception raised by the bound-tenant defence in the adapter, caught by type at
the route. `run_history.py` is Phase 1 vintage; Phase 2-A inherited and extended
the pattern (8 of the 10 occurrences are portfolio/intake). **Severity:
material.**

### D8 — Domain `jurisdiction` non-empty validation repeated across value objects

`if not self.jurisdiction.strip(): raise ValueError(...)` appears in the
`__post_init__` of `IntakeRecord`, `DataPoint`, `Case`, and `Assertion`, with
near-identical non-empty-string checks also in `TenantContext` and
`ActorReference`. Six value objects across two contexts plus shared_kernel repeat
the same one-or-two-line validation idiom. A shared field-validation helper is a
reasonable extraction; the cost of leaving it is low (the check is two lines and
self-evident). **Severity: marginal.**

### DRY positives

- **Permission strings are single-sourced.** The five portfolio and three intake
  permission strings are named once as module constants in
  `shared_kernel/authorisation.py` and referenced by both the decorator
  applications and the `_ROLE_AUTHORISATIONS` lookup. The module comment
  (lines 41-45) explicitly names the parallel-drafting fragility this removes.
  The S44a brief flagged an "authorisation-keys-must-match" concern; the code
  dissolved it structurally rather than managing it.
- **`DataPointWriteResult`** serves both the create-data-point and
  revise-data-point orchestrations — one DTO, two uses, deliberately
  ([portfolio_writer.py:51-67](../contexts/intake/application/ports/portfolio_writer.py#L51-L67)).
- **Alembic 0017 vs 0018** share little structural code because they are
  different migration kinds (table creation vs column addition) — the migrations
  DRY watch-point came up clean.

---

# Section 3: SOLID

## 3.1 Single Responsibility (SRP)

**Methodology.** File-altitude SRP via the size distribution from Section 1;
class/module-altitude SRP via the responsibilities visible in each file's public
surface.

**Quantitative metrics.** 15 files at 400–599 lines, 4 at 600–799, 5 at 800+.
The five files over 800 lines:

| File | Lines | Vintage |
|---|---|---|
| `apps/cli/_cross_context.py` | 1704 | P5–P11 (accreted) |
| `contexts/agent/application/use_cases.py` | 1054 | P7–P8 |
| `apps/api/_agent_runtime_wiring.py` | 912 | P9–P13 (accreted) |
| `apps/cli/_agent.py` | 901 | P7–P8 |
| `apps/api/_errors.py` | 828 | P9–P13 (accreted) |

### SRP1 — `apps/api/_errors.py` at 828 lines; grew under a standing split-flag

`_errors.py` holds the `ErrorResponse` model, eight exception classes, ~25
exception handlers, and seven `register_*_error_handlers` functions for seven
router families (run_history, audit, ingestion, retrieval_evaluation,
optimization, portfolio, intake). The `charter/phase-2-audit-inputs.md`
close-hygiene list records it at **729 lines** as surfaced at S44a. It now stands
at **828** — it grew ~99 lines at S44b when the portfolio and intake error
handlers landed in it ([lines 670-797](../apps/api/_errors.py#L670)). This is
honest within the file's own per-router-family convention — intake and portfolio
*are* router families — and "start simple, refactor at the threshold" defends not
pre-emptively splitting. But the data point is sharp: a file flagged for splitting
at S44a grew by a session's worth of handlers at S44b. The file-topology-budget
discipline redirects genuinely-new *categories* of code (S44a sent the
auth-cross-cutting `AuthorisationDenied` handler to `_auth_errors.py`) but does
not stop a flagged file accreting more of its *existing* category. The split is
already on the Phase 2-A close hygiene list. **Severity: material.**

### SRP2 — `apps/api/_agent_runtime_wiring.py` at 912 lines; name is now a misnomer

The file holds ~15 `build_*` functions and several adapter classes
(`TenantRoutingRetrievalClient`, `PortfolioReaderAdapter`,
`TenantRoutingSourceRepository`, `HttpRetrievalRunnerPort`) wiring the agent
runtime, run-history, portfolio, ingestion, audit, gold-set, evaluation-run,
optimization-run, recommendation, and retrieval surfaces. It is the API
composition root for nearly every context; the name `_agent_runtime_wiring`
describes one of ten responsibilities. On the standing Phase 2-A close hygiene
list. S44b informally began the split (intake wiring went to a new
`_intake_wiring.py`) but the 912-line file itself was not divided.
**Severity: material.**

### SRP3 — `apps/cli/_cross_context.py` at 1704 lines — the largest file; un-flagged

The single largest file in the codebase holds roughly 14 cross-context adapter
classes (`MethodologyLookupAdapter`, `RoleLookupAdapter`, `SourceLookupAdapter`,
`AgentRetrievalClientAdapter`, `MethodologyOverridesLookupAdapter`,
`ToolDefinitionsLookupAdapter`, `ToolInvokerAdapter`, `RunHistoryWriterAdapter`,
`RunHistoryReaderAdapter`, `AuditEventReaderAdapter`, `GoldSetRepositoryAdapter`,
`GoldSetReaderAdapter`, `EvaluationRunRepositoryAdapter`,
`EvaluationRunReaderAdapter`, …). It is the CLI analogue of
`_agent_runtime_wiring.py` and is nearly double the size of any file the brief's
SRP watch-points named. It appears on **no hygiene list** and in no charter
document. The brief's SRP watch-points (`_errors.py`, `_agent_runtime_wiring.py`)
were drawn from session-log findings; `_cross_context.py` never surfaced because
no S43/S43b/S44 session touched it heavily. **Severity: material (and the most
surprising finding of the assessment — see synthesis).**

### SRP4 — `contexts/agent/application/use_cases.py` at 1054 lines (Phase 1)

A single application-layer file holds eight use cases plus six private helpers;
the `invoke_agent` use case alone spans ~216 lines (lines 714-930, CC 16). This
is P7–P8 vintage. It is named here for completeness because it is the
second-largest file and the brief's SRP methodology says to assess "any other
files over 400 lines." It is **out of Phase 2-A scope** and flagged as such. It
carries a positive corollary: the Phase 2-A contexts (`portfolio`, `intake`)
adopted one-file-per-use-case (`create_case.py`, `create_data_point.py`,
`record_intake.py`, …) — the better SRP shape — so the monolithic-`use_cases.py`
pattern of `contexts/agent/` and `contexts/methodology/` (578 lines) is a Phase 1
shape the Phase 2-A contexts have already evolved past. **Severity: material as
Phase 1 debt; out of Phase 2-A scope; the Phase 2-A evolution is a positive.**

### SRP positives

The Phase 2-A *context* code is SRP-clean. Domain entities are single-purpose
frozen dataclasses (Case 64 lines, Assertion 67, IntakeRecord 96, DataPoint 123).
Use cases are one file each, 37–100 lines. Audit-event drafting, cursor codec,
and query filters each occupy their own module. The SRP debt is concentrated
entirely in the **`apps/` composition layer** — none of it is in the Phase 2-A
domain or application layers. This is a clean structural separation: the
contexts are well-factored, the composition roots accrete.

## 3.2 Open-Closed (OCP)

**Methodology.** OCP assessed via extension-point identification: for each
natural extension axis, does adding a variant require modifying existing code or
only adding new code?

**Quantitative metrics.** Extension points identified: 5 (IntakeSource enum,
IntakePayload alias, CaseType/CaseStatus/DataPointType/AssertionType enums,
ActorContext role surface, `authorisations_for_roles` role union). Would-require-
modification points for currently-deferred features: 0 surfaced.

### Findings

OCP is the principle the Phase 2-A codebase honours most cleanly; the assessment
surfaces **no OCP violation**.

- **IntakeSource** ([intake_record.py:31](../contexts/intake/domain/intake_record.py#L31))
  is a `str`-Enum with one member; CALENDAR_READ and EMAIL_READ are added by
  appending members (P14). No existing consumer's logic branches on the enum
  exhaustively, so a new member does not force a modification.
- **IntakePayload** is a one-member type alias
  ([intake_record.py:66](../contexts/intake/domain/intake_record.py#L66))
  designed to widen to a `Union` — a single-line edit — when P14 lands a second
  payload variant. The domain comment states this explicitly.
- **`authorisations_for_roles`** ([authorisation.py:76](../shared_kernel/authorisation.py#L76))
  resolves a *union* over a role set, so the role-hierarchy deferred-decisions
  feature (a second role) is a pure extension of the `_ROLE_AUTHORISATIONS` dict
  with no change to the resolver, the decorator, or any call site. D126 reasoned
  this; the code delivers it.
- **ActorContext** carries `actor_id` as a `str`, supporting the deferred
  Principal-polymorphic / machine-actor shape as a pure extension.

The single marginal note: `IntakeSource.MANUAL_ENTRY` is hardcoded at four
orchestration/use-case call sites; adding a source means adding new orchestration
paths rather than modifying these — which is itself OCP-conformant. **Severity:
no findings above marginal; OCP is a positive across Phase 2-A.**

## 3.3 Liskov Substitution (LSP)

**Methodology.** LSP assessed across Protocol implementations: for each Protocol,
identify implementations and assess adherence to the declared interface.

**Quantitative metrics.** 35 Protocol definitions across `ports/` directories
plus `shared_kernel/`; one in `shared_kernel/` (`Revisable`). Phase 2-A
Protocols: `Revisable` (shared_kernel), `IntakeRepository`, `PortfolioRepository`,
`PortfolioReader`, `PortfolioWriter` (consumer port). Protocols with a
contract-test harness: **0 of the Phase 2-A Protocols** have a dedicated
`tests/contract/` harness.

### LSP1 — The Revisable Protocol is structurally unverified; the claimed harness does not exist

`tests/contract/` contains exactly two subdirectories — `http` and
`tenant_isolation`. **`tests/contract/revisable/` does not exist.** Yet three
charter surfaces assert it:

- D114: "CI-enforceable conformance via contract tests."
- D125 and the `charter/schema.md` Revisable sub-section repeat the claim.
- `charter/architecture.md:274` states verbatim: "CI-enforceable conformance via
  contract tests at `tests/contract/revisable/`."

Revisable is currently covered only by unit tests at
`tests/unit/shared_kernel/test_revisable.py`. The `@runtime_checkable` decorator
on the Protocol permits `isinstance` checks, but `@runtime_checkable` verifies
method *names* only — not signatures, not return types, not the append-only
semantics the Protocol's docstring commits ("`revise` appends rather than
overwrites; the latest revision is the entity's current state"). LSP for the
codebase's one cross-context Protocol — and the architectural primitive D114
elevates as a Phase 2-A must-have — is therefore **structurally unverified at the
CI level**. This is already tracked as a phase-2-audit-inputs close-hygiene
entry. The brief names "LSP gaps that block CI verification of major Protocols"
as a load-bearing example. **Severity: load-bearing.**

### LSP2 — `DataPoint.revise` extends the Revisable signature; the Protocol is documentation-only

`Revisable.revise` is declared `revise(self, change: AssertionChange, actor:
ActorReference) -> Revisable[RevisionT]`
([revisable.py:65](../shared_kernel/revisable.py#L65)). The one implementer,
`DataPoint.revise`, declares a **third parameter**:
`revise(self, change, actor, intake_id: UUID | None = None) -> "DataPoint"`
([data_point.py:81](../contexts/portfolio/domain/data_point.py#L81)). LSP is not
*broken* — the extra parameter is optional with a default, so any call valid
against the Protocol (`revise(change, actor)`) remains valid against `DataPoint`,
and the `-> DataPoint` return is a covariant narrowing of `-> Revisable[…]`. The
finding is subtler and is shared with YAGNI (Y3): the Protocol is **never used as
a type**. A grep for `Revisable[` across `contexts/` and `apps/` finds only the
definition and docstring mentions — no function parameter, variable, or return
type is annotated `Revisable[...]`. The actual call site,
`revise_data_point.py:68`, calls `existing.revise(AssertionChange(value=value),
authored_by, intake_id)` — three positional args, on the concrete `DataPoint`
type. The Protocol is documentation of intent; no code depends on it
polymorphically, so LSP substitutability is not exercised at all. **Severity:
marginal (LSP technically holds; the finding is the Protocol's non-use, assessed
in full under YAGNI).**

### LSP positives

The repository adapters honour their port contracts consistently. Both
`PostgresPortfolioRepository` and `PostgresIntakeRepository` carry the identical
bound-tenant defence-in-depth: a `tenant_context.tenant_id != bound_tenant_id`
check and an `entity_tenant_id != bound_tenant_id` check
([portfolio_repository.py:72,80](../contexts/portfolio/adapters/outbound/postgres/portfolio_repository.py#L72);
[intake_repository.py:93,101](../contexts/intake/adapters/outbound/postgres/intake_repository.py#L93)).
The brief's LSP watch-point — does the intake repository honour tenant-scoping
identically to the portfolio repository — is answered positively: the two
adapters enforce the contract with the same shape, and S44b added 11
tenant-isolation contract scenarios that exercise it.

## 3.4 Interface Segregation (ISP)

**Methodology.** ISP assessed via port surface sizes and per-method consumer
counts.

**Quantitative metrics.**

| Port | Methods | Consumers | Methods used per consumer |
|---|---|---|---|
| `IntakeRepository` | 3 (save, get_by_id, list_for_tenant) | `record_intake`, `get_intake`, `list_intakes` | 1 each |
| `PortfolioRepository` | 3 (save_case, save_data_point, save_assertion) | `create_case`, `create_data_point`, `revise_data_point` | 1 each |
| `PortfolioWriter` | 3 (create_case, create_data_point, revise_data_point) | 3 orchestrations | 1 each |
| `PortfolioReader` | 5 (get_case, list_cases, get_data_point, list_data_points, assertion_history) | use cases + wiring | 1–2 each |

Dead port methods (zero consumers): 0.

### ISP1 — Phase 2-A ports are aggregate-cohesion-shaped, not consumer-shaped

By the strict ISP metric, every Phase 2-A write/repository port is a candidate
fat interface: each has three methods and **no consumer uses more than one of
them**. `record_intake` calls only `save`; `get_intake` calls only `get_by_id`;
each portfolio use case calls one repository method. Strict ISP would split each
3-method port into three single-method ports.

The counter is aggregate cohesion: each port is the persistence (or write)
surface for one aggregate — the IntakeRecord, the Case. The port docstrings name
this explicitly (`IntakeRepository`: "A single port carries the intake
aggregate's write and read surfaces … the budget-table split trigger does not
fire … the read and write shapes share the IntakeRecord aggregate"). Splitting
into single-method ports would multiply the port count, multiply the wiring, and
buy nothing — each port is implemented by exactly one adapter, and Python's
structural typing means an orchestration that imports the `PortfolioWriter`
Protocol and calls one method carries zero burden from the other two. The
"fatness" cost is genuinely near-zero.

The honest reading: the metric flags the ports; the judgement is that
aggregate-cohesion ports are a defensible, deliberate, consistently-applied
counter-pattern, and the ISP-strict alternative would be ceremony. The one place
the metric would have teeth — a consumer forced to depend on a method it cannot
satisfy or must stub — does not occur. **Severity: marginal (deliberate pattern;
named so the disposition session sees the metric and the judgement together).**

A sub-note on `PortfolioReader.assertion_history`: it returns the same data as
`get_data_point(...).revision_history()`. It is not dead — it has one consumer,
`apps/api/_agent_runtime_wiring.py:420` — but it is a slightly redundant fifth
method on the read port. Marginal.

## 3.5 Dependency Inversion (DIP)

**Methodology.** DIP assessed via import-direction analysis: import-linter
contract status; vendor SDK imports per layer; adapter-implements-port placement.

**Quantitative metrics.**

- Import-linter: **29 contracts, 29 kept, 0 broken** (matches S44b's 29/29; the
  `layers-intake` contract is the Phase 2-A addition).
- Vendor SDK imports (`litellm`, `langfuse`, `neo4j`, `fastapi`, `anthropic`,
  `openai`) in `contexts/*/domain/`: **0**. In `contexts/*/application/`: **0**.
- Pydantic in `contexts/*/domain/` or `shared_kernel/`: **0**.
- `sqlalchemy` outside adapter layers: **1** (see DIP1).

### DIP positives (the dominant finding)

DIP is mechanically enforced and holding. The hexagonal layering — domain depends
on nothing, application depends on ports, adapters implement ports — is verified
at CI by 14 per-context `layers-*` contracts plus the cross-context independence,
domain-purity, and shared-kernel contracts. No vendor SDK reaches a domain or
application layer. The Phase 2-A consumer-port pattern is correctly realised:
`contexts/intake/application/ports/portfolio_writer.py` defines the
intake-context-owned `PortfolioWriter` Protocol importing nothing from
`contexts.portfolio`; `apps/api/_intake_wiring.py`'s `PortfolioWriterAdapter`
implements it by invoking `contexts.portfolio.application` use cases — the legal
seam, since `apps/` may import any context. The import-linter "Cross-context:
application layers are independent" contract did load-bearing work at S44b: it is
the contract the brief's original orchestration design violated, and the
consumer-port resolution keeps `contexts.intake.application` independent of
`contexts.portfolio.application` (verified at 29/29). The brief's
watch-point — any escaped cross-context contract violation — finds **none**.

### DIP1 — `sqlalchemy` imported at a `contexts/` application layer (Phase 1, marginal)

`contexts/tenancy/application/connection_resolution.py:43` imports
`from sqlalchemy.ext.asyncio import (...)`. This is the one place a vendor/infra
SDK reaches a `contexts/*/application/` layer. The import-linter `domain-purity`
contract forbids vendor SDKs in *domain* layers but does not police *application*
layers for SQLAlchemy, so this is not a contract escape — it is a gap in what the
contract set covers. The file is P3-vintage connection-routing plumbing
(`TenantSessionFactoryCache`); resolving per-tenant database connections is
infrastructure-adjacent by nature, and the application/domain split for
connection-routing is itself a grey area. It is **out of Phase 2-A scope** and
named only because the import scan surfaced it. **Severity: marginal (Phase 1
vintage; connection-routing plumbing; named, not pursued).**

---

# Section 4: YAGNI

**Methodology.** YAGNI assessed via the substrate-depth-classified D-entry
inventory plus forward-compat field/code-path analysis. For each substrate-depth
D-entry, identify the Phase 2-A consumer beyond tests. For each forward-compat
field, verify whether a Phase 2-A code path populates and reads it. Per the
brief, findings here are **baseline evidence for the Phase 3 close audit, not
Phase 2 violation accusations** — the Phase-2-substrate-builds-toward-Phase-3
posture is acknowledged.

**Substrate-depth-classified D-entry inventory** (verified against
`charter/decisions.md` bodies): D124–D128 are all Kano must-have. D126, D127, and
D128 carry explicit cost-now-versus-cost-later or cost-of-pivot substrate-depth
reasoning under Decision 7's framing; D124 is the base substrate and D125
inherits D114's must-have classification. The substrate-depth-with-cost-of-pivot
set assessed here is **D126, D127, D128**, plus the P13-framing
`charter/deferred-decisions.md` flag-for-future-testing (6) and defer-with-trigger
(2) entries.

**Quantitative metrics.** Substrate-depth D-entries with a Phase 2-A consumer
beyond tests: D127 (intake substrate — consumed by orchestrations, HTTP, CLI),
D128 (intake_id — written and readable), D126 (decorator — exercised on every use
case). Forward-compat fields populated but never read for a decision: see Y1, Y2.
Forward-compat fields declared and round-tripped but never populated: 1
(`DataPoint.certainty`). Speculative abstractions with zero Phase 2-A polymorphic
consumer: 1 (`Revisable` Protocol).

### Y1 — `ActorContext.role_list` is a write-only field at Phase 2-A

`ActorContext` carries `role_list: frozenset[str]`
([actor_context.py:49](../shared_kernel/actor_context.py#L49)). The
`get_actor_context` HTTP dependency builds it as `frozenset({ROLE_OPERATOR})`,
passes it to `authorisations_for_roles(role_list)` to derive `authorisation_set`,
and stores both on the ActorContext
([middleware.py:205-210](../apps/api/middleware.py#L205)). A grep for `.role_list`
across `contexts/`, `apps/`, and `shared_kernel/` finds exactly two hits — both
the `__post_init__` non-empty invariant ([actor_context.py:57-58](../shared_kernel/actor_context.py#L57)).
**Nothing reads `role_list` after construction.** `authorisation_set` does real
work — the decorator checks `permission in actor.authorisation_set` on every
use-case call — but `role_list` is computed, stored, invariant-checked, and never
consulted again. It is a forward-compat field for the role-hierarchy
deferred-decisions feature (D126 names the activation trigger). The
substrate-depth argument is sound — when a second role lands, having `role_list`
on the envelope means the hierarchy resolves without a signature change — but at
Phase 2-A `role_list` is genuinely write-only. **Severity: material as Phase 3
baseline evidence; the substrate-depth justification is on the record.**

### Y2 — `DataPoint.certainty` is declared, persisted, round-tripped, never populated

`DataPoint.certainty: float | None = None`
([data_point.py:55](../contexts/portfolio/domain/data_point.py#L55)) has a
`__post_init__` range check, a `certainty` column on the `data_points` table
([_tables.py:67](../contexts/portfolio/adapters/outbound/postgres/_tables.py#L67)),
is written by the repository and read by the reader, and surfaces in the
read DTO ([_portfolio_dto.py:113](../apps/api/routers/_portfolio_dto.py#L113)).
But **no code path ever sets it to a non-None value** — `create_data_point`
constructs `DataPoint(...)` without `certainty`, and `revise` preserves it via
`replace`. It is reserved for the D117 tiered-by-salience implementation at P15;
the S43 close reflection (prompt 2) already named it a forward-compat affordance
landed unused. The cost of carrying it is one nullable column — the D12
column-from-inception reasoning generalises cleanly, and the consumer (P15) is
named. **Severity: marginal (single nullable column; defensible substrate-depth;
named consumer).**

### Y3 — The Revisable Protocol has one implementer and zero polymorphic uses

`Revisable` (D114 primitive, D125 shape) is implemented structurally by exactly
one entity — `DataPoint`. It is **never used as a type annotation** anywhere
(see LSP2): no function takes or returns `Revisable[...]`; `DataPoint.revise` and
`.revision_history()` are always called on the concrete type. It has no
contract-test harness (see LSP1). At Phase 2-A the Protocol earns its place only
as documentation of intent. This is the clearest instance of the
substrate-depth-overrides-YAGNI pattern in the Phase 2-A code: an architectural
primitive built ahead of need. It is defensible — D114 classifies it must-have,
P14's methodology-application revision and a future Case-level revision are the
named second and third implementers, and the generic-`Protocol[RevisionT]` shape
is genuinely better protocol design than a context-coupled one. But the honest
Phase 2-A reading is that `Revisable` is substrate with no current polymorphic
consumer. **Severity: material as Phase 3 baseline evidence (cross-referenced to
LSP1 — the same primitive's missing harness is the load-bearing half).**

### Y4 — `ManualEntryPayload.intent_hint` and `linked_case_ids` round-trip but drive no behaviour

Both fields are populated from the HTTP request body
([portfolio.py:140-141](../apps/api/routers/portfolio.py#L140),
[intake.py:82-83](../apps/api/routers/intake.py#L82)), persisted
([intake_repository.py:56-57](../contexts/intake/adapters/outbound/postgres/intake_repository.py#L56)),
read back, and surfaced in the intake response DTO
([_intake_dto.py:64-65](../apps/api/routers/_intake_dto.py#L64)). So unlike Y1
and Y2 they are not write-only — they fully round-trip. But **nothing acts on
them**: there is no intent-based routing, no case-linking heuristic. They are
inert forward-compat payload data; the domain comment dates the linking-heuristics
UX surface to P14. This is honest substrate (D127 builds the payload shape P14
consumes) and the lightest-possible carrying cost (data-only fields). **Severity:
marginal.**

### YAGNI positives (where YAGNI was actively respected)

The Phase 2-A code shows deliberate YAGNI restraint at several points the brief's
watch-points probed:

- **`AssertionChange` has no `rationale` field.** The brief's YAGNI watch-point
  asked whether `AssertionChange.rationale` is "read at any consumer beyond
  tests." The field **does not exist** — `AssertionChange` carries only `value`
  ([revisable.py:40-48](../shared_kernel/revisable.py#L40)). The watch-point
  probed a field that was never built; YAGNI was respected.
- **`IntakePayload` is a one-member alias, not a sealed variant.** D127
  alternative (b) explicitly rejected "a sealed variant type … with empty
  placeholders" per the build-at-second-instance discipline. The code carries
  zero union machinery for the single Phase 2-A variant.
- **`IntakeSource` carries no metadata slot.** D127 alternative (a) rejected a
  discriminated value object with metadata fields; the enum is a bare `str`-Enum.
- **`ActorReference` resists an `actor_type` discriminator.** Its own docstring
  ([actor_reference.py:12-16](../shared_kernel/actor_reference.py#L12)) names the
  resisted field and the deferred-decisions trigger for adding it.

### YAGNI watch-point that dissolved

D128's intake-canonical substrate is **not** "written and forgotten." IntakeRecords
are readable: `get_intake` and `list_intakes` use cases plus `apps/api/routers/intake.py`
expose `GET /api/v1/intakes`, and `intake_id` on portfolio entities surfaces in
the portfolio read DTO. The substrate is both written and consumable at a read
surface — the brief's D128 watch-point ("just being written and forgotten")
dissolves on inspection.

---

# Section 5: Tell Don't Ask (TDA)

**Methodology.** TDA assessed at the command surface (does the caller read object
state and decide externally, or invoke a method that decides internally?) and the
query surface (does the caller extract fields, or does the entity construct its
own representation?) separately.

**Quantitative metrics.** Write-path call sites sampled: the 3 orchestrations,
4 portfolio/intake use cases, `DataPoint.revise` — all tell-shaped. Read-path
call sites: route handlers delegate to translator functions (`*_to_dto`,
`*_to_response`) — a forced middle pattern, see T3.

### TDA positives (the command surface)

The Phase 2-A command surface is tell-shaped. Orchestrations tell:
`portfolio_writer.create_case(...)`, `record_intake(...)`. Use cases tell:
`repository.save_case(...)`, `audit_port.emit(...)`. The domain decides
internally: `DataPoint.revise(change, actor, intake_id)` mints its own `Assertion`
— id, timestamp, `revises_assertion_id` chaining — inside the method
([data_point.py:101-113](../contexts/portfolio/domain/data_point.py#L101)); the
caller does not assemble the Assertion and hand it in. `DataPoint.__post_init__`
enforces the assertion-chain invariants (first must be INITIAL, the rest
REVISION) so the entity protects its own integrity. The brief's TDA watch-point
on the Revisable surface — is it `entity.revise(change, actor)` (tell) or
`actor.revise(entity, change)` (ask-across-the-boundary) — is answered: it is
`entity.revise(...)`, the tell shape.

### T1 — The authorisation decorator asks ActorContext for its set and decides externally

`requires_authorisation` reads `actor.authorisation_set` and evaluates
`if permission not in actor.authorisation_set: raise AuthorisationDenied(...)`
([authorisation.py:138](../shared_kernel/authorisation.py#L138)). ActorContext is
a pure frozen data holder; the authorisation *decision* lives in the decorator,
not in the object that owns the authorisation data. The brief's TDA watch-point
asks exactly this. A more TDA-aligned shape would give ActorContext a method —
`actor.is_authorised(permission) -> bool` or `actor.require(permission)` — moving
the decision to the data's owner. The counter: D126 deliberately centralises the
check at one grep-able decorator boundary for procurement-auditability, and
keeping ActorContext a pure data holder is consistent with `TenantContext` (also
a pure holder, no behaviour). Moving the predicate to an `ActorContext` method
would be marginally more TDA-aligned *and* equally grep-able (the decorator would
still be the single application surface), so the trade is close. **Severity:
marginal.**

### T2 — Use cases ask ActorContext for fields and construct across the boundary

Every use case does `tenant_context = actor.tenant_context` and
`authored_by = ActorReference(user_id=actor.actor_id)` — asking the ActorContext
for its parts and constructing a new value object externally. A tell shape would
be `actor.as_actor_reference()`. This is the same code as D6 (the DRY view) and
K3 (the KISS view); under TDA it reads as a mild ask-and-construct at the
value-object boundary. S44a Item 1 documented the `actor.tenant_context`
extraction as deliberate boundary visibility, which is a conscious choice to
prefer the visible ask over the hidden tell. **Severity: marginal (by design per
S44a).**

### T3 — The query/route surface uses translator functions — a hexagonally-forced middle pattern

Route handlers do not ask domain entities for fields directly, nor do entities
construct their own HTTP responses. The route hands a whole domain or result
object to a translator function (`case_detail_to_dto(detail)`,
`case_write_result_to_response(result)` — [portfolio.py:215,244](../apps/api/routers/portfolio.py#L215)).
The translator extracts fields and builds the Pydantic DTO. This is neither the
TDA-ideal ("entity constructs its own response") nor the TDA-violation ("caller
scatters field extraction inline"). It is the forced middle: D16 forbids domain
entities from importing Pydantic, so an entity *cannot* construct its own HTTP
DTO; the translator function is the only available shape, and centralising it in
the `_dto` modules keeps the extraction out of the route bodies. The hexagonal
boundary makes the TDA-ideal architecturally impossible here, and the
translator-function pattern is the honest best resolution. **Severity: no action
(constrained-positive — the route layer is thin and tells; the translator is a
deliberate, centralised boundary).**

A sub-note: `revise_data_point` does `revised.assertions[-1]` after
`existing.revise(...)` to recover the new assertion for persistence — a small
ask-after-tell. `revise` could return the assertion alongside the DataPoint.
Marginal.

---

# Findings synthesis

## Overall posture summary

**KISS — strong.** The Phase 2-A code is, by file size and cyclomatic
complexity, among the simplest in the codebase: 82 of 87 functions at CC ≤ 5, no
context file over 400 lines, one function above CC 10. The write-path layer depth
is high but every layer is charter-mandated. Load-bearing evidence: the CC
distribution and the file size distribution.

**DRY — mixed, drift-present.** The Phase 2-A *context* code is internally clean,
but it sits inside a codebase-wide pattern of reimplementing structural shapes
per context rather than extracting shared primitives — cursor codec (7 copies),
pagination value objects, audit-event drafts, per-tenant wiring adapters. Phase
2-A added two cursor copies and re-inlined audit-draft boilerplate that its
sibling context had factored. Load-bearing evidence: the 7-file cursor diff and
the portfolio-vs-intake `audit_events.py` contrast.

**SRP — mixed.** The Phase 2-A domain and application layers are SRP-clean
(one-file-per-use-case, single-purpose entities). The SRP debt is real and
concentrated entirely in the `apps/` composition layer: five files over 800
lines, the largest (`_cross_context.py`, 1704) on no hygiene list. Load-bearing
evidence: the file size distribution.

**OCP — strong.** No OCP violation surfaced. Enums, the `IntakePayload` alias,
the role-union resolver, and the ActorContext identity slot are all clean
extension points. Load-bearing evidence: the extension-point inventory.

**LSP — drift-present at the verification layer.** The codebase's one
cross-context Protocol, `Revisable`, has no contract-test harness despite three
charter surfaces asserting one exists; its conformance is structurally
unverified. Load-bearing evidence: the absence of `tests/contract/revisable/`.

**ISP — mixed, by deliberate design.** Phase 2-A ports are aggregate-cohesion-
shaped; every consumer uses one method, which the strict metric flags as fat
interfaces, but the cost is near-zero and the pattern is consistent and reasoned.
Load-bearing evidence: the port/consumer table.

**DIP — strong.** 29/29 import-linter contracts; zero vendor SDK imports in any
domain or application layer; the consumer-port pattern correctly realised. One
marginal Phase 1 finding (SQLAlchemy in a tenancy application module). Load-
bearing evidence: the import-linter run and the layer import scan.

**YAGNI — mixed, honestly so.** Phase 2-A shows deliberate restraint at several
points (no sealed-variant placeholder, no metadata slot, no resisted
discriminator) and equally carries forward-compat affordances inert at Phase 2-A
(`role_list` write-only, `certainty` never populated, `Revisable` with no
polymorphic consumer). Per the brief, these are Phase 3-audit baseline evidence,
not Phase 2 violations. Load-bearing evidence: the `.role_list` grep and the
`certainty` populator search.

**TDA — strong on the command surface.** Orchestrations and use cases tell;
domain entities decide internally. The two minor ask-shapes (the authorisation
decorator, the ActorContext unpack) are conscious trade-offs; the query surface's
translator pattern is hexagonally forced.

## Cross-principle pattern findings

**CP1 — Structural shapes reimplemented per context (DRY × KISS).** The single
largest pattern in the assessment. The cursor codec (D1), pagination value
objects (D2), audit-event drafts (D3), and per-tenant wiring adapters (D4) are
each a structural shape copied per context rather than extracted to a shared
primitive. The pattern spans four DRY findings. It is now well past the
methodology's own three-instance structural-promotion threshold (cursor codec
alone is at 7), and the copies have begun to **diverge** — the Phase 2-A cursor
codec is better-factored than the Phase 1 copies, meaning fixes no longer
propagate. P12 audit Finding B5 saw the cursor slice and dispositioned it
non-action on "structural consistency" grounds; that justification is now
strained because the consistency has broken.

**CP2 — SRP debt concentrates in the composition layer, not the contexts.** The
five files over 800 lines are all `apps/` wiring, error-handling, and
cross-context-adapter files (SRP1, SRP2, SRP3). The `contexts/` themselves —
including the Phase 1 contexts at the domain and most of the application layer —
are well-factored; the exception, `agent/application/use_cases.py` (SRP4), is a
Phase 1 shape the Phase 2-A contexts have already evolved past. The composition
layer accretes because it is where every new context's wiring must land and no
file-topology budget governs it the way it governs context files.

**CP3 — Substrate-depth overrides YAGNI, with load-bearing justification (KISS ×
YAGNI).** D126/D127/D128 are all must-have with cost-of-pivot reasoning, and the
reasoning is sound — the depth bought genuine future simplification (Y3's
generic Protocol, Y1's pure role-hierarchy extension). The residue is three
forward-compat affordances inert at Phase 2-A (Y1, Y2, Y3). This is the pattern
the brief asked to track as Phase 3 baseline evidence; the assessment records it
as honest substrate, not violation — but names the three artefacts so the Phase 3
close audit can check whether their P14/P15 consumers actually materialised.

**CP4 — Phase 2-A code is better-factored than Phase 1 code, and also inherits
Phase 1 smells.** A two-edged observation. Phase 2-A adopted one-file-per-use-case
(better than monolithic `use_cases.py`), factored helpers (`_draft`,
`_session_factory_for_tenant_builder`, the lower-CC cursor `_decode`). It also
propagated the `if "tenant" in str(exc)` message-sniffing (D7 — 8 of 10
occurrences are Phase 2-A) and added two more cursor-codec copies (D1). The newer
code is cleaner where it wrote fresh and dirtier where it copied an existing
pattern.

## Severity-classified findings list

**Load-bearing (1)**

- **LSP1** — Revisable Protocol has no contract-test harness; three charter
  surfaces (D114, D125, `architecture.md:274`, `schema.md`) assert one exists.
  The codebase's one cross-context architectural-primitive Protocol is
  structurally unverified at CI.

**Material (9)**

- **D1** — Cursor codec duplicated across 7 contexts, with divergent evolution.
- **D2** — Pagination value objects duplicated per context (D1 cluster).
- **D3** — Audit-event draft boilerplate: portfolio factored it, intake
  re-inlined it; 11-arg list written twice per draft.
- **D4** — Per-tenant-resolving wiring-adapter boilerplate repeated ~15×.
- **D7** — Route-level tenant-mismatch rewrap repeated 10× via exception-message
  string-sniffing (fragility + duplication).
- **SRP1** — `apps/api/_errors.py` at 828 lines; grew ~99 lines at S44b under a
  standing split-flag.
- **SRP2** — `apps/api/_agent_runtime_wiring.py` at 912 lines; name is a misnomer
  for a 10-context composition root.
- **SRP3** — `apps/cli/_cross_context.py` at 1704 lines (largest file); on no
  hygiene list.
- **Y1 / Y3** — `ActorContext.role_list` write-only at Phase 2-A; `Revisable`
  Protocol with one implementer and zero polymorphic uses (Phase 3 baseline
  evidence).

**Material as Phase 1 debt, out of Phase 2-A scope (1)**

- **SRP4** — `contexts/agent/application/use_cases.py` at 1054 lines (Phase 1).

**Marginal (12)**

- **K2** — write-path layer depth high but charter-mandated.
- **K3** — `actor.tenant_context` extraction verbosity (S44a trade-off holds).
- **K4** — audit-event drafts compute a placeholder hash that is discarded.
- **D5** — three intake orchestrations share a ~7-line prologue.
- **D6** — use-case ActorContext-unpack prologue repeated ~7×.
- **D8** — domain `jurisdiction` non-empty validation repeated across ~6 value
  objects.
- **LSP2** — `DataPoint.revise` extends the Revisable signature with `intake_id`
  (LSP holds; Protocol is documentation-only).
- **ISP1** — Phase 2-A ports are aggregate-cohesion-shaped (deliberate;
  `assertion_history` slightly redundant).
- **DIP1** — `sqlalchemy` imported at `contexts/tenancy/application/` (Phase 1).
- **Y2** — `DataPoint.certainty` declared, persisted, never populated.
- **Y4** — `intent_hint` / `linked_case_ids` round-trip but drive no behaviour.
- **T1 / T2** — authorisation decorator and use-case unpack are mild ask-shapes
  (conscious trade-offs).

## Recommended actions per finding

These are **inputs to the disposition conversation, not commitments at this
session**.

| Finding | Recommended disposition |
|---|---|
| LSP1 | Hygiene item — land `tests/contract/revisable/`; the harness is already on the Phase 2-A close hygiene list and D114/D125/architecture.md/schema.md all assert it. Closing it also closes a charter-vs-code honesty gap. |
| D1 + D2 | Hygiene item — extract a generic base64-JSON cursor codec plus shared `MalformedCursorError` / `PAGE_SIZE_CEILING`, parameterised over the cursor dataclass. Re-examine P12 Finding B5's non-action disposition: the 7-instance count and the divergence have overtaken its "structural consistency" reasoning. |
| D3 | Hygiene item — extract a shared audit-event draft helper, or at minimum align intake to portfolio's `_draft` shape. Consider whether `AuditEvent` should compute its own draft hash to remove the 11-arg double-listing (relates to K4). |
| D4 | Hygiene item — extract a shared per-tenant-routing adapter primitive; coordinate with the SRP2 split. |
| D7 | Hygiene item — replace exception-message sniffing with a typed bound-tenant exception raised by the adapter; removes both the duplication and the fragility. Spans Phase 1 (`run_history.py`) and Phase 2-A. |
| SRP1, SRP2, SRP3 | Hygiene items — SRP1 and SRP2 are already on the Phase 2-A close hygiene list; **add SRP3 (`_cross_context.py`, 1704 lines)**, which is currently tracked nowhere. Consider whether the file-topology budget discipline should extend to the `apps/` composition layer. |
| SRP4 | Deferred — Phase 1 debt; note the positive Phase 2-A evolution (one-file-per-use-case) and leave the Phase 1 contexts for a Phase 1-scoped hygiene pass if one occurs. |
| Y1, Y2, Y3 | No action now — forward to the Phase 3 close audit as baseline evidence per the YAGNI-monitoring discipline. The Phase 3 audit checks whether the P14/P15 consumers (role hierarchy, tiered-by-salience, methodology-application revision) materialised; if a consumer does not arrive, the affordance is reclassified. This is the queue the held YAGNI-monitoring draft text addresses. |
| D5, D6, D8, K3, K4, LSP2, ISP1, DIP1, Y4, T1, T2, K2 | No action — marginal; recorded for completeness. Several are conscious, charter-reasoned trade-offs (D5 per D127(d), D6/K3/T2 per S44a Item 1, ISP1 per aggregate cohesion). |
| CP1–CP4 | Cross-principle patterns — inputs to the disposition session's framing; CP1 is the disposition's highest-value single thread (it consolidates D1–D4); CP2 motivates extending the file-topology budget to `apps/`. |

---

*End of assessment. Conducted 2026-05-22 against commit `59bf205` (S44b close).
Findings are evidence for the subsequent disposition conversation; this document
records, it does not dispose.*
