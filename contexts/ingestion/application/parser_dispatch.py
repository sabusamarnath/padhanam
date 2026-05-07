"""Parser dispatch — pure file-type and extension routing (D61).

This module is pure application-layer code: it knows the supported
file_type tag space and the extension-to-file-type map, both
derived from D61's parsing scope. It does NOT construct adapters
— that responsibility belongs to the adapter-layer registry at
``contexts/ingestion/adapters/outbound/parsers/__init__.py``,
which the worker imports for composition.

Splitting the responsibility this way preserves the hexagonal-
layers contract: application code never imports from adapters.
The worker's composition layer is the only caller that crosses
both seams: it asks the application layer "is this file_type
supported?" and asks the adapter registry "give me the parser for
file_type X".

Adding a new format at S20+ touches three places:
  1. The parser adapter at ``adapters/outbound/parsers/``.
  2. ``SUPPORTED_FILE_TYPES`` and ``EXTENSION_TO_FILE_TYPE`` here.
  3. The adapter registry's get_parser dispatch.
The schema CHECK on ``sources.file_type`` extends in the same
migration as (1).
"""

from __future__ import annotations


SUPPORTED_FILE_TYPES: frozenset[str] = frozenset({"markdown", "text"})

EXTENSION_TO_FILE_TYPE: dict[str, str] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".text": "text",
}


def file_type_for_extension(extension: str) -> str | None:
    """Return the canonical file_type for a file-name extension, or
    None when no parser handles the extension. The CLI surface
    uses this to validate uploads before they hit the database.
    """
    return EXTENSION_TO_FILE_TYPE.get(extension.lower())


def is_supported_file_type(file_type: str) -> bool:
    """True iff a parser adapter exists for ``file_type``. The
    register-source use case calls this as the upload-time
    validation gate per D61.
    """
    return file_type in SUPPORTED_FILE_TYPES
