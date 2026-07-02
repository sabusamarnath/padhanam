"""S103x/D230: the Google Contacts feeder — the org-filter parser and the Nango-proxy
People API adapter (pagination + headers)."""

from __future__ import annotations

import asyncio

import httpx

from contexts.daily_driver.domain.google_contacts_parse import (
    parse_people_connections,
)
from ops.google_contacts_source import NangoProxyGoogleContactsSource

_CONNS = [
    {"names": [{"displayName": "Jane Doe"}], "organizations": [{"name": "Acme", "title": "VP"}]},
    {"names": [{"displayName": "Bob Smith"}], "organizations": [{"name": "Globex Legal"}]},
    {"names": [{"displayName": "Mum"}]},                                   # no org -> filtered
    {"names": [{"displayName": "Nick"}], "organizations": [{"title": "Friend"}]},  # org, no name -> filtered
    {"organizations": [{"name": "Acme"}]},                                 # no name -> filtered
]


def test_parser_filters_to_org_carrying_contacts():
    sc = parse_people_connections(_CONNS)
    assert [(c.name, c.company) for c in sc] == [("Jane Doe", "Acme"), ("Bob Smith", "Globex Legal")]


def test_parser_reads_company_from_organizations_directly():
    # unlike the email seed (ATS domains hid the company), the org field is the company
    sc = parse_people_connections([
        {"names": [{"displayName": "X"}], "organizations": [{"name": "Real Co Ltd"}]},
    ])
    assert sc[0].company == "Real Co Ltd"


def test_parser_falls_back_to_given_family_name():
    sc = parse_people_connections([
        {"names": [{"givenName": "Ada", "familyName": "Lovelace"}], "organizations": [{"name": "C"}]},
    ])
    assert sc[0].name == "Ada Lovelace"


def test_adapter_paginates_and_sends_nango_headers():
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        assert "personFields=names" in str(request.url)
        if "pageToken" not in str(request.url):
            return httpx.Response(200, json={"connections": _CONNS[:2], "nextPageToken": "p2"})
        return httpx.Response(200, json={"connections": _CONNS[2:]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    src = NangoProxyGoogleContactsSource(
        base_url="http://nango", secret_key="sk",
        provider_config_key="google-contacts", connection_id="conn1", client=client,
    )
    out = asyncio.run(src.load())
    # both pages fetched, org-filter applied across the union
    assert [(c.name, c.company) for c in out] == [("Jane Doe", "Acme"), ("Bob Smith", "Globex Legal")]
    assert seen_headers["authorization"] == "Bearer sk"
    assert seen_headers["provider-config-key"] == "google-contacts"
    assert seen_headers["connection-id"] == "conn1"


def test_adapter_empty_when_no_connections():
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"connections": []})
    ))
    src = NangoProxyGoogleContactsSource(
        base_url="http://nango", secret_key="sk",
        provider_config_key="google-contacts", connection_id="c", client=client,
    )
    assert asyncio.run(src.load()) == ()


def test_as_channel_list_tolerates_scalar_list_and_null():
    from contexts.ingestion.adapters.outbound.neo4j.graph_repository import _as_channel_list
    assert _as_channel_list("email") == ["email"]
    assert _as_channel_list(["email", "address_book"]) == ["email", "address_book"]
    assert _as_channel_list(None) == []
    assert _as_channel_list(("linkedin",)) == ["linkedin"]
