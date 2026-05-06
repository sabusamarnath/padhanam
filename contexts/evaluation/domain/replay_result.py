"""ReplayResult value object — what the inference port returns.

The replay engine asks an inference port to run a model against an
input and return its text output plus the trace identifier that
links the call to the OTel/Langfuse span the underlying adapter
emitted. The trace_id flows downstream into ``RubricApplication``
records via the new column landed at commit 1 of this session.

Forward-affordance fields (token counts, latency, cost) are not on
the value object at S17a per the S16 discipline-holding shape: they
exist on the trace span the inference adapter emitted, and S17b's
cost-per-successful-task computation reads them through the trace
store rather than through this value object. Putting them here
without an active consumer would be paper architecture; the trace
store is the architectural authority on cost dimensions per D27.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReplayResult:
    output_text: str
    trace_id: str
