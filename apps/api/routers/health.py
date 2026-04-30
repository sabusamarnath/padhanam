"""GET /health — operator probe.

Public (the auth middleware exempts it explicitly). No tenant scope,
no side effects. Intentionally trivial: any non-trivial check belongs
in a /readyz endpoint that can fail independently.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
