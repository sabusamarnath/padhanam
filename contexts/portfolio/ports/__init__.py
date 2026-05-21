"""Portfolio ports layer (D124).

Consumer-defined persistence Protocols. The write-side
``PortfolioRepository`` and read-side ``PortfolioReader`` ports
land at the S43 application/ports commit. Ports are pure per D16 —
no SQLAlchemy, no asyncpg.
"""
