"""Messaging domain layer (D129).

- ``Message`` (aggregate root) at ``message.py`` — one inbound or
  outbound communication on a channel, with the ``MessageDirection``,
  ``MessageChannel``, and ``MessageStatus`` enums.

Domain code is framework-free per D16 — stdlib plus shared_kernel.
"""

from contexts.messaging.domain.message import (
    Message,
    MessageChannel,
    MessageDirection,
    MessageStatus,
)

__all__ = [
    "Message",
    "MessageChannel",
    "MessageDirection",
    "MessageStatus",
]
