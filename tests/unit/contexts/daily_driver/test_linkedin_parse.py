"""S103v/D223: the LinkedIn self-export parser — pinned to the reconciled archive
layout (the 3-4-line Notes preamble, the Connections.csv columns, the messages.csv
FROM column). If LinkedIn drifts the layout, this test is where the delta shows."""

from __future__ import annotations

import os
import tempfile

from contexts.daily_driver.domain.linkedin_parse import (
    parse_connections_csv,
    parse_messages_csv,
)
from ops.linkedin_archive_source import SelfExportArchiveSource

# The reconciled Connections.csv: LinkedIn writes a 3-line "Notes:" preamble before
# the header row; the real Company is a column (unlike the email seed).
_CONNECTIONS = (
    "Notes:\n"
    '"When exporting your connection data, you may notice that some of the'
    ' email addresses are missing. You will only see email addresses for'
    ' connections who have allowed their connections to see or download their'
    ' email address using this setting..."\n'
    "\n"
    "First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
    "Jane,Doe,https://www.linkedin.com/in/janedoe,,Acme,VP Product,01 Jan 2024\n"
    "Bob,Smith,https://www.linkedin.com/in/bobsmith,bob@bs.com,Globex Legal,Partner,02 Feb 2024\n"
    ",,,,,,\n"  # a blank-name row is skipped
)
# The reconciled messages.csv: the FROM column is the sender's display name.
_MESSAGES = (
    "CONVERSATION ID,CONVERSATION TITLE,FROM,SENDER PROFILE URL,TO,DATE,SUBJECT,CONTENT\n"
    "c1,,Yuki Tanaka,https://x,Me,2024-01-01,,hi\n"
    "c1,,Yuki Tanaka,https://x,Me,2024-01-02,,again\n"  # dup sender collapses to one
    "c2,,Priya Patel,https://y,Me,2024-02-01,,hello\n"
)


def test_connections_skip_preamble_read_name_and_company():
    conns = parse_connections_csv(_CONNECTIONS)
    assert [c.name for c in conns] == ["Jane Doe", "Bob Smith"]  # blank row skipped
    assert conns[0].company == "Acme" and conns[0].degree == "first"
    assert conns[1].company == "Globex Legal"
    assert all(c.kind == "connection" for c in conns)


def test_connections_no_header_yields_nothing():
    assert parse_connections_csv("garbage,without,a,header\n1,2,3,4\n") == ()


def test_messages_distinct_senders_from_column():
    msgs = parse_messages_csv(_MESSAGES)
    assert [m.name for m in msgs] == ["Yuki Tanaka", "Priya Patel"]  # deduped
    assert all(m.kind == "message" and m.company is None and m.degree is None for m in msgs)


def test_headers_are_case_insensitive():
    lower = _CONNECTIONS.replace(
        "First Name,Last Name,URL,Email Address,Company,Position,Connected On",
        "first name,last name,url,email address,company,position,connected on",
    )
    conns = parse_connections_csv(lower)
    assert conns[0].name == "Jane Doe" and conns[0].company == "Acme"


def test_self_export_adapter_reads_directory():
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "Connections.csv"), "w") as f:
        f.write(_CONNECTIONS)
    with open(os.path.join(d, "messages.csv"), "w") as f:
        f.write(_MESSAGES)
    loaded = SelfExportArchiveSource(d).load()
    kinds = {c.kind for c in loaded}
    assert kinds == {"connection", "message"}
    assert len(loaded) == 4  # 2 connections + 2 message senders


def test_self_export_adapter_missing_files_yield_empty():
    d = tempfile.mkdtemp()
    assert SelfExportArchiveSource(d).load() == ()
