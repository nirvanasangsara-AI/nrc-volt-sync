from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from .config import STATE_PATH, ensure_app_dirs

TABLE_COLUMNS = """
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    activity_start TEXT NOT NULL,
    distance_m REAL NOT NULL,
    device_name TEXT,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    garmin_id TEXT,
    error TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source, source_id)
"""
CREATE_TABLE = f"CREATE TABLE IF NOT EXISTS sync_item ({TABLE_COLUMNS})"
CREATE_INDEX = "CREATE INDEX IF NOT EXISTS sync_item_status ON sync_item(status)"
CREATE_FINGERPRINT_INDEX = (
    "CREATE INDEX IF NOT EXISTS sync_item_fingerprint ON sync_item(fingerprint)"
)
SCHEMA_VERSION = 3


class State:
    def __init__(self, path: Path = STATE_PATH) -> None:
        if path == STATE_PATH:
            ensure_app_dirs()
        else:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self._initialize_schema()
        path.chmod(0o600)

    def _initialize_schema(self) -> None:
        columns = {
            str(row["name"])
            for row in self.connection.execute("PRAGMA table_info(sync_item)").fetchall()
        }
        if columns and "source" not in columns:
            self._migrate_legacy_schema()
            return
        with self.connection:
            self.connection.execute(CREATE_TABLE)
            self.connection.execute(CREATE_INDEX)
            self.connection.execute(CREATE_FINGERPRINT_INDEX)
            self.connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _migrate_legacy_schema(self) -> None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self.connection.execute("ALTER TABLE sync_item RENAME TO sync_item_legacy")
            self.connection.execute(f"CREATE TABLE sync_item ({TABLE_COLUMNS})")
            self.connection.execute(
                """
                INSERT INTO sync_item (
                    source, source_id, fingerprint, activity_start, distance_m, device_name,
                    status, attempts, garmin_id, error, updated_at
                )
                SELECT
                    'strava', CAST(strava_id AS TEXT), fingerprint, activity_start,
                    distance_m, device_name,
                    status, attempts, garmin_id, error, updated_at
                FROM sync_item_legacy
                """
            )
            self.connection.execute("DROP TABLE sync_item_legacy")
            self.connection.execute(CREATE_INDEX)
            self.connection.execute(CREATE_FINGERPRINT_INDEX)
            self.connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> State:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get(self, source: str, source_id: str | int) -> sqlite3.Row | None:
        with closing(
            self.connection.execute(
                "SELECT * FROM sync_item WHERE source = ? AND source_id = ?",
                (source, str(source_id)),
            )
        ) as cursor:
            return cursor.fetchone()

    def is_complete(self, source: str, source_id: str | int) -> bool:
        row = self.get(source, source_id)
        return bool(row and row["status"] in {"uploaded", "already_on_garmin", "skipped"})

    def record(
        self,
        *,
        source: str,
        source_id: str | int,
        fingerprint: str,
        activity_start: str,
        distance_m: float,
        device_name: str | None,
        status: str,
        garmin_id: str | None = None,
        error: str | None = None,
        increment_attempts: bool = False,
    ) -> None:
        if not source or not str(source_id):
            raise ValueError("source and source_id are required")
        existing = self.get(source, source_id)
        attempts = int(existing["attempts"]) if existing else 0
        if increment_attempts:
            attempts += 1
        now = datetime.now(UTC).isoformat()
        self.connection.execute(
            """
            INSERT INTO sync_item (
                source, source_id, fingerprint, activity_start, distance_m, device_name,
                status, attempts, garmin_id, error, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, source_id) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                activity_start = excluded.activity_start,
                distance_m = excluded.distance_m,
                device_name = excluded.device_name,
                status = excluded.status,
                attempts = excluded.attempts,
                garmin_id = COALESCE(excluded.garmin_id, sync_item.garmin_id),
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (
                source,
                str(source_id),
                fingerprint,
                activity_start,
                distance_m,
                device_name,
                status,
                attempts,
                garmin_id,
                error,
                now,
            ),
        )
        self.connection.commit()

    def summary(self) -> dict[str, int]:
        with closing(
            self.connection.execute(
                """
                SELECT source || ':' || status AS source_status, COUNT(*) AS count
                FROM sync_item
                GROUP BY source, status
                ORDER BY source, status
                """
            )
        ) as cursor:
            return {row["source_status"]: row["count"] for row in cursor.fetchall()}
