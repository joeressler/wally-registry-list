"""SQLite cache for parsed package records (latest version only)."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from wally_registry_list.config import database_path
from wally_registry_list.models import PackageRecord


class PackageCache:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or database_path()
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._migrate_if_needed()

    def _migrate_if_needed(self) -> None:
        versions_table = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='versions'"
        ).fetchone()
        package_columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(packages)")
        }
        if versions_table or "version_count" in package_columns:
            self._conn.executescript(
                """
                DROP TABLE IF EXISTS versions;
                DROP TABLE IF EXISTS packages;
                """
            )
            self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS packages (
                scope TEXT NOT NULL,
                name TEXT NOT NULL,
                latest_version TEXT NOT NULL,
                description TEXT NOT NULL,
                license TEXT NOT NULL,
                realm TEXT NOT NULL,
                authors_json TEXT NOT NULL,
                homepage TEXT,
                repository TEXT,
                dependency_count INTEGER NOT NULL,
                server_dependency_count INTEGER NOT NULL,
                PRIMARY KEY (scope, name)
            );
            """
        )
        self._conn.commit()

    def get_last_sync(self) -> float | None:
        row = self._conn.execute(
            "SELECT value FROM sync_meta WHERE key = 'last_index_sync'"
        ).fetchone()
        if row is None:
            return None
        try:
            return float(row["value"])
        except ValueError:
            return None

    def set_last_sync(self, timestamp: float | None = None) -> None:
        ts = timestamp if timestamp is not None else time.time()
        self._conn.execute(
            """
            INSERT INTO sync_meta (key, value) VALUES ('last_index_sync', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(ts),),
        )
        self._conn.commit()

    def has_packages(self) -> bool:
        row = self._conn.execute("SELECT COUNT(*) AS c FROM packages").fetchone()
        return bool(row and row["c"] > 0)

    def replace_all(self, packages: list[PackageRecord]) -> None:
        self._conn.execute("DELETE FROM packages")
        for record in packages:
            self._insert_package(record)
        self.set_last_sync()
        self._conn.commit()

    def _insert_package(self, record: PackageRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO packages (
                scope, name, latest_version, description, license, realm,
                authors_json, homepage, repository,
                dependency_count, server_dependency_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.scope,
                record.name,
                record.latest_version,
                record.description,
                record.license,
                record.realm,
                json.dumps(record.authors),
                record.homepage,
                record.repository,
                record.dependency_count,
                record.server_dependency_count,
            ),
        )

    def load_all(self) -> list[PackageRecord]:
        rows = self._conn.execute(
            """
            SELECT * FROM packages
            ORDER BY scope COLLATE NOCASE, name COLLATE NOCASE
            """
        ).fetchall()
        return [_row_to_record(row) for row in rows]


def _row_to_record(row: sqlite3.Row) -> PackageRecord:
    return PackageRecord(
        scope=row["scope"],
        name=row["name"],
        latest_version=row["latest_version"],
        description=row["description"],
        license=row["license"],
        realm=row["realm"],
        authors=json.loads(row["authors_json"]),
        homepage=row["homepage"],
        repository=row["repository"],
        dependency_count=row["dependency_count"],
        server_dependency_count=row["server_dependency_count"],
    )
