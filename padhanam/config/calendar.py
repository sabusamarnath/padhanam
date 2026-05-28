"""Calendar integration settings — how Padhanam reaches the Nango tool service (D148).

Platform-level config for the calendar context's Nango Proxy adapter: the
base URL Padhanam uses to reach Nango's Proxy and the dashboard secret
key it authenticates with. These are distinct from the per-tenant
Connection (provider_config_key + opaque connection reference), which is
domain data stored in the tenant store, not config.

Secrets enter through this Settings subclass only — no module reads .env
or calls os.getenv directly (D19, enforced by import-linter). In dev,
``nango_base_url`` equals the ``NANGO_SERVER_URL`` the Nango server
advertises; production points it at the internal service URL.
"""

from __future__ import annotations

from padhanam.config.base import PadhanamSettings


class CalendarSettings(PadhanamSettings):
    """Nango Proxy reach + auth for the calendar context (D148)."""

    # URL Padhanam uses to reach Nango Proxy. Dev default matches the
    # self-hosted compose service (SERVER_PORT 3003).
    nango_base_url: str = "http://localhost:3003"
    # Nango dashboard secret key used as the Proxy bearer token. Empty in
    # the example env; the operator pastes the dashboard secret. Resolved
    # by the production secret manager in deployed environments.
    nango_secret_key: str = ""
