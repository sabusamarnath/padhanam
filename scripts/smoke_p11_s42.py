"""Live-stack smoke for the S42 HTTP transport surface (D112).

Exercises the retrieval-evaluation and optimization HTTP routes
end-to-end against the running padhanam-padhanam-api-1 container.
Issues dev JWTs at smoke time, hits the routes via httpx on
localhost:8000, and captures a structured summary suitable for the
smoke-doc artefact.

Seven stages:

- Stage 1: gold-set authoring (create + append entry + finalize + get + list).
- Stage 2: retrieval-candidates discovery (Stage 1 of the two-step shape).
- Stage 3: synchronous evaluation-run kickoff against the new gold-set.
- Stage 4: synchronous optimization-run kickoff against existing evaluation evidence.
- Stage 5: recommendation read surface (list + get; verifies discriminated citations).
- Stage 6: tenant isolation (tenant_a token against tenant_b resource → 404).
- Stage 7: OpenAPI verification (counts new operations).

The script is idempotent at the data level — each invocation creates a
fresh gold-set with a unique name so reruns do not collide.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from padhanam.security.auth import issue_dev_token


_BASE_URL = "http://localhost:8000"
_TENANT_A = "00000000-0000-4000-8000-00000000a001"
_TENANT_B = "00000000-0000-4000-8000-00000000b002"


def _token(*, tenant_id: str = _TENANT_A, subject: str = "smoke-operator") -> str:
    return issue_dev_token(
        subject=subject, tenant_id=tenant_id, roles=["agent.invoke"]
    )


def _headers(*, tenant_id: str = _TENANT_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(tenant_id=tenant_id)}"}


def _stage(name: str) -> None:
    print(f"\n=== {name} ===", flush=True)


def main() -> None:
    summary: dict[str, object] = {}

    with httpx.Client(base_url=_BASE_URL, timeout=120) as client:
        # --------------------------------------------------------------
        # Stage 1: gold-set authoring
        # --------------------------------------------------------------
        _stage("Stage 1: gold-set authoring")
        timestamp = datetime.now(timezone.utc).isoformat()
        gs_name = f"S42 smoke gold-set ({timestamp})"

        r_create = client.post(
            "/gold-sets",
            json={"name": gs_name},
            headers=_headers(),
        )
        assert r_create.status_code == 201, r_create.text
        create_body = r_create.json()
        gold_set_id = create_body["gold_set"]["id"]
        initial_revision_id = create_body["initial_revision"]["id"]
        print(f"created gold-set {gold_set_id}", flush=True)

        # Append an entry. Use a real chunk-id from tenant_a's chain;
        # if there are no chunks (S39b corpus state), the gold_set_entries
        # table has no FK against chunks so the entry persists cleanly.
        fake_chunk_id = str(uuid4())
        r_append = client.post(
            f"/gold-sets/{gold_set_id}/entries",
            json={
                "query": "What is the Lean Value Tree methodology?",
                "expected_chunk_ids": [fake_chunk_id],
            },
            headers=_headers(),
        )
        assert r_append.status_code == 201, r_append.text
        append_body = r_append.json()
        print(
            f"appended entry {append_body['entry']['id']} to revision "
            f"{append_body['revision']['id']}",
            flush=True,
        )

        r_finalize = client.post(
            f"/gold-sets/{gold_set_id}/finalize",
            headers=_headers(),
        )
        assert r_finalize.status_code == 200, r_finalize.text
        finalize_body = r_finalize.json()
        revision_hash = finalize_body["this_event_hash"]
        print(f"finalized revision; hash head: {revision_hash[:16]}", flush=True)

        r_get = client.get(f"/gold-sets/{gold_set_id}", headers=_headers())
        assert r_get.status_code == 200
        get_body = r_get.json()
        assert get_body["current_revision"]["status"] == "finalized"
        assert len(get_body["entries"]) == 1

        r_list = client.get(
            "/gold-sets?page_size=5", headers=_headers()
        )
        assert r_list.status_code == 200
        list_body = r_list.json()
        # The new gold-set is in the listing.
        new_listed = any(
            gs["id"] == gold_set_id for gs in list_body["items"]
        )
        assert new_listed, "new gold-set not present in list"

        summary["stage_1_gold_set_authoring"] = {
            "gold_set_id": gold_set_id,
            "initial_revision_id": initial_revision_id,
            "finalized_revision_hash_head": revision_hash[:16],
            "entries_count": len(get_body["entries"]),
            "list_has_new_gold_set": new_listed,
        }

        # --------------------------------------------------------------
        # Stage 2: retrieval candidates discovery
        # --------------------------------------------------------------
        _stage("Stage 2: retrieval candidates discovery")
        r_candidates = client.get(
            "/retrieval-candidates",
            params={"query": "Lean Value Tree introduction", "limit": 5},
            headers=_headers(),
        )
        assert r_candidates.status_code == 200, r_candidates.text
        candidates_body = r_candidates.json()
        print(
            f"discovery returned {len(candidates_body['candidates'])} candidates",
            flush=True,
        )
        summary["stage_2_retrieval_candidates"] = {
            "candidates_count": len(candidates_body["candidates"]),
        }

        # --------------------------------------------------------------
        # Stage 3: synchronous evaluation run kickoff
        # --------------------------------------------------------------
        _stage("Stage 3: evaluation-run kickoff")
        eval_start = time.monotonic()
        r_eval = client.post(
            "/evaluation-runs",
            json={"gold_set_id": gold_set_id},
            headers=_headers(),
        )
        eval_duration_ms = int((time.monotonic() - eval_start) * 1000)
        assert r_eval.status_code == 201, r_eval.text
        eval_body = r_eval.json()
        evaluation_run_id = eval_body["run"]["id"]
        print(
            f"completed evaluation run {evaluation_run_id} in "
            f"{eval_duration_ms}ms with {len(eval_body['aggregates'])} aggregates",
            flush=True,
        )

        # The new gold-set's expected_chunk_id is a synthetic UUID that
        # doesn't exist in tenant_a's chunks table, so metrics will be
        # all zeros — that's structurally honest for this smoke setup.
        summary["stage_3_evaluation_run"] = {
            "evaluation_run_id": evaluation_run_id,
            "status": eval_body["run"]["status"],
            "duration_ms": eval_duration_ms,
            "per_query_results_count": len(eval_body["results"]),
            "per_strategy_aggregates_count": len(eval_body["aggregates"]),
            "aggregate_strategies": [
                a["retrieval_strategy"] for a in eval_body["aggregates"]
            ],
        }

        # --------------------------------------------------------------
        # Stage 4: synchronous optimization run kickoff
        # --------------------------------------------------------------
        _stage("Stage 4: optimization-run kickoff")
        opt_start = time.monotonic()
        r_opt = client.post(
            "/optimization-runs",
            headers=_headers(),
        )
        opt_duration_ms = int((time.monotonic() - opt_start) * 1000)
        assert r_opt.status_code == 201, r_opt.text
        opt_body = r_opt.json()
        optimization_run_id = opt_body["run"]["id"]
        print(
            f"completed optimization run {optimization_run_id} in "
            f"{opt_duration_ms}ms with {len(opt_body['recommendations'])} "
            f"recommendations; skipped: "
            f"{list(opt_body['run']['skipped_categories'].keys())}",
            flush=True,
        )

        summary["stage_4_optimization_run"] = {
            "optimization_run_id": optimization_run_id,
            "status": opt_body["run"]["status"],
            "duration_ms": opt_duration_ms,
            "recommendations_count": len(opt_body["recommendations"]),
            "skipped_categories": list(
                opt_body["run"]["skipped_categories"].keys()
            ),
            "first_recommendation_category": (
                opt_body["recommendations"][0]["category"]
                if opt_body["recommendations"]
                else None
            ),
        }

        # --------------------------------------------------------------
        # Stage 5: recommendation read surface (verify discriminated citation)
        # --------------------------------------------------------------
        _stage("Stage 5: recommendation read surface")
        r_recs = client.get(
            "/recommendations?page_size=5", headers=_headers()
        )
        assert r_recs.status_code == 200, r_recs.text
        recs_body = r_recs.json()
        print(
            f"recommendation list returned {len(recs_body['items'])} items",
            flush=True,
        )

        sample_citation_category = None
        if recs_body["items"]:
            sample_id = recs_body["items"][0]["id"]
            r_one = client.get(
                f"/recommendations/{sample_id}", headers=_headers()
            )
            assert r_one.status_code == 200
            one_body = r_one.json()
            sample_citation_category = (
                one_body["evidence_citations"][0]["category"]
                if one_body["evidence_citations"]
                else None
            )

        # Filter by category=retrieval_strategy.
        r_filtered = client.get(
            "/recommendations?category=retrieval_strategy",
            headers=_headers(),
        )
        assert r_filtered.status_code == 200
        filtered_body = r_filtered.json()

        summary["stage_5_recommendation_reads"] = {
            "list_count": len(recs_body["items"]),
            "first_citation_category": sample_citation_category,
            "filtered_by_retrieval_strategy_count": len(filtered_body["items"]),
        }

        # --------------------------------------------------------------
        # Stage 6: tenant isolation through HTTP
        # --------------------------------------------------------------
        _stage("Stage 6: tenant isolation")
        # Issue a tenant_b token and try to read tenant_a's gold-set.
        # The bound-tenant adapter sees no match and the route returns 404.
        r_iso = client.get(
            f"/gold-sets/{gold_set_id}",
            headers=_headers(tenant_id=_TENANT_B),
        )
        assert r_iso.status_code == 404, r_iso.text
        iso_body = r_iso.json()
        print(
            f"cross-tenant GET returned {r_iso.status_code} "
            f"error_code={iso_body['error_code']}",
            flush=True,
        )

        # Cross-tenant list returns empty (tenant_b has no gold-sets).
        r_iso_list = client.get(
            "/gold-sets", headers=_headers(tenant_id=_TENANT_B)
        )
        # Note: tenant_b may not be registered in tenant_a's container;
        # the get_tenant_context dependency may raise 404 tenant_not_found.
        # Accept either: a 200 with empty list (tenant exists) or 404
        # (tenant unknown to registry).
        if r_iso_list.status_code == 200:
            iso_list_body = r_iso_list.json()
            iso_list_outcome = (
                f"200 empty={len(iso_list_body['items']) == 0}"
            )
        else:
            iso_list_outcome = f"{r_iso_list.status_code}"

        # Privacy posture: the 404 message names the requester's
        # gold_set_id (which is fine — they asked for it) and the
        # generic word "tenant" without naming any concrete tenant_id.
        # No information about which tenant actually owns the resource
        # leaks.
        leaks_cross_tenant_id = _TENANT_A in iso_body["message"]
        summary["stage_6_tenant_isolation"] = {
            "cross_tenant_get_status": r_iso.status_code,
            "cross_tenant_get_error_code": iso_body["error_code"],
            "leaks_cross_tenant_id_in_body": leaks_cross_tenant_id,
            "cross_tenant_list_outcome": iso_list_outcome,
        }

        # --------------------------------------------------------------
        # Stage 7: recommendation lifecycle exercise
        # --------------------------------------------------------------
        _stage("Stage 7: recommendation lifecycle exercise")
        # Pick two generated recommendations from this smoke run for the
        # lifecycle exercise: one to acknowledge → apply, one to reject.
        # Filter by status=generated so we don't try to transition a
        # terminal recommendation (which would surface as 409).
        r_generated = client.get(
            "/recommendations?status=generated&page_size=5",
            headers=_headers(),
        )
        assert r_generated.status_code == 200
        generated_items = r_generated.json()["items"]
        lifecycle_outcome: dict[str, object] = {
            "generated_count_available": len(generated_items),
        }

        if len(generated_items) >= 2:
            ack_id = generated_items[0]["id"]
            rej_id = generated_items[1]["id"]
            r_ack = client.post(
                f"/recommendations/{ack_id}/acknowledge",
                headers=_headers(),
            )
            assert r_ack.status_code == 200, r_ack.text
            ack_body = r_ack.json()
            r_apply = client.post(
                f"/recommendations/{ack_id}/apply",
                headers=_headers(),
            )
            assert r_apply.status_code == 200, r_apply.text
            apply_body = r_apply.json()
            r_reject = client.post(
                f"/recommendations/{rej_id}/reject",
                headers=_headers(),
            )
            assert r_reject.status_code == 200, r_reject.text
            reject_body = r_reject.json()
            # Attempting to apply again on a terminal recommendation
            # must return 409 with the structured details payload.
            r_terminal = client.post(
                f"/recommendations/{ack_id}/apply",
                headers=_headers(),
            )
            assert r_terminal.status_code == 409, r_terminal.text
            terminal_body = r_terminal.json()
            lifecycle_outcome.update(
                {
                    "acknowledge_status": r_ack.status_code,
                    "acknowledge_transition_to": ack_body["transition"][
                        "to_status"
                    ],
                    "apply_status": r_apply.status_code,
                    "apply_transition_to": apply_body["transition"][
                        "to_status"
                    ],
                    "reject_status": r_reject.status_code,
                    "reject_transition_to": reject_body["transition"][
                        "to_status"
                    ],
                    "terminal_transition_status": r_terminal.status_code,
                    "terminal_error_code": terminal_body["error_code"],
                }
            )
            print(
                f"lifecycle: acknowledge→apply on {ack_id[:8]}, "
                f"reject on {rej_id[:8]}; 409 on re-apply confirmed",
                flush=True,
            )
        else:
            print(
                "insufficient generated recommendations for lifecycle exercise",
                flush=True,
            )

        summary["stage_7_recommendation_lifecycle"] = lifecycle_outcome

        # --------------------------------------------------------------
        # Stage 8: run_history and audit HTTP read surfaces (S34, S37)
        # --------------------------------------------------------------
        _stage("Stage 8: run_history and audit HTTP read surfaces")
        r_runs = client.get("/runs?page_size=5", headers=_headers())
        assert r_runs.status_code == 200, r_runs.text
        runs_body = r_runs.json()
        # Audit list filtered to agent-context events so we avoid the
        # pre-existing empty-correlation_id data shape from S40/S41
        # audit drafts (a captured finding for the pre-P12 hygiene
        # session; not S42's path to fix). The S37 single-event lookup
        # path is unaffected.
        r_audit = client.get(
            "/audit/events?resource_type=agent&page_size=5",
            headers=_headers(),
        )
        audit_status = r_audit.status_code
        if audit_status == 200:
            audit_body = r_audit.json()
            audit_events_count = len(audit_body.get("events", []))
            audit_chain = audit_body.get("chain_integrity", {}).get("status")
        else:
            audit_body = {}
            audit_events_count = 0
            audit_chain = f"error_{audit_status}"
        print(
            f"run_history GET /runs returned {len(runs_body.get('runs', []))} "
            f"runs; audit GET /audit/events (agent filter) returned "
            f"status={audit_status}",
            flush=True,
        )
        summary["stage_8_existing_read_surfaces"] = {
            "run_history_status": r_runs.status_code,
            "run_history_runs_count": len(runs_body.get("runs", [])),
            "audit_status": audit_status,
            "audit_events_count": audit_events_count,
            "audit_chain_integrity_status": audit_chain,
            "audit_filter_used": "resource_type=agent",
            "audit_note": (
                "pre-existing S40/S41 audit rows carry empty correlation_id "
                "which the S36/S37 reader's AuditEventRecord validator "
                "rejects; filter limits to agent-context rows that carry "
                "valid correlation_ids. Captured for pre-P12 hygiene."
            ),
        }

        # --------------------------------------------------------------
        # Stage 9: OpenAPI verification
        # --------------------------------------------------------------
        _stage("Stage 9: OpenAPI verification")
        # /openapi.json is auth-gated like every other route per the
        # AuthenticationMiddleware-on-everything-but-/health policy.
        r_spec = client.get("/openapi.json", headers=_headers())
        assert r_spec.status_code == 200
        spec = r_spec.json()
        operations: list[str] = []
        for path, methods in spec["paths"].items():
            for method, info in methods.items():
                if method.lower() in {"get", "post", "put", "delete", "patch"}:
                    op_id = info.get("operationId", "(unnamed)")
                    operations.append(f"{method.upper()} {path} -> {op_id}")
        # Count the S42-specific operations.
        s42_operation_ids = [
            "createGoldSet", "listGoldSets", "getGoldSet",
            "appendGoldSetEntry", "finalizeGoldSetRevision",
            "listRetrievalCandidates", "startEvaluationRun",
            "listEvaluationRuns", "getEvaluationRun",
            "startOptimizationRun", "listOptimizationRuns",
            "getOptimizationRun", "listRecommendations",
            "getRecommendation", "acknowledgeRecommendation",
            "applyRecommendation", "rejectRecommendation",
        ]
        present_ids = set()
        for path, methods in spec["paths"].items():
            for method, info in methods.items():
                if (op_id := info.get("operationId")) in s42_operation_ids:
                    present_ids.add(op_id)
        missing_ids = set(s42_operation_ids) - present_ids
        print(
            f"openapi spec exposes {len(operations)} total operations; "
            f"{len(present_ids)}/{len(s42_operation_ids)} S42 operations present",
            flush=True,
        )

        summary["stage_9_openapi"] = {
            "total_operations": len(operations),
            "s42_operations_expected": len(s42_operation_ids),
            "s42_operations_present": len(present_ids),
            "missing_operations": sorted(missing_ids),
        }

    print("\n=== Smoke summary ===", flush=True)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
