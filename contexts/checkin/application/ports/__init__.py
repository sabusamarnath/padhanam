"""Check-in consumer ports (D17 seam).

Cross-context reads and writes go through these Protocols; the ``apps/``
composition root supplies the adapters (the eligible-lever traversal over
daily_driver's graph + Postgres, the two-store write, the LLM reply parse).
This context never imports another context's domain across the boundary.
"""
