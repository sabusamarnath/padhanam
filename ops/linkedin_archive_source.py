"""SelfExportArchiveSource — the built LinkedIn source adapter (S103v, D223).

Implements ``LinkedInSource`` by reading the member's self-export archive — a zip
(as downloaded) or an already-unzipped directory — and parsing ``Connections.csv``
and ``messages.csv`` with the pure parsers. Read-only; never writes to LinkedIn.
File lookup is case-insensitive and recursive (LinkedIn nests files across
releases). A missing file yields no contacts from that file, logged by the seed.
"""

from __future__ import annotations

import os
import zipfile

from contexts.daily_driver.domain.linkedin_parse import (
    LinkedInContact,
    parse_connections_csv,
    parse_messages_csv,
)
from contexts.daily_driver.ports.linkedin_source import LinkedInSource

_CONNECTIONS = "connections.csv"
_MESSAGES = "messages.csv"


class SelfExportArchiveSource(LinkedInSource):
    def __init__(self, archive_path: str) -> None:
        self._path = archive_path

    def _read_member(self, basename: str) -> str | None:
        """Read a named file (case-insensitive) from the zip or directory, or None."""
        want = basename.lower()
        if zipfile.is_zipfile(self._path):
            with zipfile.ZipFile(self._path) as zf:
                for name in zf.namelist():
                    if os.path.basename(name).lower() == want:
                        return zf.read(name).decode("utf-8", errors="replace")
            return None
        if os.path.isdir(self._path):
            for root, _dirs, files in os.walk(self._path):
                for f in files:
                    if f.lower() == want:
                        with open(
                            os.path.join(root, f), encoding="utf-8", errors="replace"
                        ) as fh:
                            return fh.read()
            return None
        # a single file path — treat it as the connections file if it matches
        if os.path.isfile(self._path) and os.path.basename(self._path).lower() == want:
            with open(self._path, encoding="utf-8", errors="replace") as fh:
                return fh.read()
        return None

    def load(self) -> tuple[LinkedInContact, ...]:
        connections = parse_connections_csv(self._read_member(_CONNECTIONS) or "")
        messages = parse_messages_csv(self._read_member(_MESSAGES) or "")
        return connections + messages


__all__ = ["SelfExportArchiveSource"]
