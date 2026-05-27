"""ChannelType re-export from shared_kernel (D144, S53).

Pre-write reconciliation Finding A (build-mode): the brief committed
ChannelType at ``contexts/messaging/domain/channel_type.py`` but the
``platform → contexts`` import-linter contract forbids
``padhanam.config.messaging`` from importing ``contexts.messaging``.
The canonical home moved to ``shared_kernel/channel_type.py``;
messaging-context callers continue to import the messaging-domain
path so the existing module structure stays stable. The re-export
mirrors the symmetric arrangement at MessageIntent (sourced from
shared_kernel; not duplicated at messaging.domain).

Domain layer per D16 — stdlib only, no vendor SDK imports.
"""

from __future__ import annotations

from shared_kernel.channel_type import ChannelType

__all__ = ["ChannelType"]
