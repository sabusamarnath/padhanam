"""ChannelType enum — the messaging channel discriminator (D144, S53).

Phase 2-A registers a single value (``WHATSAPP``); SLACK, EMAIL, and
future channels defer to the second-channel activation trigger at
D136 Primitive 1 (User aggregate root + per-user channel preference).
The enum extension is additive — existing code paths absorbing the
addition without restructuring per the principle of forward-
compatible discriminator unions.

Lives at shared_kernel rather than ``contexts/messaging/`` because
``padhanam/config/messaging.py`` references the type at the
MessagingSettings ``operator_default_channel`` field, and the
``platform`` ⇸ ``contexts`` import-linter contract forbids
``padhanam.config`` from importing ``contexts``. Cross-context value
references that any non-context surface (config, shared_kernel) needs
to reference live at shared_kernel per the MessageIntent precedent
at the same session. The ChannelResolver Protocol at
``contexts/messaging/application/ports/channel_resolver.py`` and the
ChannelDestination value object at
``contexts/messaging/domain/channel_destination.py`` continue to live
inside the messaging context — only the discriminator enum lifts to
shared_kernel.

Framework-free per D16 — shared_kernel is policed; stdlib only.
"""

from __future__ import annotations

from enum import StrEnum


class ChannelType(StrEnum):
    """The set of messaging channels Padhanam can route outbound through.

    Phase 2-A registers ``WHATSAPP`` only. Future channels register
    additively at second-channel activation; the ChannelResolver
    Protocol (D144) consults this enum to discriminate outbound
    routing.
    """

    WHATSAPP = "whatsapp"


__all__ = ["ChannelType"]
