"""Daily-driver context (D156, D157).

The first instance of the Phase 2 whole-life causal daily driver: a
prioritised-today surface over existing read-surfaces (OPEN Cases) plus
a minimal user-authored ``Commitment`` with render-time staleness. The
context composes the portfolio read-side through a consumer-defined
``OpenCasesReader`` port (the D17 cross-context seam) and owns the
``Commitment`` / completion-log substrate plus the per-day ordering and
done-for-today marks (the minimal Day concept).

Hexagonal per D16 (adapters / application / ports / domain), a plain
package mirroring the portfolio context.
"""
