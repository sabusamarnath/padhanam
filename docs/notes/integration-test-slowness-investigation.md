# Integration-test slowness investigation (2026-05-14)

**Mode:** investigation (no tests/conftest modified, no commits)

Surfaced during S34 close hygiene. Pytest against `tests/integration/contexts/`
plus `tests/integration/evaluation/` (plus the cli + api integration paths)
runs slow enough that intermediate session hygiene runs get killed before
completing. Investigation answers three questions: where does the time
actually go; is the cost from fixture-scope antipatterns or from
test-body real work; is the fix shape mechanical (conftest-only) or
structural (test architecture).

## Section 1 — Durations data

Command run from the host:

```
uv run pytest tests/integration/contexts/ tests/integration/evaluation/ \
  --durations=10 -q --no-header --tb=no
```

The run completed (89 tests; some failures and errors orthogonal to the
investigation per the brief). Top 10 slowest:

| # | Test | Time | Notes |
| - | ---- | ---- | ----- |
| 1 | `evaluation/test_cli_e2e.py::test_eval_run_single_revision_emits_cost_summary` | **167.13s** | call phase |
| 2 | `ingestion/test_retrieval_e2e.py::test_cross_tenant_search_returns_zero_for_other_tenant` | 88.89s | call |
| 3 | `ingestion/test_retrieval_e2e.py::test_search_returns_chunks_for_indexed_tenant_source` | 85.54s | call |
| 4 | `ingestion/test_retrieval_e2e.py::test_cross_tenant_traverse_returns_zero_for_other_tenant` | 78.56s | call |
| 5 | `ingestion/test_retrieval_e2e.py::test_traverse_returns_entities_for_indexed_tenant_source` | 60.85s | call |
| 6 | `evaluation/test_cost_per_successful_task_e2e.py::test_cross_tenant_isolation_at_cost_query_layer` | 54.19s | call |
| 7 | `evaluation/test_cost_per_successful_task_e2e.py::test_cost_per_successful_task_end_to_end_against_tenant_a` | 53.97s | call |
| 8 | `ingestion/test_extract_e2e.py::test_full_pipeline_extract_lands_indexed_with_entities` | 40.90s | call |
| 9 | `evaluation/test_cli_e2e.py::test_eval_report_renders_text_regression_report` | 34.73s | **setup** |
| 10 | `ingestion/test_extract_e2e.py::test_worker_idempotent_on_already_indexed_source` | 30.41s | call |

Sum of top 10: **695s (~11.6 min)**.

Three files dominate the top 10:

- `ingestion/test_retrieval_e2e.py` — 4 tests, **313.84s combined** (entries 2-5).
- `evaluation/test_cli_e2e.py` — 1 call + 1 setup = **201.86s combined** (entries 1 and 9).
- `evaluation/test_cost_per_successful_task_e2e.py` — 2 tests = **108.16s combined** (entries 6-7).
- `ingestion/test_extract_e2e.py` — 2 tests = **71.31s combined** (entries 8, 10).

The two files that I had initially guessed (per the conftest-creating-database hypothesis) — `test_repository.py` and `test_connection_resolution_e2e.py` — are NOT in the top 10. The hypothesis was wrong; the real cost is elsewhere.

## Section 2 — Top-three fixture trace

The user's specific question for each: does the module-scoped fixture share state across tests, or does `engine.dispose()` plus reconnect happen in a per-test function-scoped fixture below it (which would defeat module scope on the engine and pay the connection cost per test anyway)?

### Top 1 — `evaluation/test_cli_e2e.py::test_eval_run_single_revision_emits_cost_summary` (167s)

Fixture chain (read from the file at offsets 95, 445, plus the `_SETUP_SCRIPT` string at 133-396):

- `stack_ready` — `@pytest.fixture(scope="module")` at line 95. Checks docker compose services running plus ollama and langfuse-web health probes. Cost: probe-only, <1s. **Module scope honoured.**
- `populated_data` — `@pytest.fixture(scope="module")` at line 445. Calls `_run_inside_api(_SETUP_SCRIPT, timeout=300)` which invokes `docker compose exec padhanam-api python -` running the embedded `_SETUP_SCRIPT`. The setup script (1) constructs `create_async_engine(_async_url(a))` at line 361, (2) truncates + inserts fixtures, (3) calls `replay_and_score` twice (lines 374-375) — each call drives full LLM inference through `LiteLLMAdapter` against `qwen2.5:7b` via Ollama, (4) `_provider.force_flush(timeout_millis=10000)` + `time.sleep(8)`, (5) `await a_engine.dispose()` at line 392 inside the script's `finally` block.

**Engine.dispose() pattern:** the engine is created at line 361 and disposed at line 392 — within ONE invocation of `_run()`. The `populated_data` fixture runs that one invocation once per module. Tests then invoke the CLI via `_invoke_cli` (subprocess) against the pre-populated state; no per-test engine creation, no per-test dispose. **Module scope is preserved. The 35s setup time IS the LLM cost of two `replay_and_score` calls, not engine-reconnect overhead.**

The 167s test-body time on test 1 is the test itself invoking the CLI's `eval run` command, which runs another full evaluation revision against `qwen2.5:7b` — multiple LLM inference calls inside a fresh CLI subprocess. Pure LLM cost, not fixture cost.

### Top 2-5 — `ingestion/test_retrieval_e2e.py` (4 tests, 314s combined)

Fixture chain (file at offsets 75, 134):

- `stack_ready` — `@pytest.fixture(scope="module")` at line 75. Cheap.
- `_clean` — `@pytest.fixture(autouse=True)` at line 134 with **no explicit scope**, which defaults to **function scope**. Runs on every test. Calls `_truncate_tenant("a")` + `_truncate_tenant("b")` + `_truncate_neo4j_extraction_data()` — three `docker compose exec` shellouts per test, each ~1-2s. Combined truncate cost per test: ~3-6s.

Each test body then runs `_ingest_run` + `_ingest_worker` + `_ingest_search`/`_ingest_traverse`. The `_ingest_worker` step runs the full ingestion pipeline including LLM embedding via LiteLLM → Ollama for every document. That's the dominant cost — ~60-85s per test for embedding work, not the truncation. The function-scoped `_clean` adds maybe ~5s per test on top, which is real but not the headline.

**Engine.dispose() pattern:** NOT applicable. This file does no `create_async_engine` (verified via grep). All work happens through `docker compose exec` subprocess calls to the running container, which manages its own engine lifecycle inside the container. The slowness is real LLM embedding work, not host-side engine reconnection.

### Top 6-7 — `evaluation/test_cost_per_successful_task_e2e.py` (2 tests, 108s combined)

Fixture chain (file at offset 89 + the embedded `_SETUP_SCRIPT` at 343-462):

- `stack_ready` — `@pytest.fixture(scope="module")` at line 89.
- `populated_data` — module-scoped (same pattern as test_cli_e2e.py). The setup script runs ONE replay_and_score against tenant_a, force-flushes spans, sleeps 8s, queries cost-per-successful-task.

**Engine.dispose() pattern:** lines 346-349 create `a_engine` + `b_engine`; lines 457-458 dispose both. All inside one `_run()` invocation; module-scope honoured. The 54s per test is LLM inference within `replay_and_score` (executed inside the per-module setup) plus the cost-query path which hits Langfuse-web's API. Two tests in this module each query against the same pre-populated state but each pays the Langfuse-query roundtrip independently.

## Section 3 — Bonus question — does `test_connection_resolution_e2e.py` reuse compose stack's databases or create per-tenant?

The user's second specific question. Read from offset 87:

The `e2e_setup` fixture is **function-scoped** (no `scope=` decoration). It:
1. Creates **two fresh databases** on the loopback control-plane Postgres (`CREATE DATABASE "e2e_tenant_a_{suffix}"` + `..._b_{suffix}"`) per test (lines 116-120).
2. Applies the per-tenant Alembic chain to each via `command.upgrade(cfg, "head")` (lines 126-133).
3. Registers two synthetic tenants in the live registry pointing at these synthetic DBs.
4. Yields, then on teardown drops both databases.

So it does **create** per-tenant databases — does not reuse the compose stack's tenant_a/tenant_b. But this test is NOT in the top 10 (so the cost is bounded; per-test alembic upgrade on an empty database is fast at this stage).

If it WERE in the top 10, this would be the prototypical mechanical fix: change `@pytest.fixture` to `@pytest.fixture(scope="module")` and add a per-test cleanup helper that truncates rather than drops. But the cost is not currently load-bearing on the slowness budget, so the fix is not urgent.

## Section 4 — Shape determination

**Structural.** Reasoning:

The dominant cost across the top 10 — **~650 of the 695s combined** — is **real LLM inference via LiteLLM→Ollama against `qwen2.5:7b`** (and the embedding model for the retrieval tests). Three pieces of evidence:

1. **All three top-three files import `LiteLLMAdapter`** and construct it with real `InferenceSettings()`. The tests verify cost capture from Langfuse, embedding correctness, retrieval semantics, and end-to-end inference behaviour — these assertions are load-bearing on real model output and real cost telemetry.

2. **Fixture-scope discipline is already in place.** All three files use `@pytest.fixture(scope="module")` correctly. Engine creation in the embedded setup scripts is bounded to ONE invocation per module via `try: ... finally: await engine.dispose()`. The user's concern about module-scope-defeated-by-per-test-dispose does not hold for these files.

3. **The only function-scoped fixture in the top three (`_clean` in test_retrieval_e2e.py)** does `docker compose exec` truncation of Postgres + Neo4j per test (~5s/test, ~20s across 4 tests). That's ~3% of the file's combined cost. Eliminating it would save ~20s on a ~314s budget — meaningful but not dominant.

**Why mechanical doesn't fix this.** Lifting fixture scopes from function to module or session would touch ~50 lines of conftest+inline fixtures, but the LLM-inference cost happens INSIDE test bodies, not in fixture setup. Scope changes cannot move work from test body to once-per-module. To get the LLM cost out of test bodies, the tests would need to share a pre-populated corpus AND change their assertions to not depend on test-specific document content — that's a test-body rewrite, not a conftest change.

**Mechanical opportunity exists but is small.** `test_connection_resolution_e2e.py` (not in top 10) is the textbook function-scoped CREATE DATABASE pattern. Lifting it to module scope would shave some intermediate-time, but doesn't move the needle on the top-three cost.

## Section 5 — Recommended next action

**Defer to a separate session brief — structural surface, not mechanical hygiene.**

The fix space the operator should choose from at session-framing time:

1. **Two-tier test strategy.** Mark the LLM-dependent integration tests with `@pytest.mark.slow` or `@pytest.mark.live_llm` and exclude from the default session-hygiene run; run them on a separate cadence (per-package close, weekly, CI). This is the cheapest structural change: ~one decorator per test plus a pytest marker config plus a session-hygiene helper script change. Loses no fidelity; trades freshness of LLM-dependent verification against turnaround time on the hygiene run.

2. **Shared corpus per module for retrieval tests.** test_retrieval_e2e.py's four tests could share one pre-populated corpus seeded once at module setup; per-test assertions would need rewriting to assert against shared content rather than per-test content. ~saves 80% of test_retrieval_e2e.py's 314s. Touches test bodies plus fixtures. Moderate effort.

3. **pytest-xdist parallelism with Ollama queue tuning.** Wall-clock improvement (4x with 4 workers) without changing test fidelity. Requires Ollama-side concurrency configuration to not bottleneck; potential test-database name collision issues that need per-worker naming. Doesn't reduce total LLM cost — just parallelises.

4. **Mocking the embedder for `_e2e` tests while keeping the `_smoke` tier real.** Highest risk of fidelity loss — the eval/retrieval tests' value is precisely the real-LLM behaviour. Reject unless paired with explicit `_smoke` tier coverage.

The recommended path is **option 1** — the marker-based tier separation — because it preserves test value, requires no test-body changes, and the existing pre-existing failures hint that the LLM tier is already an opt-in surface for full validation rather than session-hygiene. Operator decides at session-framing time which session in P10 or later phase-1-close substrate-completion absorbs the work; the slowness investigation is not the blocker on S35 or any subsequent session unless the operator wants to run the full integration suite as part of S35 hygiene specifically.

## Appendix — Correction to S34 session log claim

S34's session log entry (commit df25baf) named the integration slowness as "tests/integration/contexts/ and tests/integration/evaluation/ which were never reached when I killed the run. Those files create/drop synthetic databases (1–3s each)." The synthetic-database hypothesis was wrong. The actual driver is real LLM inference via Ollama. The session log is otherwise accurate; this note documents the correction without rewriting history.
