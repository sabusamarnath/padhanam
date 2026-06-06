"""Daily-driver settings — the drop-candidate quiet window (D162).

Platform-level config for the daily driver's expected-versus-observed
loop. ``drop_candidate_quiet_days`` is the threshold N: an open,
not-yet-dropped Commitment with no progress (no completion and no
observation) for at least N days is surfaced as a drop-candidate
recommendation on the Today surface. It is a recommendation only — the
operator acts, the platform never auto-drops (D162, the no-auto-deletion
invariant).

The default 21 is a deliberately long window (longer than typical
commitment intervals) so the nudge marks genuinely-gone-quiet items, not
merely-behind ones; the dogfooding week tunes it via configuration. The
env var ``DROP_CANDIDATE_QUIET_DAYS`` overrides it (e.g. a small value so
the smoke can exercise the nudge without waiting weeks).

Read through this Settings subclass only — no module reads .env or calls
os.getenv directly (D19, enforced by import-linter).
"""

from __future__ import annotations

from padhanam.config.base import PadhanamSettings


class DailyDriverSettings(PadhanamSettings):
    """Daily-driver tunables (D162)."""

    # Quiet-window threshold N for the drop-candidate recommendation.
    drop_candidate_quiet_days: int = 21
