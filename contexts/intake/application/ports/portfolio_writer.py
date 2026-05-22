"""PortfolioWriter consumer port (D127 alternative (e), S44b).

The intake context's consumer-side port for driving a portfolio
write from an intake-canonical orchestration. Per the D16/D17/D28
cross-context contract the intake application layer cannot import
``contexts.portfolio`` directly; it defines the shape it needs here,
and the ``apps/`` composition layer provides the adapter that
invokes ``contexts.portfolio.application`` use cases.

This module imports nothing from ``contexts.portfolio`` — the result
DTOs are intake-context-owned, mirroring the producer's output at
the type level. The structural duplication is the intentional cost
of the D17 boundary; the wiring adapter does field-for-field
translation. The shape follows the consumer-port-plus-wiring-adapter
precedent at ``contexts/agent/application/ports/run_history_writer.py``.

Ports layer is pure per D16 — stdlib plus shared_kernel only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from shared_kernel import ActorContext


@dataclass(frozen=True)
class CaseWriteResult:
    """Intake-owned mirror of a portfolio Case write (D127).

    Carries the fields the orchestration's caller — the HTTP route or
    the CLI — needs to render a response. ``intake_id`` is the
    IntakeRecord the Case traces to per D128.
    """

    case_id: UUID
    tenant_id: UUID
    jurisdiction: str
    title: str
    case_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    intake_id: UUID


@dataclass(frozen=True)
class DataPointWriteResult:
    """Intake-owned mirror of a portfolio DataPoint write (D127).

    Serves both the create-data-point and revise-data-point
    orchestrations. ``assertion_ids`` is the DataPoint's full
    revision chain in chronological order — the caller derives the
    INITIAL id (``[0]``), the latest id (``[-1]``), and the revision
    count (``len``). ``intake_id`` is the IntakeRecord the most
    recent write traces to per D128.
    """

    data_point_id: UUID
    case_id: UUID
    data_point_type: str
    current_value: dict[str, Any]
    assertion_ids: tuple[UUID, ...]
    intake_id: UUID


class PortfolioWriter(Protocol):
    """Consumer port: drive a portfolio write from an intake orchestration.

    Each method carries the request-scoped ActorContext through to
    the portfolio use case (which re-checks authorisation at its own
    decorator) and the ``intake_id`` the orchestration recorded. The
    wiring adapter at ``apps/`` implements this Protocol by invoking
    ``contexts.portfolio.application`` use cases and translating their
    domain aggregates into the result DTOs above.
    """

    async def create_case(
        self,
        *,
        actor: ActorContext,
        title: str,
        intake_id: UUID,
    ) -> CaseWriteResult:
        """Create a Case carrying ``intake_id``; Phase 2-A defaults
        ``case_type`` to PORTFOLIO_ITEM and ``status`` to OPEN."""
        ...

    async def create_data_point(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        data_point_type: str,
        value: dict[str, Any],
        intake_id: UUID,
    ) -> DataPointWriteResult:
        """Create a DataPoint whose INITIAL assertion carries ``intake_id``."""
        ...

    async def revise_data_point(
        self,
        *,
        actor: ActorContext,
        data_point_id: UUID,
        value: dict[str, Any],
        intake_id: UUID,
    ) -> DataPointWriteResult:
        """Append a REVISION assertion carrying ``intake_id``."""
        ...


__all__ = ["CaseWriteResult", "DataPointWriteResult", "PortfolioWriter"]
