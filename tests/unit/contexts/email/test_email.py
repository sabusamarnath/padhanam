"""Unit tests for the Email artefact + no-plaintext-at-rest (D151, D21)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from padhanam.security import crypto

from contexts.email.adapters.outbound.postgres.email_store import _CONTENT_FIELD, _aad
from contexts.email.domain.email import (
    Email,
    email_from_message,
    serialize_email_content,
    synthesise_email_text,
)
from contexts.email.domain.email_message import EmailMessage

_TENANT = uuid4()
_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)

_SECRET_SUBJECT = "Project Falcon merger terms"
_SECRET_BODY = "We will acquire Acme for 50M; keep this confidential."
_SECRET_FROM = "ceo@acme-target.example"


def _email() -> Email:
    return Email(
        id=uuid4(),
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        message_id="msg-1",
        thread_id="thr-1",
        from_address=_SECRET_FROM,
        to_addresses=("me@example.com",),
        cc_addresses=("ea@example.com",),
        subject=_SECRET_SUBJECT,
        body=_SECRET_BODY,
        snippet="We will acquire Acme",
        received_at=_NOW,
        labels=("INBOX",),
        history_id="555",
        content_hash="h",
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_email_from_message_maps_and_hashes() -> None:
    msg = EmailMessage(
        google_message_id="msg-9",
        thread_id="thr-9",
        from_address="a@x.com",
        to_addresses=("b@x.com",),
        cc_addresses=(),
        subject="Hello",
        body="Body text",
        snippet="Body",
        received_at=_NOW,
        labels=("INBOX",),
        history_id="42",
    )
    e = email_from_message(msg, tenant_id=_TENANT, jurisdiction="eu-west", email_id=uuid4(), now=_NOW)
    assert e.message_id == "msg-9"
    assert e.content_hash is not None and len(e.content_hash) == 64
    assert e.to_search_text() == synthesise_email_text(subject="Hello", body="Body text")


def test_serialized_content_encrypts_with_no_plaintext_and_round_trips() -> None:
    """The at-rest payload the store inserts carries no plaintext sensitive content."""
    email = _email()
    plaintext = serialize_email_content(email)
    enc = crypto.encrypt_field(plaintext, _aad(email.tenant_id, _CONTENT_FIELD))

    # The ciphertext (what lands in enc_ciphertext at rest) leaks no secret.
    for secret in (_SECRET_SUBJECT, _SECRET_BODY, _SECRET_FROM):
        assert secret.encode("utf-8") not in enc.ciphertext

    # And it decrypts back to the original content (recoverable evidence).
    recovered = json.loads(crypto.decrypt_field(enc, _aad(email.tenant_id, _CONTENT_FIELD)).decode("utf-8"))
    assert recovered["subject"] == _SECRET_SUBJECT
    assert recovered["body"] == _SECRET_BODY
    assert recovered["from_address"] == _SECRET_FROM
    assert recovered["to_addresses"] == ["me@example.com"]


def test_is_deleted_flag() -> None:
    e = _email()
    assert e.is_deleted is False
    from dataclasses import replace

    assert replace(e, deleted_at=_NOW).is_deleted is True
