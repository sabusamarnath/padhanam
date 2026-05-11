"""Public read-only query interface for the ingestion context (D17).

Cross-context callers (the agent context's
``create_agent_from_methodology`` flow at S25 reading source
existence; the agent runtime at P8 reading retrieved chunks; the
recommendation engine at P11 reading source-level metrics) call
through here. The api facade is the single import target for
cross-context consumers; D17 forbids reaching into
``contexts.ingestion.{domain,application,adapters}`` directly.

S25 adds the first cross-context consumer entry: ``get_source``
exposed for the agent context's source-existence validation at
clone-from-methodology time (D79). The agent context's
``SourceLookup`` adapter at ``apps/cli/_runtime.py`` is the only
caller at P7; the api-facade-via-callable pattern from D17
preserves the consumer-side abstraction while the adapter wraps
this entry.

Surface forecast: a ``RetrievalClient`` port and corresponding read
use cases follow at P8 (agent runtime) and P11 (recommendation
engine) per D5; cross-context consumers import retrieval-shaped
read functions through here once they exist.
"""

from __future__ import annotations

from contexts.ingestion.application.get_source import get_source

__all__ = ["get_source"]
