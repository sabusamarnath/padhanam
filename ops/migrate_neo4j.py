"""Cypher migration runner against the shared Neo4j instance (D63).

Phase 3 of `ops.migrate`. Runs after the per-tenant Postgres phase
(D36) so that any cross-store consumer sees both stores migrated to
their target heads on a successful `make migrate` run.

Migration shape (intentionally lighter than Alembic):

  - Migrations live at ``migrations/neo4j/*.cypher``, one file per
    schema change, sorted lexicographically by file basename. The
    file basename minus the ``.cypher`` suffix is the migration's
    *version* string and is the identity for the applied-migrations
    log.
  - Applied migrations are recorded as ``(:_Migration {version})``
    nodes on the shared instance. The runner queries this node-set
    before applying each file; presence means the file is skipped.
  - Each file is parsed by splitting on ``;\\n`` (one semicolon
    immediately followed by a newline) into statements; whitespace-
    or comment-only statements are filtered out. Each statement runs
    against ``session.run(stmt)`` (auto-commit), which Neo4j 5
    requires for schema DDL like ``CREATE CONSTRAINT`` and ``CREATE
    INDEX``. Statements use ``IF NOT EXISTS`` for double idempotency:
    the file-level ``:_Migration`` check is the primary gate, the
    ``IF NOT EXISTS`` clauses are the structural backstop if the
    primary gate is bypassed.
  - The applied-migration node is written in a separate
    ``execute_write`` transaction after the file's statements
    succeed. Failure mid-file leaves the partial state visible (the
    user-guidance-light shape; Alembic-style versioning that wraps
    a whole file in a transaction is paper architecture at S21
    scope and Neo4j 5's auto-commit DDL blocks the cleaner shape
    anyway). Re-running picks up from the next un-applied file
    because the node is only written on full-file success.

Run directly: ``python -m ops.migrate_neo4j`` (does not run the
Postgres phases). Run as part of the full migrate flow:
``make migrate`` (Postgres phases first, then this).
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from neo4j import GraphDatabase

from padhanam.config import Neo4jSettings

log = logging.getLogger("ops.migrate_neo4j")

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "neo4j"

# Strip ``//`` line comments from a Cypher statement before checking
# whether it is whitespace-only. The comment-stripping is local to
# the emptiness check; the statement we send to Neo4j retains the
# comments since the driver tolerates them.
_LINE_COMMENT = re.compile(r"//[^\n]*")


def _split_statements(text: str) -> list[str]:
    raw = text.split(";\n")
    statements: list[str] = []
    for piece in raw:
        # Re-add the trailing semicolon dropped by split, but only if
        # the piece still has Cypher content.
        stripped = _LINE_COMMENT.sub("", piece).strip()
        if not stripped:
            continue
        statements.append(piece.strip() + ";" if not piece.rstrip().endswith(";") else piece.strip())
    return statements


def _migration_files() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(MIGRATIONS_DIR.glob("*.cypher"), key=lambda p: p.name)


def _is_applied(driver, version: str) -> bool:
    with driver.session() as session:
        result = session.run(
            "MATCH (m:_Migration {version: $version}) RETURN m LIMIT 1",
            version=version,
        )
        return result.single() is not None


def _record_applied(driver, version: str) -> None:
    with driver.session() as session:
        result = session.run(
            "MERGE (m:_Migration {version: $version}) "
            "ON CREATE SET m.applied_at = datetime() "
            "RETURN m",
            version=version,
        )
        result.consume()


def _apply_migration(driver, file: Path) -> None:
    version = file.stem
    if _is_applied(driver, version):
        log.info("phase 3: %s already applied, skipping", version)
        return
    log.info("phase 3: applying %s", version)
    statements = _split_statements(file.read_text(encoding="utf-8"))
    with driver.session() as session:
        for stmt in statements:
            result = session.run(stmt)
            result.consume()
    _record_applied(driver, version)
    log.info("phase 3: %s applied", version)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("phase 3: neo4j cypher migrations")
    settings = Neo4jSettings()
    driver = GraphDatabase.driver(
        settings.bolt_uri,
        auth=(settings.user, settings.password),
    )
    try:
        files = _migration_files()
        if not files:
            log.info("phase 3: no migrations under %s", MIGRATIONS_DIR)
        else:
            log.info("phase 3: %d migration file(s) discovered", len(files))
            for file in files:
                _apply_migration(driver, file)
    finally:
        driver.close()
    log.info("phase 3: complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
