"""NangoProxyGoogleContactsSource — the Google Contacts adapter (S103x, D230).

Implements the `ContactSource` port by fetching the operator's contacts through
self-hosted Nango's Proxy over HTTP (the NangoProxyTaskAdapter/D167 pattern), reusing
the connected Google provider with an added ``contacts.readonly`` scope. The only
place that speaks the People API wire format or Nango Proxy's headers; no vendor SDK
in domain (D4/D16). Read-only — it never writes to any Google surface.

Reconciled against the People API (current Google docs, 2026-07):
  - endpoint:  ``GET /proxy/v1/people/me/connections`` (people.connections.list)
  - fields:    ``personFields=names,emailAddresses,organizations`` (org = company)
  - paging:    ``pageToken`` / ``nextPageToken``, ``pageSize`` (max 1000)
  - scope:     ``https://www.googleapis.com/auth/contacts.readonly``

Consent: the live Google connector holds calendar/gmail/tasks but NOT a contacts
scope, so this runs only after the operator adds ``contacts.readonly`` to the Nango
Google integration and re-authorises (operator-gated, surfaced in the seed).
"""

from __future__ import annotations

from typing import Any

import httpx

from contexts.daily_driver.domain.google_contacts_parse import (
    parse_people_connections,
)
from contexts.daily_driver.ports.contact_source import SourcedContact

_PERSON_FIELDS = "names,emailAddresses,organizations"
_PAGE_SIZE = 1000
_TIMEOUT = 30.0


class GoogleContactsError(RuntimeError):
    """The People API proxy request failed."""


class NangoProxyGoogleContactsSource:
    """ContactSource over Nango Proxy → Google People API (D230)."""

    def __init__(
        self,
        *,
        base_url: str,
        secret_key: str,
        provider_config_key: str,
        connection_id: str,
        client: httpx.AsyncClient | None = None,
        page_size: int = _PAGE_SIZE,
        timeout: float = _TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret_key = secret_key
        self._provider_config_key = provider_config_key
        self._connection_id = connection_id
        self._client = client
        self._owns_client = client is None
        self._page_size = page_size
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Provider-Config-Key": self._provider_config_key,
            "Connection-Id": self._connection_id,
        }

    async def load(self) -> tuple[SourcedContact, ...]:
        connections: list[dict] = []
        page_token: str | None = None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            while True:
                params: dict[str, str] = {
                    "personFields": _PERSON_FIELDS,
                    "pageSize": str(self._page_size),
                }
                if page_token:
                    params["pageToken"] = page_token
                body = await self._get(client, params)
                connections.extend(body.get("connections", []) or [])
                page_token = body.get("nextPageToken")
                if not page_token:
                    break
        finally:
            if self._owns_client:
                await client.aclose()
        return parse_people_connections(connections)

    async def _get(
        self, client: httpx.AsyncClient, params: dict[str, str]
    ) -> dict[str, Any]:
        url = f"{self._base_url}/proxy/v1/people/me/connections"
        try:
            response = await client.get(url, params=params, headers=self._headers())
        except httpx.HTTPError as exc:
            raise GoogleContactsError(f"people proxy request failed: {exc}") from exc
        if response.status_code == 200:
            return response.json()
        raise GoogleContactsError(
            f"people proxy returned {response.status_code}: {response.text[:500]}"
        )


__all__ = ["GoogleContactsError", "NangoProxyGoogleContactsSource"]
