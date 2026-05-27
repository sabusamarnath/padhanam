"""Messaging application-layer consumer ports (S46).

- ``PortfolioGateway`` at ``portfolio_gateway.py`` — the manual entry
  cell's single seam to the portfolio context (resolution reads plus
  the three intake-canonical orchestration writes).
- ``BroadcastDispatch`` at ``broadcast_dispatch.py`` (D143, S53) — the
  trigger-driven dispatch port symmetric to ``CellDispatch``.
- ``BroadcastFlowRegistry`` at ``broadcast_flow_registry.py`` (D143,
  S53) — the composition-root surface for BroadcastFlow implementer
  registration.
"""

from contexts.messaging.application.ports.broadcast_dispatch import (
    BroadcastDispatch,
    NoRegisteredBroadcastImplementerError,
)
from contexts.messaging.application.ports.broadcast_flow_registry import (
    BroadcastFlowRegistry,
)
from contexts.messaging.application.ports.channel_resolver import (
    ChannelResolver,
)
from contexts.messaging.application.ports.portfolio_gateway import (
    CaseSummary,
    CaseWriteOutcome,
    DataPointSummary,
    DataPointWriteOutcome,
    PortfolioGateway,
)

__all__ = [
    "BroadcastDispatch",
    "BroadcastFlowRegistry",
    "CaseSummary",
    "CaseWriteOutcome",
    "ChannelResolver",
    "DataPointSummary",
    "DataPointWriteOutcome",
    "NoRegisteredBroadcastImplementerError",
    "PortfolioGateway",
]
