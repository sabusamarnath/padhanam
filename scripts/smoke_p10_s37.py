"""Live-stack smoke for the P10 S37 audit HTTP transport (D103).

Runs inside padhanam-api against the live API via httpx pointed at
``http://localhost:8000``. Exercises the four routes plus the four
auth failure cases plus the filter validation cases:

Happy paths:
  1. GET /audit/events — tenant token; full page with no filters.
  2. GET /audit/events/{event_id} — tenant token; known event id
     captured from scenario 1's first result.
  3. GET /audit/events?resource_type=X — tenant token; filtered.
  4. GET /audit/events?resource_id=Y&resource_type=X — tenant token;
     narrower filtered page.
  5. GET /platform/audit/events — platform-operator token;
     control-plane chain (may be empty depending on prior smokes;
     we seed first if empty).

Failure paths:
  6. GET /audit/events?resource_id=Y (no resource_type) — tenant
     token; expect 400 invalid_audit_filter.
  7. GET /audit/events?cursor=garbage — tenant token; expect 400
     malformed_audit_cursor.
  8. GET /audit/events — no token; expect 401.
  9. GET /audit/events — platform-operator token; expect 403
     principal_type_mismatch.
 10. GET /platform/audit/events — tenant token; expect 403
     principal_type_mismatch.

Output is JSON for the smoke document to capture verbatim.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import httpx
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from contexts.audit.adapters.outbound.postgres.audit import tenant_audit
from contexts.audit.domain.events import GENESIS_HASH, compute_event_hash
from padhanam.security.auth import (
    issue_dev_token,
    issue_platform_operator_dev_token,
)


TENANT_A_UUID = "00000000-0000-4000-8000-00000000a001"
BASE_URL = "http://localhost:8000"


def _cp_url() -> str:
    user = os.environ["POSTGRES_CONTROL_PLANE_USER"]
    pwd = os.environ["POSTGRES_CONTROL_PLANE_PASSWORD"]
    db = os.environ["POSTGRES_CONTROL_PLANE_DB"]
    return f"postgresql+asyncpg://{user}:{pwd}@postgres-control-plane:5432/{db}"


async def maybe_seed_one_control_plane_event(cp_sm) -> str | None:
    """If the control-plane chain is empty, seed one probe event so
    scenario 5 has data to return. Returns the seeded event id (str)
    if a row was inserted, else None."""
    async with cp_sm() as session:
        count_q = sa.select(sa.func.count()).select_from(tenant_audit)
        existing = (await session.execute(count_q)).scalar_one()
        if existing > 0:
            return None

        # Chain is empty — seed one row at GENESIS.
        event_id = uuid4()
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc)
        ts_iso = ts.isoformat()
        actor = "smoke:p10_s37"
        tenant_id = ""
        jurisdiction = "platform"
        action_verb = "control_plane.audit.smoke_probe"
        resource_type = "probe"
        resource_id = str(event_id)
        before_state: dict[str, Any] = {}
        after_state: dict[str, Any] = {"smoke": "p10_s37"}
        correlation_id = "smoke-p10-s37-cp-seed"

        this_hash = compute_event_hash(
            actor=actor,
            tenant_id=tenant_id,
            jurisdiction=jurisdiction,
            timestamp=ts_iso,
            action_verb=action_verb,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
            correlation_id=correlation_id,
            previous_event_hash=GENESIS_HASH,
        )
        await session.execute(
            sa.insert(tenant_audit).values(
                id=event_id,
                tenant_id=tenant_id,
                actor=actor,
                jurisdiction=jurisdiction,
                timestamp=ts,  # datetime, not str — Postgres TIMESTAMPTZ
                action_verb=action_verb,
                resource_type=resource_type,
                resource_id=resource_id,
                before_state=before_state,
                after_state=after_state,
                correlation_id=correlation_id,
                previous_event_hash=GENESIS_HASH,
                this_event_hash=this_hash,
            )
        )
        await session.commit()
        return str(event_id)


def _summarise_response(resp: httpx.Response) -> dict[str, Any]:
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    return {
        "status_code": resp.status_code,
        "correlation_id_header": resp.headers.get("x-correlation-id"),
        "error_code": body.get("error_code") if isinstance(body, dict) else None,
        "body_summary": _summarise_body(body),
    }


def _summarise_body(body: Any) -> Any:
    if isinstance(body, dict):
        if "events" in body:
            return {
                "events_count": len(body["events"]),
                "first_event_id": body["events"][0]["id"] if body["events"] else None,
                "first_tenant_id": (
                    body["events"][0]["tenant_id"] if body["events"] else None
                ),
                "chain_integrity_status": body.get("chain_integrity", {}).get("status"),
                "next_cursor_present": body.get("next_cursor") is not None,
            }
        if "id" in body:
            return {
                "id": body.get("id"),
                "tenant_id": body.get("tenant_id"),
                "action_verb": body.get("action_verb"),
                "this_event_hash_head": body.get("this_event_hash", "")[:16],
            }
        if "message" in body and "error_code" in body:
            return {"error_code": body["error_code"], "message": body["message"][:120]}
    return body


async def main() -> None:
    tenant_token = issue_dev_token(
        subject="smoke:p10-s37-tenant",
        tenant_id=TENANT_A_UUID,
        roles=["audit.read"],
    )
    operator_token = issue_platform_operator_dev_token(
        subject="smoke:p10-s37-ops"
    )

    cp_engine = create_async_engine(_cp_url())
    cp_sm = async_sessionmaker(cp_engine, expire_on_commit=False)
    seeded_cp_event_id = await maybe_seed_one_control_plane_event(cp_sm)
    await cp_engine.dispose()

    results: dict[str, Any] = {
        "seeded_cp_event_id": seeded_cp_event_id,
    }

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # ----- Happy path 1: tenant list with no filters -----
        resp = await client.get(
            "/audit/events",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        scenario_1 = _summarise_response(resp)
        results["scenario_1_tenant_list_no_filters"] = scenario_1

        known_event_id: str | None = None
        if resp.status_code == 200:
            body = resp.json()
            if body.get("events"):
                known_event_id = body["events"][0]["id"]

        # ----- Happy path 2: tenant single-event lookup -----
        if known_event_id:
            resp = await client.get(
                f"/audit/events/{known_event_id}",
                headers={"Authorization": f"Bearer {tenant_token}"},
            )
            results["scenario_2_tenant_get_known_event"] = _summarise_response(resp)

        # ----- Happy path 3: tenant list with resource_type filter -----
        resp = await client.get(
            "/audit/events",
            params={"resource_type": "probe"},
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        results["scenario_3_tenant_list_resource_type"] = _summarise_response(resp)

        # ----- Happy path 4: tenant list with paired resource filter -----
        # Use the first event's resource_id + resource_type if available.
        if resp.status_code == 200:
            scenario_3_body = resp.json()
            if scenario_3_body.get("events"):
                rid = scenario_3_body["events"][0]["resource_id"]
                rtype = scenario_3_body["events"][0]["resource_type"]
                resp = await client.get(
                    "/audit/events",
                    params={"resource_type": rtype, "resource_id": rid},
                    headers={"Authorization": f"Bearer {tenant_token}"},
                )
                results["scenario_4_tenant_list_paired_resource"] = (
                    _summarise_response(resp)
                )

        # ----- Happy path 5: platform-operator list (control-plane) -----
        resp = await client.get(
            "/platform/audit/events",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        results["scenario_5_platform_list_cp"] = _summarise_response(resp)

        # ----- Failure 6: resource_id without resource_type -> 400 -----
        resp = await client.get(
            "/audit/events",
            params={"resource_id": "any-id"},
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        results["scenario_6_resource_id_without_resource_type"] = _summarise_response(
            resp
        )

        # ----- Failure 7: malformed cursor -> 400 -----
        resp = await client.get(
            "/audit/events",
            params={"cursor": "not-a-real-cursor"},
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        results["scenario_7_malformed_cursor"] = _summarise_response(resp)

        # ----- Failure 8: no auth header -> 401 -----
        resp = await client.get("/audit/events")
        results["scenario_8_no_auth"] = _summarise_response(resp)

        # ----- Failure 9: platform-operator on tenant route -> 403 -----
        resp = await client.get(
            "/audit/events",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        results["scenario_9_platform_operator_on_tenant_route"] = _summarise_response(
            resp
        )

        # ----- Failure 10: tenant token on platform route -> 403 -----
        resp = await client.get(
            "/platform/audit/events",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        results["scenario_10_tenant_on_platform_route"] = _summarise_response(resp)

    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
