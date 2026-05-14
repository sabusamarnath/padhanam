"""Live-stack smoke for the P10 close end-to-end demonstration (D104, S38).

Runs inside ``padhanam-api`` against the live API via httpx pointed
at ``http://localhost:8000``. Exercises the full P10 read substrate
end-to-end in a single reproducible script:

Audit destinations (S36 + S37 substrate):
  1. GET /audit/events — tenant token; verifies per-tenant chain
     reads with ``chain_integrity == "verified"``.
  2. GET /audit/events/{event_id} — tenant token; single-event
     lookup against the per-tenant chain.
  3. GET /platform/audit/events — platform-operator token;
     verifies control-plane chain reads.

Ingestion destinations (S38 substrate):
  4. GET /ingestion/sources — tenant token; verifies own-tenant
     sources visible.
  5. GET /ingestion/sources/{source_id} — tenant token; single
     source lookup.
  6. GET /ingestion/sources/{source_id}/status — tenant token;
     status projection on the existing source.

Cross-destination isolation (D102 + D103 + D104):
  7. GET /platform/audit/events — tenant token; expect 403
     principal_type_mismatch + AUTHZ_DENIAL.
  8. GET /audit/events — platform-operator token; expect 403
     principal_type_mismatch + AUTHZ_DENIAL.
  9. GET /ingestion/sources — platform-operator token; expect 403
     principal_type_mismatch + AUTHZ_DENIAL.

Cross-tenant isolation (D104):
 10. GET /ingestion/sources/{fabricated_uuid} — tenant token; expect
     404 ingestion_source_not_found (no security event).
 11. GET /ingestion/sources?cursor=garbage — tenant token; expect
     400 malformed_ingestion_cursor.

The script seeds a probe control-plane audit event if the chain is
empty and a probe ingestion source on tenant_a if no sources exist;
the seed paths are idempotent so repeat invocations behave the same.
Output is JSON for the smoke document to capture verbatim.

This is the P10 close artefact: the full read substrate exercised
end-to-end on the live stack in a single reproducible invocation.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from contexts.audit.adapters.outbound.postgres.audit import tenant_audit
from contexts.audit.domain.events import GENESIS_HASH, compute_event_hash
from contexts.ingestion.adapters.outbound.postgres._tables import (
    sources as sources_table,
)
from contexts.ingestion.domain.state import SourceState
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


def _tenant_a_url() -> str:
    user = os.environ["POSTGRES_TENANT_A_USER"]
    pwd = os.environ["POSTGRES_TENANT_A_PASSWORD"]
    db = os.environ["POSTGRES_TENANT_A_DB"]
    return f"postgresql+asyncpg://{user}:{pwd}@postgres-tenant-a:5432/{db}"


async def maybe_seed_control_plane_event(cp_sm) -> str | None:
    """Seed one probe event on the control-plane chain if empty.

    Returns the seeded event id (str) if a row was inserted; None
    if the chain already had data.
    """
    async with cp_sm() as session:
        count_q = sa.select(sa.func.count()).select_from(tenant_audit)
        existing = (await session.execute(count_q)).scalar_one()
        if existing > 0:
            return None

        event_id = uuid4()
        ts = datetime.now(timezone.utc)
        ts_iso = ts.isoformat()
        actor = "smoke:p10_s38"
        tenant_id = ""
        jurisdiction = "platform"
        action_verb = "control_plane.audit.p10_close_probe"
        resource_type = "probe"
        resource_id = str(event_id)
        before_state: dict[str, Any] = {}
        after_state: dict[str, Any] = {"smoke": "p10_s38", "phase": "p10_close"}
        correlation_id = "smoke-p10-s38-cp-seed"

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
                timestamp=ts,
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


async def maybe_seed_ingestion_source(tenant_sm) -> str | None:
    """Seed one probe source on tenant_a if no sources exist.

    Returns the seeded source id if a row was inserted; None if
    sources already exist.
    """
    async with tenant_sm() as session:
        count_q = sa.select(sa.func.count()).select_from(sources_table)
        existing = (await session.execute(count_q)).scalar_one()
        if existing > 0:
            return None

        source_id = uuid4()
        now = datetime.now(timezone.utc)
        await session.execute(
            sa.insert(sources_table).values(
                id=str(source_id),
                tenant_id=TENANT_A_UUID,
                jurisdiction="eu-west",
                file_name="p10_s38_smoke_probe.md",
                file_type="markdown",
                file_size_bytes=42,
                raw_content=b"# P10 S38 smoke probe\n",
                state=SourceState.INDEXED.value,
                parsing_error_text=None,
                created_by_user_id="smoke:p10_s38",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
        return str(source_id)


def _summarise(resp: httpx.Response) -> dict[str, Any]:
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
        if "sources" in body:
            return {
                "sources_count": len(body["sources"]),
                "first_source_id": body["sources"][0]["id"] if body["sources"] else None,
                "first_tenant_id": (
                    body["sources"][0]["tenant_id"] if body["sources"] else None
                ),
                "states_present": sorted(
                    {s["state"] for s in body["sources"]}
                ),
                "next_cursor_present": body.get("next_cursor") is not None,
            }
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
        # Single-record shape — common keys for both audit and ingestion.
        if "id" in body and "tenant_id" in body and "this_event_hash" not in body:
            return {
                "id": body.get("id"),
                "tenant_id": body.get("tenant_id"),
                "state": body.get("state"),
                "file_name": body.get("file_name"),
            }
        if "id" in body and "this_event_hash" in body:
            return {
                "id": body.get("id"),
                "tenant_id": body.get("tenant_id"),
                "action_verb": body.get("action_verb"),
                "this_event_hash_head": body.get("this_event_hash", "")[:16],
            }
        if "id" in body and "state" in body:
            return {
                "id": body.get("id"),
                "state": body.get("state"),
                "parsing_error_text": body.get("parsing_error_text"),
                "embedding_error_text": body.get("embedding_error_text"),
                "extraction_error_text": body.get("extraction_error_text"),
            }
        if "message" in body and "error_code" in body:
            return {"error_code": body["error_code"], "message": body["message"][:120]}
    return body


async def main() -> None:
    tenant_token = issue_dev_token(
        subject="smoke:p10-s38-tenant",
        tenant_id=TENANT_A_UUID,
        roles=["audit.read", "ingestion.read"],
    )
    operator_token = issue_platform_operator_dev_token(
        subject="smoke:p10-s38-ops"
    )

    cp_engine = create_async_engine(_cp_url())
    cp_sm = async_sessionmaker(cp_engine, expire_on_commit=False)
    seeded_cp_event_id = await maybe_seed_control_plane_event(cp_sm)
    await cp_engine.dispose()

    tenant_engine = create_async_engine(_tenant_a_url())
    tenant_sm = async_sessionmaker(tenant_engine, expire_on_commit=False)
    seeded_source_id = await maybe_seed_ingestion_source(tenant_sm)
    await tenant_engine.dispose()

    results: dict[str, Any] = {
        "seeded_cp_event_id": seeded_cp_event_id,
        "seeded_source_id": seeded_source_id,
    }

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # ------------- Audit per-tenant chain (S36 + S37) -------------

        resp = await client.get(
            "/audit/events",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        results["1_audit_per_tenant_list"] = _summarise(resp)

        known_event_id: str | None = None
        if resp.status_code == 200:
            body = resp.json()
            if body.get("events"):
                known_event_id = body["events"][0]["id"]

        if known_event_id:
            resp = await client.get(
                f"/audit/events/{known_event_id}",
                headers={"Authorization": f"Bearer {tenant_token}"},
            )
            results["2_audit_per_tenant_get_one"] = _summarise(resp)

        # ------------- Audit control-plane chain (S37) -------------

        resp = await client.get(
            "/platform/audit/events",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        results["3_audit_control_plane_list"] = _summarise(resp)

        # ------------- Ingestion management (S38) -------------

        resp = await client.get(
            "/ingestion/sources",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        results["4_ingestion_list"] = _summarise(resp)

        known_source_id: str | None = None
        if resp.status_code == 200:
            body = resp.json()
            if body.get("sources"):
                known_source_id = body["sources"][0]["id"]

        if known_source_id:
            resp = await client.get(
                f"/ingestion/sources/{known_source_id}",
                headers={"Authorization": f"Bearer {tenant_token}"},
            )
            results["5_ingestion_get_one"] = _summarise(resp)

            resp = await client.get(
                f"/ingestion/sources/{known_source_id}/status",
                headers={"Authorization": f"Bearer {tenant_token}"},
            )
            results["6_ingestion_get_status"] = _summarise(resp)

        # ------------- Cross-destination isolation (D102 + D103 + D104) -------------

        resp = await client.get(
            "/platform/audit/events",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        results["7_tenant_on_platform_audit"] = _summarise(resp)

        resp = await client.get(
            "/audit/events",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        results["8_operator_on_tenant_audit"] = _summarise(resp)

        resp = await client.get(
            "/ingestion/sources",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        results["9_operator_on_ingestion"] = _summarise(resp)

        # ------------- Cross-tenant + malformed inputs (D104) -------------

        fabricated_id = uuid4()
        resp = await client.get(
            f"/ingestion/sources/{fabricated_id}",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        results["10_ingestion_fabricated_source_id"] = _summarise(resp)

        resp = await client.get(
            "/ingestion/sources?cursor=not!base64",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        results["11_ingestion_malformed_cursor"] = _summarise(resp)

    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
