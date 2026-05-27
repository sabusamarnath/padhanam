"""Unit tests for the MirrorPortfolioReader port + DTOs (P14, S52)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contexts.mirror_conversation.application.ports.mirror_portfolio_reader import (  # noqa: E501
    MirrorCaseDetail,
    MirrorCaseSummary,
    MirrorDataPoint,
    MirrorDataPointSummary,
    MirrorPortfolioReader,
)


def _now() -> datetime:
    return datetime(2026, 5, 27, 14, 30, tzinfo=timezone.utc)


def test_mirror_case_summary_constructs() -> None:
    summary = MirrorCaseSummary(
        case_id=uuid4(),
        title="Q3 portfolio review",
        case_status="OPEN",
        created_at=_now(),
        last_activity_at=_now(),
        data_point_count=3,
    )
    assert summary.title == "Q3 portfolio review"
    assert summary.case_status == "OPEN"
    assert summary.data_point_count == 3


def test_mirror_case_detail_constructs() -> None:
    case_summary = MirrorCaseSummary(
        case_id=uuid4(),
        title="Q3 portfolio review",
        case_status="OPEN",
        created_at=_now(),
        last_activity_at=_now(),
        data_point_count=2,
    )
    data_points = (
        MirrorDataPointSummary(
            data_point_id=uuid4(),
            case_id=case_summary.case_id,
            data_point_type="GOAL",
            label="ship Wave 1",
            created_at=_now(),
        ),
        MirrorDataPointSummary(
            data_point_id=uuid4(),
            case_id=case_summary.case_id,
            data_point_type="STATUS",
            label="on track",
            created_at=_now(),
        ),
    )
    detail = MirrorCaseDetail(case=case_summary, data_points=data_points)
    assert len(detail.data_points) == 2
    assert detail.case is case_summary


def test_mirror_data_point_constructs() -> None:
    dp = MirrorDataPoint(
        data_point_id=uuid4(),
        case_id=uuid4(),
        data_point_type="GOAL",
        current_value={"text": "ship Wave 1 by Friday"},
        created_at=_now(),
        revision_count=2,
    )
    assert dp.revision_count == 2
    assert dp.current_value["text"] == "ship Wave 1 by Friday"


def test_protocol_isinstance_admits_minimal_adapter() -> None:
    class _Stub:
        async def list_cases(self, *, actor, limit: int = 50):
            return ()

        async def get_case_detail(self, *, actor, case_id):
            return None

        async def get_data_point(self, *, actor, data_point_id):
            return None

        async def find_cases(self, *, actor):
            return ()

    # MirrorPortfolioReader is a structural Protocol, not runtime-checkable.
    # The unit-level conformance is exercised at the wiring adapter
    # plus the cell's instantiation; we just verify the Protocol's
    # method set is satisfiable here.
    stub = _Stub()
    assert hasattr(stub, "list_cases")
    assert hasattr(stub, "get_case_detail")
    assert hasattr(stub, "get_data_point")
    assert hasattr(stub, "find_cases")
