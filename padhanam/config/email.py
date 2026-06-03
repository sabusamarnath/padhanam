"""Email integration settings — how Padhanam reaches the Nango tool service (D151).

Platform-level config for the email context's Nango Proxy adapter: the
base URL Padhanam uses to reach Nango's Proxy and the dashboard secret key
it authenticates with. The same self-hosted Nango instance serves both the
google-calendar and google-mail providers, so these read the same
``NANGO_BASE_URL`` / ``NANGO_SECRET_KEY`` env as CalendarSettings; email
keeps its own Settings subclass per bounded-context independence rather
than importing calendar's config.

Secrets enter through this Settings subclass only — no module reads .env or
calls os.getenv directly (D19, enforced by import-linter).
"""

from __future__ import annotations

from padhanam.config.base import PadhanamSettings


class EmailSettings(PadhanamSettings):
    """Nango Proxy reach + auth for the email context (D151)."""

    nango_base_url: str = "http://localhost:3003"
    nango_secret_key: str = ""
