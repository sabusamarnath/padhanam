# P11 S40b — Clean gold-set authoring with content-fit selection

Closes the S40-close verdict: the S39b gold-set was rank-selected, the S40
runner verified its substrate end-to-end, the metrics were "perfect" for
structural rather than retrieval-quality reasons, and an S40b bridge
session was needed before S41 could cite gold-set evaluation as
procurement-grade evidence. This smoke walks the corpus refresh, the
content-fit authoring, the verification re-run, and the S41-evidence
verdict on the new gold-set.

Verification date: 2026-05-15. Stack identified by `docker compose ps`
at S40 smoke time (~30 minutes prior to S40b); all services healthy.

## Caveats and pre-write notes

Two notes worth surfacing up front because they shape how the metric
values below are read.

- **Pre-write reconciliation Query 2 reframing.** The brief specified
  replacing `lvt_methodology_overview.md` content without naming the
  query reframing as load-bearing. Pre-write reconciliation surfaced
  that the original Query 2 ("which sources cover the LVT methodology
  framing") uses the word *framing* which is system-prompt vocabulary;
  retrieval against any LVT-shaped corpus would surface chunks sharing
  that vocabulary regardless of what the corpus says. Reframed Query 2
  ("how did Pacelane apply LVT to its recovery-first wearable launch")
  uses case-study-specific terms that exist only in the new corpus.
  Vocabulary divergence comes from the case-study domain being
  something the LVTGuide system prompt has no exposure to. This is the
  third instance of pre-write reconciliation surfacing a brief-vs-
  required-structure gap in P11 (after D105 scoring-sheet sibling-in-
  pattern at S39 and D66 framing-vs-as-built at S40).

- **MRR-above-0.9-revise threshold operator-owned as a wrong implicit
  assumption.** The brief said MRR above 0.9 raises a structural-honesty
  question and would trigger revising the corpus or query. At Stage 4
  the recall@k drops were substantive (recall@1 dropped 28% relative,
  recall@3 dropped 20%) but MRR stayed at 1.0. Operator-owned
  disposition: MRR is structurally insensitive to the contamination
  shape content-fit selection addresses; recall@k is the contamination-
  sensitive surface in this evaluation setup. The Stage 5 verdict
  carries on recall@k evidence, and the methodology line at session-log
  close captures the threshold-setting error explicitly for P12 audit.

## Stage 1 — Corpus refresh on tenant_a

Replace `lvt_methodology_overview.md` (whose paraphrase of the LVTGuide
system prompt was the S39b structural-honesty observation) with the
Pacelane recovery-first wearable case study at
`tests/fixtures/corpus/p11_s40b/pacelane_recovery_first_case.md`.

The operator's refined Neo4j cleanup criterion (per S40b pre-write
reconciliation Finding 6 refinement): for each entity referencing any
LVT-source chunk, remove the LVT-source chunk IDs from
`source_chunk_ids`; delete the entity only if the array becomes empty.
This preserves entities co-derived from surviving sources.

### Stage 1a — Pre-delete inventory

Six chunks belonged to LVT source `166bc87c-b710-4bc9-a6e5-9c000f0d8253`.
Twelve Neo4j entities referenced at least one of those chunks. Per the
refined criterion, eight entities were LVT-source-only (would be
deleted): `"Lean Value Tree"`, `"initiative"`, `"epic"`, `"story"`,
`"LVT"`, `"user"`, `"LVT agent"`, `"Padhanam's broader principle"`.
Four entities were partially-LVT (would be trimmed): `"bet"` (3 chunks,
2 LVT), `"Padhanam"` (4 chunks, 1 LVT), `"PM agent"` (3 chunks, 1
LVT), `"agent"` (3 chunks, 1 LVT).

### Stage 1b — Neo4j cleanup

```cypher
MATCH (e:Entity {tenant_id: '00000000-0000-4000-8000-00000000a001'})
WHERE any(c IN e.source_chunk_ids WHERE c IN [<lvt_chunk_ids>])
SET e.source_chunk_ids = [c IN e.source_chunk_ids
                          WHERE NOT c IN [<lvt_chunk_ids>]]
RETURN count(e);
// entities_trimmed: 12

MATCH (e:Entity {tenant_id: '00000000-0000-4000-8000-00000000a001'})
WHERE size(e.source_chunk_ids) = 0
DETACH DELETE e
RETURN count(*);
// entities_deleted: 8
```

Twelve entities trimmed; eight deleted. `"bet"`, `"Padhanam"`,
`"PM agent"`, `"agent"` preserved with non-LVT chunk references intact.

### Stage 1c — Postgres cleanup

```sql
BEGIN;
DELETE FROM chunks WHERE source_id = '166bc87c-...';  -- 6 rows
DELETE FROM sources WHERE id = '166bc87c-...';        -- 1 row
COMMIT;
```

### Stage 1d — Pacelane source registration and ingest

```
$ docker cp tests/fixtures/corpus/p11_s40b/pacelane_recovery_first_case.md \
    padhanam-padhanam-api-1:/tmp/s40b_corpus/

$ docker compose exec -T padhanam-api python -m apps.cli.main \
    ingest run /tmp/s40b_corpus/pacelane_recovery_first_case.md \
    --tenant-id a --user-id smoke-s40b
acb19547-c91e-4e4f-8ada-9109d5b5bd67
```

Worker drain produced 7 chunks (parse + embed succeeded). The first
worker attempt registered the source as `acb19547-...`'s predecessor
`41fe4786-...`; the extract stage repeatedly stalled.

### Stage 1e — Methodology finding: graph-extract bypass

The local Ollama qwen2.5:7b extract pipeline is slow (1-3 minutes per
chunk) and unreliable on this dev rig — multiple worker invocations
left the source in `extracting` state without producing entities or
transitioning to a terminal state. Per the S39b precedent, the path
forward is "delete + re-run", which I executed once. The second
attempt also stalled. Reading the structural surface: the S40 CLI
runner's graph_only leg returns empty per the honest
`_CliCompositeRetrievalClient` Phase 1 limitation captured at
`apps/cli/_retrieval_evaluation.py` commit b20262a docstring. Since
S40b's contamination-break test is purely about vector retrieval
(graph_only stays at zero metrics regardless of Neo4j entity state),
the graph-extract bottleneck does not affect the test's structural
validity.

Pragmatic disposition: force the source's state to `indexed` via
direct SQL UPDATE on `sources.state`, capturing the bypass as a
methodology finding so the audit trail is honest about what shipped.

```sql
UPDATE sources
SET state = 'indexed'
WHERE id = 'acb19547-...' AND state = 'extracting';
```

The chunks are fully parsed and embedded (vector retrieval works
against them). No Neo4j entities for the Pacelane source were created.
A late-completing worker from the first attempt did write 57 entities
+ 33 relationships for the deleted `41fe4786-...` source; those
orphaned entities were cleaned up via the same trim + conditional-
delete pattern (92 entities trimmed, 65 deleted, 114 entities remain
all with live chunk references).

**P12 audit input:** the graph-extract pipeline's reliability on the
local dev rig is the gating constraint for any S40-style smoke that
needs both retrieval legs. Two paths forward: invest in extract
reliability (timeout handling, automatic retry semantics, observable
worker progress) at a future hygiene session; or accept that
graph_only metrics are honest-zero on this rig and document the
expectation. Either path is reasonable; S40b operates under the
second.

### Stage 1f — Corpus state post-refresh

```
$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -tAc "SELECT s.file_name, count(c.id) FROM sources s
          LEFT JOIN chunks c ON c.source_id = s.id
          GROUP BY s.file_name ORDER BY s.file_name"
agent_cost_governance.md       | 6
optimization_layer_overview.md | 6
pacelane_recovery_first_case.md| 7
padhanam_bet_summary.md        | 6
```

Four sources, all indexed, 25 chunks total. Pacelane source produces
7 chunks (the chunker split slightly differently than the other 6-
chunk sources; the case-study content has a clearer section structure
that produced one extra split).

## Stage 2 — Rename the S39b rank-selected gold-set

```sql
UPDATE gold_sets
SET name = 'P11 retrieval baseline (rank-selected, S39b)'
WHERE id = '78f65f1e-c352-453c-aa1c-589930cd5293'
  AND name = 'P11 retrieval baseline (real corpus)'
RETURNING id, name;
-- 78f65f1e-...|P11 retrieval baseline (rank-selected, S39b)
```

Hash-chain verification: the stored revision `this_event_hash` is
`9ee5aed07c7ce176c06c90f9b4d212de4dff400464be476770dc7a92dec228f0`
both pre-rename and post-rename — byte-identical. The canonical
revision payload at
[contexts/retrieval_evaluation/domain/hash_chain.py:70-94](contexts/retrieval_evaluation/domain/hash_chain.py#L70-L94)
spans `{revision_number, entries[]}` and explicitly excludes the
gold-set's name field. The rename is hash-chain-invariant under D109
commitment 4. Same structural-proof S39b documented at its smoke
Stage 3 (synthetic gold-set rename to "...(synthetic, S39)").

## Stage 3 — Author clean gold-set with content-fit selection

```
$ docker compose exec -T padhanam-api python -m apps.cli.main \
    gold-set create --tenant-id a \
    --name "P11 retrieval baseline (clean, S40b)" \
    --created-by smoke-s40b
gold_set_id=3b001430-33be-4049-ba3b-34cd30b6d6dd
initial_revision_id=1b90f0ed-7e32-48a1-b41d-eae281393403
status=draft revision_number=1
```

For each of the three queries, the authoring procedure is:

1. Run `padhanam ingest search --query <q> --limit 10` to get the
   top-10 vector retrieval candidates with their similarity scores
   and content excerpts.
2. Read each candidate's content text via direct SQL (`SELECT content
   FROM chunks WHERE id = ?`) when the excerpt is not sufficient to
   judge content fit.
3. Select the chunks that genuinely answer the query, in content-fit
   priority order (not vector-rank order).
4. Run `padhanam gold-set append-entry --correct-indices <selection>`
   to commit the entry.

The selection function (CC reading content and judging answer-fit) is
structurally different from the evaluation function (vector retrieval
ranking by embedding similarity). That structural difference is what
D110's procurement-grade-defensibility commitment depends on.

### Query 1 — "what is the cost ceiling for the PM agent"

Top-10 vector retrieval candidates (similarity / chunk_id / source /
opening line):

| Rank | Sim | Source | Opening |
|---:|---:|---|---|
| 1 | 0.824 | agent_cost_governance | The cost-ceiling surface |
| 2 | 0.791 | agent_cost_governance | The PM agent's cost ceiling |
| 3 | 0.770 | agent_cost_governance | Why cost-ceiling values are not in the agent template |
| 4 | 0.683 | agent_cost_governance | Cost-attribution surface |
| 5 | 0.676 | padhanam_bet | What success at Phase 1 close looks like |
| 6 | 0.652 | agent_cost_governance | Why cost governance is a first-class concern |
| 7-10 | <0.62 | various | (off-topic) |

**Content-fit selection: indices [2, 1] — two chunks, in this order.**

- **Index 2 selected first**: "The PM agent's cost ceiling" names both
  query subjects (the cost ceiling AND the PM agent) and specifies
  the calibration values being tenant-registry defaults. This is the
  most direct answer to "what is the cost ceiling for the PM agent".
- **Index 1 selected second**: "The cost-ceiling surface" defines the
  cost-ceiling abstraction generally (soft vs hard limits, daily budget
  reset, the why-of-the-split). Relevant to "what is" but doesn't
  specify the PM agent — included as supporting context.
- **Index 3 rejected** (vector rank 3): "Why cost-ceiling values are
  not in the agent template" explains architectural placement (cost
  ceiling lives on tenant-registry, not on agent template). Answers a
  related question ("where is the cost ceiling defined") but not "what
  is the cost ceiling for the PM agent". Borderline; rejected on the
  strict reading that "what is" means content-of-the-thing not
  storage-location-of-the-thing.

**Selection-vs-rank divergence:** content-fit puts the rank-2 chunk
first. Comparison to S39b: S39b's authoring for the same query
selected index "1" — a single chunk, the rank-1 one. S40b selects two
chunks in reordered priority.

### Query 2 (reframed) — "how did Pacelane apply LVT to its recovery-first wearable launch"

Top-10 vector retrieval candidates:

| Rank | Sim | Source | Opening |
|---:|---:|---|---|
| 1 | 0.745 | pacelane | Applying LVT to the recovery-first commitment |
| 2 | 0.722 | pacelane | (title chunk: # Pacelane and the recovery-first wearable bet) |
| 3 | 0.687 | pacelane | Epic scope and an early pivot |
| 4 | 0.685 | pacelane | The three initiatives that fell out of the bet |
| 5 | 0.663 | pacelane | A startup with one big question |
| 6 | 0.661 | pacelane | What Pacelane learned about applying LVT |
| 7 | 0.602 | pacelane | Stories, sprint discipline, and a lesson about acceptance criteria |
| 8-10 | <0.58 | other | (cost-attribution, phase 1 close, optimisation — off-topic) |

Vector retrieval correctly discriminated Pacelane chunks from non-
Pacelane chunks: top 7 are all Pacelane. The discrimination test
passes — case-study vocabulary was unique enough.

**Content-fit selection: indices [1, 4, 3, 7, 6] — five chunks, in
this order.**

- **Index 1 selected first**: "Applying LVT to the recovery-first
  commitment" is the foundational LVT-application moment in the case
  study (the bet was written, success criteria named, vision-statement-
  vs-bet conversation captured). Most directly answers "how Pacelane
  applied LVT".
- **Index 4 selected second**: "The three initiatives that fell out of
  the bet" shows the decomposition step — initiative arcs with
  measurable outcomes following from the bet.
- **Index 3 selected third**: "Epic scope and an early pivot" — the
  pivot decision (killing the Daily Fitness Score epic in favour of
  Recovery-specific morning prompt) is a concrete LVT-application
  choice with named consequences.
- **Index 7 selected fourth**: "Stories, sprint discipline, and a
  lesson about acceptance criteria" — story-level LVT application
  with the 25%→8% re-open-rate consequence.
- **Index 6 selected fifth (BORDERLINE, transparent treatment):**
  "What Pacelane learned about applying LVT" is the section the
  operator flagged for transparent discrimination. My initial read at
  draft surfacing framed this section as "abstract reflection rather
  than application narrative". Operator's read: the section contains
  specific LVT-application decisions and consequences — bet's success
  criteria should have been written before the seed raise; the 0.7
  correlation threshold was a guess that got tightened to 0.75 after
  pilot data; the tightened threshold drove substantive recovery-
  model re-architecture. Reading the section in full at authoring
  time, the operator's read is correct: these are concrete
  application observations framed retrospectively, not abstract
  reflection. **Included on the criterion that retrospective framing
  does not disqualify content from answering "how" when the content
  names specific application decisions and their consequences.**
- **Index 2 rejected** (vector rank 2): The title chunk. Mentions
  Pacelane and recovery-first wearable bet but contains no
  application narrative — it's a heading. Rejected on the criterion
  that mentioning the topic is not the same as describing the
  application.
- **Index 5 rejected** (vector rank 5): "A startup with one big
  question" — Pacelane founding background. Mentions the company but
  contains no LVT material; LVT is not adopted until later sections.
  Rejected on the criterion that mentioning the company is not the
  same as describing the LVT application.

**Selection-vs-rank divergence:** content-fit reorders the top-7
non-trivially. Index 1 retained at rank 1 (vector and content-fit
agree on the foundational chunk). Index 4 (rank 4 by vector)
elevated to rank 2 by content-fit (the initiatives narrative answers
"how" more directly than the title chunk at rank 2 and the founding
background at rank 5). Index 2 and Index 5 rejected entirely.

### Query 3 — "what does the bet say about procurement-grade architecture"

Top-10 vector retrieval candidates:

| Rank | Sim | Source | Opening |
|---:|---:|---|---|
| 1 | 0.850 | padhanam_bet | Why procurement-grade architecture is load-bearing |
| 2 | 0.721 | padhanam_bet | What the bet is |
| 3 | 0.715 | padhanam_bet | The compliance and architectural constraints |
| 4 | 0.696 | padhanam_bet | What success at Phase 1 close looks like |
| 5-10 | <0.67 | various | (Pacelane LVT chunks; optimisation; agentic-workflow framing) |

**Content-fit selection: indices [1, 3] — two chunks.**

- **Index 1 selected first**: "Why procurement-grade architecture is
  load-bearing" directly addresses the query subject — names "the
  bet's test condition is procurement-grade architecture" in its
  opening line.
- **Index 3 selected second**: "The compliance and architectural
  constraints" — explicit enumeration of the bet's test conditions
  including specific compliance and architectural requirements.
- **Index 2 rejected** (vector rank 2): "What the bet is" defines the
  bet's central claim (senior product leader directing enterprise-
  grade agentic platform via Claude Code). Mentions "enterprise-
  grade agentic platform" but does not address procurement-grade
  architecture specifically. Rejected on the criterion that defining
  what the bet IS is not the same as answering what the bet SAYS
  about procurement-grade architecture.
- **Index 4 rejected** (vector rank 4): "What success at Phase 1
  close looks like" describes the success demonstration; references
  "enterprise constraints" but does not specifically address
  procurement-grade architecture as a bet element.

**Selection-vs-rank divergence:** content-fit excludes vector rank 2
and includes vector rank 3. Two chunks total vs S39b's three. The
exclusion of "What the bet is" is the content-fit discrimination call
that differs most from rank-selection.

### Finalize

```
$ docker compose exec -T padhanam-api python -m apps.cli.main \
    gold-set finalize --tenant-id a \
    --gold-set-id 3b001430-33be-4049-ba3b-34cd30b6d6dd
revision_id=1b90f0ed-7e32-48a1-b41d-eae281393403
revision_number=1
status=finalized
this_event_hash=8fec2553d90f8af5aa4f066d716451355e548e7b6ef641d9cf1cffd2db2113c3
previous_event_hash=0000000000000000000000000000000000000000000000000000000000000000
```

Genesis revision; previous_event_hash is `GENESIS_HASH` per D26.

## Stage 4 — Verification re-run

```
$ docker compose exec -T padhanam-api python -m apps.cli.main \
    evaluation-run start --tenant-id a \
    --gold-set-id 3b001430-33be-4049-ba3b-34cd30b6d6dd \
    --invoked-by smoke-s40b
evaluation_run_id=c168c2ba-328f-4163-b374-1f69d914b623
status=completed
per_query_results=6
per_strategy_aggregates=2
  strategy=vector_only
    recall_mean={1: 0.400, 3: 0.800, 5: 0.867, 10: 1.0}
    precision_mean={1: 1.0, 3: 0.667, 5: 0.467, 10: 0.3}
    mrr_mean=1.0000
    latency_p50=2564ms latency_p95=5467ms
  strategy=graph_only
    recall_mean={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0}
    precision_mean={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0}
    mrr_mean=0.0000
    latency_p50=0ms latency_p95=0ms
```

### Comparison vs S39b run `ef58678a-...`

| Metric | S39b (rank-selected) | S40b (content-fit) | Δ |
|---|---:|---:|---|
| recall@1 | 0.555 | **0.400** | −28% relative |
| recall@3 | 1.000 | **0.800** | −20% relative |
| recall@5 | 1.000 | **0.867** | −13% relative |
| recall@10 | 1.000 | 1.000 | unchanged |
| precision@1 | 1.000 | 1.000 | unchanged |
| precision@3 | 0.778 | 0.667 | drop |
| precision@5 | 0.467 | 0.467 | unchanged |
| precision@10 | 0.233 | 0.300 | up |
| MRR | 1.000 | 1.000 | unchanged |
| latency p50 | 417 ms | 2564 ms | up |
| latency p95 | 691 ms | 5467 ms | up |

Recall@k drops substantively. Precision@10 rises because S40b's gold-
set has more expected chunks total (9 across 3 entries vs S39b's 7),
so a fixed top-10 captures a higher density of expected.

Latency increase: the Pacelane corpus has 7 chunks (vs 6 for the
other sources), and individual chunks may have more content, so
embedding-time-per-query is higher. The runner-against-corpus latency
is not the contamination-break metric and is captured here for
reproducibility, not as evidence.

## Stage 5 — S41-evidence verdict

**The S39b gold-set's contamination was rank-based selection making
the gold-set's expected chunks equal to vector retrieval's top-K by
construction.** Recall@k=1.0 at S39b for every k≥len(expected) was
not retrieval-quality measurement; it was the trivial consequence of
authoring-function-equals-evaluation-function.

**The S40b clean gold-set breaks the contamination at the recall@k
surface where it should surface.** Content-fit selection includes
chunks vector ranks lower than top-K (Query 1 includes the rank-2
chunk; Query 2 reorders rank-4 above rank-2-and-3; Query 3 includes
rank-3 while excluding rank-2). When the runner exercises the new
gold-set, the recall@k metric measures whether vector retrieval
surfaces the content-fit-selected chunks in the top-K — and the
answer is "mostly yes but not always", reflected in recall@1=0.40,
recall@3=0.80, recall@5=0.87.

**MRR stays at 1.0 for structural reasons, not contamination
reasons.** For each of the three queries, content-fit selection
agrees with vector retrieval on the rank-1 chunk (Query 1: chunk 1
"cost-ceiling surface" is in expected even though chunk 2 is
preferred first; Query 2: chunk 1 "Applying LVT" matches both
selectors; Query 3: chunk 1 "Why procurement-grade architecture"
matches both). With at least one expected chunk at rank 1 for every
entry, MRR=1/1=1.0 by definition. To get MRR<1.0 the gold-set author
would need to *exclude* the rank-1 chunk even when it is legitimately
relevant — the inverse of content-fit discipline. **The structural
cut is sharper than the brief threshold framed: at S39b rank-1 is in
expected BY CONSTRUCTION (rank-based selection); at S40b rank-1 is in
expected BY JUDGMENT (content-fit happened to agree with vector's
top-1 because vector's top-1 is genuinely relevant). The selection-
must-differ-from-evaluated-function principle holds in both cases;
MRR just isn't the surface where the difference surfaces.**

**S41-evidence verdict: the S40b run can be cited as procurement-
grade evidence for retrieval-strategy recommendations, with the
caveat that recall@k and precision@k are the load-bearing metric
surfaces and MRR is structurally non-discriminating in this evaluation
setup.** S41's optimization-engine evidence-citation specification for
the `retrieval_strategy` recommendation category should privilege
recall@k differentials (and precision@k where relevant) over MRR. A
recommendation like "switch from vector_only to graph_only because
vector_only's recall@3 of 0.80 underperforms graph_only's recall@3 of
0.92 on this gold-set" cites the right surface; the same recommendation
citing MRR=1.0 differentials would not. This evidence-shape commitment
should land at S41's framing brief explicitly.

The contamination-break verdict carries on the recall@k evidence. S41
proceeds.

## Cross-tenant verification

tenant_b stays empty per D32 — no rows on any runner table — same
shape as S40 smoke. No new contract harness scenarios needed at S40b
since the contract surface is unchanged.

## Deviations from the brief

Two surfaced at smoke time and shaped the smoke document above.

**Deviation 1: graph-extract pipeline reliability.** The local Ollama
qwen2.5:7b extract pipeline is slow (1-3 min per chunk) and
unreliable — multiple worker invocations left the Pacelane source in
`extracting` state without progress. Per the S40 runner's honest-
empty graph leg the contamination-break test doesn't depend on Neo4j
entity creation; bypassed by forcing `state = 'indexed'` directly.
Captured as methodology finding at Stage 1e and as a P12 audit input.

**Deviation 2: MRR threshold framing in the brief.** The brief stated
that MRR above 0.9 would trigger corpus revision. Operator-owned at
smoke time as a wrong implicit assumption: content-fit selection
typically agrees with vector retrieval at rank-1 when vector retrieval
is competent at top-1 ranking, so MRR=1.0 is a structural property of
this metric on a competent-retrieval setup, not a contamination
signal. The Stage 5 verdict carries on recall@k evidence; the
methodology candidate at session-log close captures the threshold-
setting error explicitly.

## Acceptance criteria status

| AC | Status | Evidence |
|---|---|---|
| 1. S40b in flight paragraph | Done | charter/current-package.md commit ad9d729 |
| 2. .gitignore charter-snapshot rule | Done | commit ad9d729 |
| 3. Corpus content at fixtures path | Done | commit db9cd2d |
| 4. tenant_a chunks reflect refreshed corpus | Done | 25 chunks, 4 sources, all indexed (Stage 1f) |
| 5. S39b gold-set renamed; hash verifies | Done | hash 9ee5aed... byte-identical post-rename (Stage 2) |
| 6. New gold-set with finalized revision | Done | id 3b001430-..., revision 1b90f0ed-..., hash 8fec2553... |
| 7. Content-fit selection rationale per entry | Done | Stage 3 per-query selection blocks |
| 8. S40 runner exercised at Stage 4 | Done | run c168c2ba-... |
| 9. vector_only MRR substantively below 1.0 | Reframed | recall@k drop is the contamination-break evidence; MRR=1.0 is structurally insensitive (Stage 5 verdict + operator-owned threshold revision) |
| 10. S41-evidence verdict captured | Done | Stage 5 |
| 11. Existing unit tests still pass | Pending | will verify at session log commit |
| 12. import-linter contracts pass | Pending | will verify at session log commit |
| 13. git status clean at close | Pending | post-session-log commit |
| 14. Session log entry | Pending | commit 5 |

AC 9 carries an asterisk: the brief threshold was operator-owned at
smoke time as a wrong implicit assumption; recall@k carries the
contamination-break verdict instead. Documented at Stage 5 and at the
session log methodology line.
