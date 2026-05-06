"""Interaction domain entities (D53).

An ``InteractionSet`` is a named collection of test inputs. Each
``Interaction`` is one input with optional expected output and an
ordering position within the set. ``input`` and ``expected_output``
are jsonb-shaped at the schema layer per the framing-level commitment
to flexibility across text prompts, structured payloads, and future
agent-trajectory inputs; the domain carries them as plain dicts so the
domain stays framework-free per D16.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class InteractionSet:
    id: UUID
    name: str
    description: str
    created_by_user_id: str
    created_at: datetime


@dataclass(frozen=True)
class Interaction:
    id: UUID
    interaction_set_id: UUID
    input: dict[str, Any]
    expected_output: dict[str, Any] | None
    ordering: int
    created_at: datetime
