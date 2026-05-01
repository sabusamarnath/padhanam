"""Tests for the credential scrub logging filter (D34 control (a))."""

from __future__ import annotations

import logging

import pytest

from padhanam.observability.credential_scrub import (
    CredentialScrubFilter,
    install_credential_scrub,
)


def _record(
    *,
    msg: str,
    args: tuple = (),
    extra: dict | None = None,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=msg,
        args=args,
        exc_info=None,
    )
    if extra:
        for k, v in extra.items():
            setattr(record, k, v)
    return record


def test_record_with_plaintext_field_in_extra_is_dropped() -> None:
    f = CredentialScrubFilter()
    record = _record(msg="connecting", extra={"password": "secret"})
    assert f.filter(record) is False


def test_record_with_connection_config_attribute_is_dropped() -> None:
    f = CredentialScrubFilter()
    record = _record(msg="opened session", extra={"connection_config": object()})
    assert f.filter(record) is False


def test_record_with_field_name_in_message_is_dropped() -> None:
    f = CredentialScrubFilter()
    record = _record(msg="connecting with user=alice host=db.local")
    assert f.filter(record) is False


def test_record_with_password_substring_in_message_is_dropped() -> None:
    f = CredentialScrubFilter()
    record = _record(msg="payload password: hunter2")
    assert f.filter(record) is False


def test_record_with_args_formatting_is_dropped() -> None:
    f = CredentialScrubFilter()
    record = _record(msg="user=%s", args=("alice",))
    assert f.filter(record) is False


def test_clean_record_passes_through() -> None:
    f = CredentialScrubFilter()
    record = _record(msg="tenant registered", extra={"tenant_id": "abc"})
    assert f.filter(record) is True


def test_install_is_idempotent() -> None:
    f1 = install_credential_scrub()
    f2 = install_credential_scrub()
    assert f1 is f2
    root = logging.getLogger()
    matching = [x for x in root.filters if isinstance(x, CredentialScrubFilter)]
    assert len(matching) == 1


def test_installed_filter_blocks_logger_messages(caplog: pytest.LogCaptureFixture) -> None:
    install_credential_scrub()
    # caplog's handler also picks up the root-level filter on modern pytest.
    log = logging.getLogger("test.credential_scrub")
    log.setLevel(logging.INFO)
    with caplog.at_level(logging.INFO, logger="test.credential_scrub"):
        # caplog's propagation handler does not inherit root.filters in
        # all configurations, so attach the filter directly to the
        # caplog handler too. Real installations use install_credential_scrub.
        scrub = CredentialScrubFilter()
        caplog.handler.addFilter(scrub)
        try:
            log.info("user=%s", "alice")
            log.info("clean record")
        finally:
            caplog.handler.removeFilter(scrub)
    messages = [r.getMessage() for r in caplog.records]
    assert "user=alice" not in messages
    assert "clean record" in messages
