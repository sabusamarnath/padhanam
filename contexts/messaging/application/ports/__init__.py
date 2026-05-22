"""Messaging application-layer consumer ports (S46).

- ``PortfolioGateway`` at ``portfolio_gateway.py`` — the manual entry
  cell's single seam to the portfolio context (resolution reads plus
  the three intake-canonical orchestration writes).
"""

from contexts.messaging.application.ports.portfolio_gateway import (
    CaseSummary,
    CaseWriteOutcome,
    DataPointSummary,
    DataPointWriteOutcome,
    PortfolioGateway,
)

__all__ = [
    "CaseSummary",
    "CaseWriteOutcome",
    "DataPointSummary",
    "DataPointWriteOutcome",
    "PortfolioGateway",
]
