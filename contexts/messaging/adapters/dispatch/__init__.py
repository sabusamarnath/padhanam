"""Dispatch adapters for the messaging context (D143, S53).

Carries the in-process BroadcastDispatch adapter symmetric to
``apps/api/adapters/cell_dispatch_inprocess.py``. The composition
root selects an adapter; tests substitute synchronous fakes.
"""

from contexts.messaging.adapters.dispatch.in_process_broadcast_dispatch_adapter import (
    InProcessBroadcastDispatchAdapter,
)

__all__ = ["InProcessBroadcastDispatchAdapter"]
