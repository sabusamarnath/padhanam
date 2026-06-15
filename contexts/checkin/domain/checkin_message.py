"""The daily check-in prompt message (D192, S97b).

Goal-level and declarative — lists the eligible goals (a multi-lever goal like
Health regimen appears once, by goal name, keeping its clinical lever names off
the channel) and invites a free reply. No compliance language: it primes, it
does not pressure (the private-assistant communication discipline).

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from contexts.checkin.domain.lever import EligibleLever, goal_labels


def build_checkin_message(levers: tuple[EligibleLever, ...]) -> str:
    """Compose the goal-level check-in prompt for the eligible levers."""
    labels = goal_labels(levers)
    return (
        "Quick check on today: "
        + ", ".join(labels)
        + ". What did you get to?"
    )


__all__ = ["build_checkin_message"]
