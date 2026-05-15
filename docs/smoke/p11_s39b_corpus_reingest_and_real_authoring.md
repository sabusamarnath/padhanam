# P11 S39b — Corpus re-ingest and real-corpus discovery-mode authoring (2026-05-15)

Closes the three smoke-evidence carryovers from S39
(`docs/smoke/p11_s39_retrieval_evaluation_substrate.md`):

1. LVTGuide re-seed plus retrieval allowlist application (S30b carryover).
2. tenant_a corpus re-ingest so retrieval has chunks to surface.
3. Real-corpus discovery-mode gold-set authoring (closes S39 AC 10
   verification gap — S39's smoke verified only typer-wiring imports).

## Pre-flight (executed)

Image: rebuilt at the start of S39b to bake migration 0013 plus the
S39b runtime fix at commit `5c7a7f2` (see Stage 4 below for the
runtime divergence the fix corrected).

`compose.yaml` digest pin advanced twice during S39b:
- `05917101...` post-migration-0013 image build
- `d68e171c...` post-runtime-fix image build (current at session close)

Vendor reconciliation against Ollama (matches the pre-write
reconciliation report):
- `nomic-embed-text:v1.5` present (`docker compose exec ollama ollama list`).
- `chunks.embedding` column is `vector(768)`; embedding model native
  output dimension is 768. Dimensions match; pgvector accepts inserts.

`tenant_a` pre-state: 0 chunks, 0 sources (S39 close state preserved).

## CC-autonomously authoring provenance

S39b's discovery-mode authoring runs entirely as Claude Code
operating autonomously. **The "operator" picking correct retrieval
candidates is CC, not the human operator.** This matters for the
audit trail: the ground-truth annotations on this gold-set reflect
CC judgment about which chunks plausibly answer each query, not
human judgment. Anyone reading this gold-set's provenance at the
P12 audit (or at any future point where this gold-set's "correct
answer" coverage matters) should understand that distinction.

## Stage 1 — LVTGuide re-seed (executed)

Migration `0013_lvtguide_reseed` lands the LVTGuide row plus
revision 1 with the retrieval tool reference pinned at insertion
time. System prompt lifted verbatim from `briefs/p7/s25.md`;
strategy name `parallel_rrf` per D66's registry (the S25 brief said
"hybrid" citing D66; D66's actual strategy name is `parallel_rrf`).

Post-migration state on the control plane:
```
   name   |       created_by_user_id       | version | tool_allowlist
----------+--------------------------------+---------+--------------------------------------------------------------------------------------------------------------
 LVTGuide | migration:0013_lvtguide_reseed |       1 | [{"tool_id": "00000000-0000-0000-0000-000000000001", "revision_id": "00000000-0000-0000-0000-000000000002"}]
```

Provenance symmetry with the seven McKinsey 7-Step roles preserved
(all eight platform-managed roles now carry `migration:NNNN_...`
actor).

Chain integrity verification across all eight role-revision chains:
```
Analyst              v1 stored=e2235a8213cf recomputed=e2235a8213cf OK
Communicator         v1 stored=046529d3afe7 recomputed=046529d3afe7 OK
Disaggregator        v1 stored=8ff135007d2d recomputed=8ff135007d2d OK
LVTGuide             v1 stored=41f61a67fccc recomputed=41f61a67fccc OK
Planner              v1 stored=22eec192a66c recomputed=22eec192a66c OK
Prioritiser          v1 stored=a7fd0da3b0f6 recomputed=a7fd0da3b0f6 OK
ProblemFramer        v1 stored=a98915cb8bc0 recomputed=a98915cb8bc0 OK
Synthesiser          v1 stored=04f54e975cd4 recomputed=04f54e975cd4 OK
broken=0/8
```

D26 chain-self-containment honoured on every row.

## Stage 2 — Corpus re-ingest (executed)

S25's original synthetic LVT-shaped markdown sources never landed in
the repo (per pre-write reconciliation Finding 1; the captures.md
2026-05-11 entry names the source UUIDs but the content was
ephemeral). Substitute corpus drafted at S39b execution time:

| File | Purpose |
|------|---------|
| `lvt_methodology_overview.md` | Plausibly answers Query 2 ("LVT methodology framing") |
| `agent_cost_governance.md` | Plausibly answers Query 1 ("cost ceiling for PM agent") |
| `padhanam_bet_summary.md` | Plausibly answers Query 3 ("bet on procurement-grade architecture") |
| `optimization_layer_overview.md` | Noise/discrimination context (gives operator non-correct chunks to discriminate against during index selection) |

Cost-ceiling specifics softened per operator review at the corpus
draft pause: invented dollar figures ($0.05 per-invocation soft,
$5.00 per-day hard) stripped; the file describes the cost-ceiling
shape (soft/hard split, attribution surface, layering rationale)
without committing to numeric values the repo does not actually
assert. Reason: the gold-set's "correct" chunks become evidence the
retrieval-evaluation context cites at S40 and that downstream
consumers (the optimisation layer at S41) operate against; invented
dollar values in those chunks would contaminate the audit trail
with assertions the repo may never actually make.

LVT feedback-loop observation: the `lvt_methodology_overview.md`
content paraphrases the LVTGuide system prompt being seeded by
migration 0013. This is a structural-honesty observation that
matters for any future reader interpreting the gold-set's "correct
answer" coverage on the LVT query. The S39b real-corpus gold-set is
a CLI-flow-verification artefact, not a methodologically-clean
evaluation baseline; the LVT-query results will be misleadingly
high at S40's runner because the retrieval corpus and the agent's
system prompt share LVT framing content. Methodologically clean
evaluation gold-sets need queries whose answers exist in the
per-tenant corpus but not in the agent's system prompt. Recorded as
a carryover line in the S39b session log entry.

Ingestion sequence:
- 4 sources registered via `padhanam ingest run`.
- Worker drained `parse → embed → extract` per source.
- `agent_cost_governance.md` failed `extract` on first attempt
  (LLM-extracted relationship_type `'for-inspection'` invalid as
  Cypher identifier); re-ingested by deleting + re-running, reached
  `indexed` cleanly on retry. The transient extraction failure is a
  vendor-LLM-output variability observation, not a structural
  drift; documented here so anyone repeating the smoke understands
  the retry path.

Final corpus state on `tenant_a`:
```
           file_name           |  state
-------------------------------+---------
 agent_cost_governance.md      | indexed
 lvt_methodology_overview.md   | indexed
 optimization_layer_overview.md| indexed
 padhanam_bet_summary.md       | indexed

 total_chunks
--------------
           24
```

AC 1 (≥1 chunk on tenant_a) and AC 2 (embedding dimension match)
verified.

## Stage 3 — S39 gold-set rename (executed)

Direct SQL UPDATE renaming the S39 aggregate from
"P11 retrieval baseline" to "P11 retrieval baseline (synthetic, S39)"
on tenant_a:

```sql
UPDATE gold_sets SET name = 'P11 retrieval baseline (synthetic, S39)'
WHERE id = 'dd4ec3ee-b65d-4426-b6f1-df8a715a1062'
  AND name = 'P11 retrieval baseline';
-- UPDATE 1
```

Post-rename:
```
                  id                  |                  name
--------------------------------------+-----------------------------------------
 dd4ec3ee-b65d-4426-b6f1-df8a715a1062 | P11 retrieval baseline (synthetic, S39)
```

**Structural-honesty observation (Finding 3 reconciliation):** the
rename is hash-chain-invariant because the revision-hash canonical
payload at `contexts/retrieval_evaluation/domain/hash_chain.py:70-94`
spans only `{revision_number, entries[{entry_index, query,
expected_chunk_ids}]}` and explicitly excludes the gold-set's name.
Renaming the parent aggregate does not invalidate any finalized
revision's `this_event_hash`. This is the structural proof that the
rename does not break D109 commitment 4: the hash-chain anchor is
revision content, not aggregate identity. The S39 gold-set's stored
hash `ad94611492299f23b76d7c3eb4602206e88a20223e9ea5983bb0568c43f465a4`
still recomputes byte-identically post-rename.

AC 4 (S39 gold-set renamed; aggregate revisions and entries intact)
verified.

## Stage 4 — Real-corpus discovery-mode authoring (executed)

S39's smoke verified only the typer-wiring imports. S39b's
real-corpus authoring exercised the path end-to-end for the first
time and immediately surfaced a runtime divergence:

```
File "/app/apps/cli/_retrieval_evaluation.py", line 166, in _go
    excerpt = c.text[:120].replace("\n", " ")
AttributeError: 'ChunkResult' object has no attribute 'text'
```

`ChunkResult` at `contexts/ingestion/domain/chunk_result.py` carries
`.content` (the chunk text) and `.similarity_score` (the score). The
CLI at S39 referenced `.text` and `.score`; the import-shape
verification passed because the CLI's typer registration imports
cleanly without invoking the candidate-rendering loop. Runtime
verification was the missing piece; S39b is where it landed.

Fix at commit `5c7a7f2` (`fix(p11/s39b): correct ChunkResult
attribute access in gold-set append-entry CLI`): `c.text` →
`c.content`, `c.score` → `c.similarity_score`. Image rebuilt
(digest `d68e171c...`), compose pin advanced, container recreated,
smoke resumed.

This runtime divergence is the methodology-shape observation that
justifies the verification-and-hygiene-bridge session shape: import-
shape verification does not substitute for runtime verification at
the discovery-mode CLI altitude. Future session-shape: substrate
sessions should not claim AC closure on CLI ACs without running the
CLI's runtime path against real producers; S39's AC 10 needed S39b
to actually close.

### Create gold-set (executed)

```
$ docker compose exec -T padhanam-api python -m apps.cli gold-set create \
    --tenant-id a --name "P11 retrieval baseline (real corpus)"
gold_set_id=78f65f1e-c352-453c-aa1c-589930cd5293
initial_revision_id=fdecc36b-2b5d-4eb8-97ee-31f962892ffb
status=draft revision_number=1
```

### Append entry 1: cost-ceiling query (executed)

```
$ docker compose exec -T padhanam-api python -m apps.cli gold-set append-entry \
    --tenant-id a --gold-set-id 78f65f1e-... \
    --query "what is the cost ceiling for the PM agent" \
    --top-k 10 --correct-indices "1"

retrieved 10 candidates:
  [1] chunk_id=0823271c-...  score=0.824  excerpt='## The cost-ceiling surface  Every agent at Padhanam carries a cost ceiling at the tenant-registry level...'
  [2] chunk_id=c482db53-...  score=0.791  excerpt="## The PM agent's cost ceiling  The platform's cost-ceiling surface exposes per-invocation soft limits..."
  [3] chunk_id=02f93aca-...  score=0.770  excerpt='## Why cost-ceiling values are not in the agent template...'
  [4] chunk_id=d39af4d2-...  score=0.683  excerpt='## Cost-attribution surface  Every cost-bearing operation tags the cost event...'
  [5] chunk_id=6a8e921b-...  score=0.676  excerpt='## What success at Phase 1 close looks like...'
  [6] chunk_id=ebb78bf5-...  score=0.652  excerpt='## Why cost governance is a first-class concern...'
  [7] chunk_id=b4a48efd-...  score=0.619  excerpt='## Why procurement-grade architecture is load-bearing...'
  [8] chunk_id=044c4159-...  score=0.603  excerpt='## How LVT is applied at Padhanam...'
  [9] chunk_id=fcf48d0a-...  score=0.594  excerpt='## What the bet is...'
  [10] chunk_id=6ae32bcf-... score=0.592  excerpt='## What the LVT framing is...'
entry_id=440bbc3a-...  entry_index=0  opened_new_draft=False
```

CC selected index 1: the cost-ceiling surface chunk. Other plausibly
correct candidates (2, 3, 4) deliberately not selected to keep the
gold-set entry's expected_chunk_ids minimal — recall@5 will report
1/1 perfect; the gold-set is a CLI-flow-verification artefact, not
a methodologically-clean evaluation baseline (see Stage 2 LVT-
feedback-loop note).

### Append entry 2: LVT methodology framing (executed)

```
$ docker compose exec -T padhanam-api python -m apps.cli gold-set append-entry \
    --tenant-id a --gold-set-id 78f65f1e-... \
    --query "which sources cover the LVT methodology framing" \
    --top-k 10 --correct-indices "1,2,3"

retrieved 10 candidates:
  [1] chunk_id=6ae32bcf-...  score=0.749  excerpt='## What the LVT framing is  The Lean Value Tree is a product-strategy methodology...'
  [2] chunk_id=bbb661f3-...  score=0.701  excerpt='## When source materials contradict each other  LVT framing assumes the user supplies source materials...'
  [3] chunk_id=044c4159-...  score=0.635  excerpt='## How LVT is applied at Padhanam  The PM agent at Padhanam embeds LVT...'
  [4] chunk_id=88daa585-...  score=0.618  excerpt='## What the optimisation layer is...'
  ...
entry_id=a5cdf2cd-...  entry_index=1  opened_new_draft=False
```

CC selected indices 1, 2, 3: all three top results from
`lvt_methodology_overview.md`. The retrieval correctly identifies
LVT-specific chunks above the optimisation noise chunks at indices
4 onward; the ranked-relevance encoding (1=most relevant) preserves
the model's similarity-score order.

### Append entry 3: bet on procurement-grade architecture (executed)

```
$ docker compose exec -T padhanam-api python -m apps.cli gold-set append-entry \
    --tenant-id a --gold-set-id 78f65f1e-... \
    --query "what does the bet say about procurement-grade architecture" \
    --top-k 10 --correct-indices "1,2,3"

retrieved 10 candidates:
  [1] chunk_id=b4a48efd-...  score=0.850  excerpt='## Why procurement-grade architecture is load-bearing  The bet's test condition is procurement-grade architecture...'
  [2] chunk_id=fcf48d0a-...  score=0.721  excerpt='## What the bet is  Padhanam is a public demonstration that a senior product leader...'
  [3] chunk_id=f90e2ad5-...  score=0.716  excerpt='## The four levels  A bet is a load-bearing strategic claim with named test conditions...'
  [4] chunk_id=10457ca7-...  score=0.715  excerpt='## The compliance and architectural constraints...'
  ...
entry_id=e8e6ae22-...  entry_index=2  opened_new_draft=False
```

CC observation worth recording: candidate 4 (compliance and
architectural constraints, score 0.715) is also strongly relevant
to the procurement-grade-architecture query — substantively as much
or more so than candidate 3 (the LVT four-levels framing, which is
about the bet structurally but not about the bet's procurement-grade
content). CC selected indices 1, 2, 3 by similarity-score rank
rather than by content-fit judgment. A human operator authoring this
gold-set might select 1, 4, 2 instead. The methodology distinction
between rank-based and content-fit-based annotation is a P12 audit
observation worth recording. For S39b's CLI-flow-verification
purpose, rank-based selection demonstrates the discovery-mode CLI
works end-to-end; the methodologically-clean gold-set at S40 should
re-author with content-fit judgment.

### Finalize revision (executed)

```
$ docker compose exec -T padhanam-api python -m apps.cli gold-set finalize \
    --tenant-id a --gold-set-id 78f65f1e-c352-453c-aa1c-589930cd5293
revision_id=fdecc36b-2b5d-4eb8-97ee-31f962892ffb
revision_number=1
status=finalized
this_event_hash=9ee5aed07c7ce176c06c90f9b4d212de4dff400464be476770dc7a92dec228f0
previous_event_hash=0000000000000000000000000000000000000000000000000000000000000000
finalized_at=2026-05-15T13:52:14.828418+00:00
```

`previous_event_hash` is `GENESIS_REVISION_HASH` (64 zeros) per D109
commitment 4.

### Hash-chain integrity verification (executed)

Independent recompute via
`contexts.retrieval_evaluation.domain.compute_revision_hash`
(delegating to `padhanam.security.hash_chain.compute_revision_hash`,
the D75-promoted primitive):

```
stored:     9ee5aed07c7ce176c06c90f9b4d212de4dff400464be476770dc7a92dec228f0
recomputed: 9ee5aed07c7ce176c06c90f9b4d212de4dff400464be476770dc7a92dec228f0
match=True
entries=3
  [0] q='what is the cost ceiling for the PM agent'
      chunks=['0823271c-a279-4277-b45f-52b200761c00']
  [1] q='which sources cover the LVT methodology framing'
      chunks=['6ae32bcf-...', 'bbb661f3-...', '044c4159-...']
  [2] q='what does the bet say about procurement-grade architecture'
      chunks=['b4a48efd-...', 'fcf48d0a-...', 'f90e2ad5-...']
```

D109 commitment 4 verified at revision granularity against the
real-corpus gold-set.

AC 5 (gold-set with real chunk_ids; hash recomputes byte-identically)
verified.
AC 6 (discovery-mode CLI exercised end-to-end with real retrieval-
surfaced candidates) verified.

## Carryovers for S40 / P12

1. **LVT-query feedback loop.** The `lvt_methodology_overview.md`
   source paraphrases the LVTGuide system prompt. Metric scores
   against the LVT query at S40 will be misleadingly high. A
   methodologically-clean evaluation gold-set requires queries whose
   answers exist in the per-tenant corpus but NOT in the agent's
   system prompt.

2. **CC-autonomously authoring provenance.** The expected_chunk_ids
   on this gold-set reflect CC's rank-based selection from
   discovery-mode retrieval candidates, not human operator
   content-fit judgment. Worth flagging if this gold-set's "correct
   answer" coverage is ever cited as ground truth.

3. **Rank-vs-content-fit annotation discipline.** Entry 3's
   selection illustrates the distinction: rank-by-similarity ≠ best
   semantic answer. A human-authored gold-set may make different
   selections; the S39b artefact is sufficient for CLI-flow
   verification but not for evaluation-quality benchmarking.

4. **`docs/archive/snapshots/` directory** still untracked in
   working tree (S38b carryover; script keeps recreating). Not S39b
   work to resolve.
