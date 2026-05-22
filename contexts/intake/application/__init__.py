"""Intake application layer (D127, D128).

Standalone use cases over the IntakeRecord aggregate:

- ``record_intake`` — mint and persist an IntakeRecord.
- ``get_intake`` — single-record read.
- ``list_intakes`` — the paginated read surface.

Orchestration use cases (``record_intake_and_create_case``,
``record_intake_and_create_data_point``,
``record_intake_and_revise_data_point``) compose ``record_intake``
with a portfolio write through the consumer-defined ``PortfolioWriter``
port at ``ports/portfolio_writer.py`` (D127 alternative (e); the
apps/ composition layer provides the adapter).

Supporting modules: ``cursor.py`` (the ``IntakeListCursor`` codec)
and ``audit_events.py`` (the draft audit-event helper).
"""

from contexts.intake.application.get_intake import get_intake
from contexts.intake.application.list_intakes import list_intakes
from contexts.intake.application.record_intake import record_intake
from contexts.intake.application.record_intake_and_create_case import (
    record_intake_and_create_case,
)
from contexts.intake.application.record_intake_and_revise_data_point import (
    record_intake_and_revise_data_point,
)

__all__ = [
    "get_intake",
    "list_intakes",
    "record_intake",
    "record_intake_and_create_case",
    "record_intake_and_revise_data_point",
]
