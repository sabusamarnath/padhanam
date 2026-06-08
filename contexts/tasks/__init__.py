"""Tasks bounded context (D167).

The P17 task-ingestion substrate (S65): pull Google Tasks through self-hosted
Nango's Proxy per D14, store each as a ``Task`` keyed on its Google task id (a
D155 external mutable cache: re-pull upserts modified tasks and tombstones
vanished/deleted ones), read-only per assess-not-replace. The third external-
cache ingestion context after calendar (D148) and email (D151); the shared
substrate is owed before the fourth adapter (Trello) per D167.

Hexagonal layers within: domain / ports / application / adapters. No Google or
Nango specifics in domain code. Correlation into units of work (D166) is P18.
"""
