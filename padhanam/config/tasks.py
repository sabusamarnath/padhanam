"""Task integration settings — how Padhanam reaches the Nango tool service (D167).

Platform-level config for the tasks context's Nango Proxy adapter: the base URL
and dashboard secret key (the same self-hosted Nango that serves google-calendar
and google-mail; these read the same ``NANGO_BASE_URL`` / ``NANGO_SECRET_KEY``
env, mirroring EmailSettings, with tasks keeping its own subclass per
bounded-context independence), plus the google-tasks integration key and the
operator-provisioned connection reference used by the ops pull.

Secrets enter through this Settings subclass only — no module reads .env or calls
os.getenv directly (D19, enforced by import-linter).
"""

from __future__ import annotations

from padhanam.config.base import PadhanamSettings


class TasksSettings(PadhanamSettings):
    """Nango Proxy reach + auth + the google-tasks connection for the tasks context (D167)."""

    nango_base_url: str = "http://localhost:3003"
    nango_secret_key: str = ""
    # The Nango integration key for Google Tasks (the operator provisions a
    # `google-tasks` integration with the tasks.readonly scope).
    tasks_provider_config_key: str = "google-tasks"
    # The opaque Nango connection reference the operator obtains after the
    # OAuth connect; empty until provisioned (the ops pull errors clearly then).
    tasks_connection_ref: str = ""
