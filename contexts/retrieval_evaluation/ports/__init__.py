"""Retrieval evaluation ports layer (D17 consumer-defined-ports pattern)."""

from contexts.retrieval_evaluation.ports.reader import (
    GoldSetListPage,
    GoldSetReader,
    GoldSetWithCurrentRevision,
    RevisionWithEntries,
)
from contexts.retrieval_evaluation.ports.repository import GoldSetRepository

__all__ = [
    "GoldSetListPage",
    "GoldSetReader",
    "GoldSetRepository",
    "GoldSetWithCurrentRevision",
    "RevisionWithEntries",
]
