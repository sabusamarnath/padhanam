"""The lever-aware confirm echo (D192, S97b).

A goal-level reply ("did my meds") maps to all of a multi-lever goal's levers,
which would silently fabricate dids on partial completion — the moat-lying the
completion arc exists to prevent. So the confirm echo summarises a multi-lever
goal at the **count level** ("Health regimen: all 4 done", "Health regimen: 3
done, 1 not done") and invites correction ("or tell me which you missed"),
exposing the over-read without ever enumerating the clinical lever names on the
channel. A single-lever goal reads plainly ("Litany: done"). Silence on a whole
goal omits it entirely (nothing is written, so nothing is echoed).

The echo previews exactly what the write will persist: a ``did`` and a
``reported_didnt`` are both shown; an unmentioned (silent) lever is not.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from contexts.checkin.domain.lever import EligibleLever
from contexts.checkin.domain.outcome import CheckinState, ParsedLeverOutcome


def build_confirm_echo(
    *,
    levers: tuple[EligibleLever, ...],
    parsed: tuple[ParsedLeverOutcome, ...],
) -> str:
    """Build the declarative confirm summary the cell echoes before writing."""
    state_by_id = {p.commitment_id: p.state for p in parsed}

    # Group levers by goal, first-seen order.
    order: list = []
    levers_by_goal: dict = {}
    for lever in levers:
        if lever.goal_id not in levers_by_goal:
            levers_by_goal[lever.goal_id] = (lever.goal_name, [])
            order.append(lever.goal_id)
        levers_by_goal[lever.goal_id][1].append(lever)

    lines: list[str] = []
    for goal_id in order:
        goal_name, goal_levers = levers_by_goal[goal_id]
        spoken = [
            state_by_id[lv.commitment_id]
            for lv in goal_levers
            if lv.commitment_id in state_by_id
        ]
        if not spoken:
            continue  # silence on the whole goal — nothing to confirm or write
        total = len(goal_levers)
        dids = sum(1 for s in spoken if s is CheckinState.DID)
        didnts = sum(1 for s in spoken if s is CheckinState.REPORTED_DIDNT)
        if total == 1:
            lines.append(
                f"• {goal_name}: {'done' if dids == 1 else 'not done'}"
            )
            continue
        # Multi-lever goal — count level only, never the clinical lever names.
        parts: list[str] = []
        if dids:
            parts.append(f"all {total} done" if dids == total else f"{dids} done")
        if didnts:
            parts.append(f"{didnts} not done")
        lines.append(f"• {goal_name}: {', '.join(parts)}")

    body = "\n".join(lines)
    return (
        "Logging today:\n"
        f"{body}\n"
        "Reply yes to confirm, or tell me which you missed."
    )


__all__ = ["build_confirm_echo"]
