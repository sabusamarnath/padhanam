"""Portfolio ports layer (D124).

Two consumer-defined persistence Protocols:

- ``PortfolioRepository`` (write side) at ``portfolio_repository.py``.
- ``PortfolioReader`` (read side) at ``portfolio_reader.py``, plus the
  ``CaseListPage`` result type.

Ports are pure per D16 — no SQLAlchemy, no asyncpg.
"""

from contexts.portfolio.ports.portfolio_reader import (
    CaseListPage,
    PortfolioReader,
)
from contexts.portfolio.ports.portfolio_repository import PortfolioRepository

__all__ = ["CaseListPage", "PortfolioReader", "PortfolioRepository"]
