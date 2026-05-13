"""Run-history application layer (D17, D95).

Use cases land at S31 commit 3 (the ``record_run`` writer-side use
case). The application layer re-exports those callables so the
``api.py`` facade has a single surface to re-export per D17.
"""
