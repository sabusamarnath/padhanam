"""Portfolio application layer (D124, D125).

Use cases orchestrating the Case aggregate:

- ``create_case`` at ``create_case.py`` — mint and persist a Case.
- ``create_data_point`` at ``create_data_point.py`` — create a
  DataPoint with its INITIAL assertion.
- ``revise_data_point`` at ``revise_data_point.py`` — apply the
  Revisable Protocol, appending a REVISION assertion.
- ``list_cases`` at ``list_cases.py`` — the paginated read surface.
- ``get_case_detail`` at ``get_case_detail.py`` — a Case plus its
  DataPoints (the ``CaseDetail`` composite).

Supporting modules: ``cursor.py`` (the ``CaseListCursor`` base64
codec) and ``audit_events.py`` (draft audit-event helpers — every
write emits an audit event per D110 commitment 7).

Use cases consume the ports by interface; no direct adapter
coupling. Each validates inputs, persists through the repository,
and emits an audit event.
"""

from contexts.portfolio.application.create_case import create_case
from contexts.portfolio.application.create_data_point import (
    create_data_point,
)
from contexts.portfolio.application.get_case_detail import (
    CaseDetail,
    get_case_detail,
)
from contexts.portfolio.application.list_cases import list_cases
from contexts.portfolio.application.revise_data_point import (
    DataPointNotFoundError,
    revise_data_point,
)

__all__ = [
    "CaseDetail",
    "DataPointNotFoundError",
    "create_case",
    "create_data_point",
    "get_case_detail",
    "list_cases",
    "revise_data_point",
]
