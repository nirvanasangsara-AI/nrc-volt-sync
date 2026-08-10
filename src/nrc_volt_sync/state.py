from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import STATE_PATH, ensure_app_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_item (
    strava_id INTEGER PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    activity_start TEXT NOT NULL,
    distance_m REAL NOT NULL,
    device_name TEXT,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    garmin_id TEXT,
    response_json TEXT,
    error TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sync_item_status ON sync_item(status);
"""


class State:
    def __init__(self, path: Path = STATE_PATH) -> None:
        ensure_app_dirs()
        self.path = path
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()
        path.chmod(0o600)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> State:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get(self, strava_id: int) -> sqlite3.Row | None:
        with closing(
            self.connection.execute("SELECT * FROM sync_item WHERE strava_id = ?", (strava_id,))
        ) as cursor:
            return cursor.fetchone()

    def is_complete(self, strava_id: int) -> bool:
        row = self.get(strava_id)
        return bool(row and row["status"] in {"uploaded", "already_on_garmin", "skipped"})

    def record(
        self,
        *,
        strava_id: int,
        fingerprint: str,
        activity_start: str,
        distance_m: float,
        device_name: str | None,
        status: str,
        garmin_id: str | None = None,
        response: Any = None,
        error: str | None = None,
        increment_attempts: bool = False,
    ) -> None:
        existing = self.get(strava_id)
        attempts = int(existing["attempts"]) if existing else 0
        if increment_attempts:
            attempts += 1
        response_json = None
        if response is not None:
            response_json = json.dumps(response, ensure_ascii=False, default=str)[:20_000]
        now = datetime.now(UTC).isoformat()
        self.connection.execute(
            """
            INSERT INTO sync_item (
                strava_id, fingerprint, activity_start, distance_m, device_name,
                status, attempts, garmin_id, response_json, error, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(strava_id) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                activity_start = excluded.activity_start,
                distance_m = excluded.distance_m,
                device_name = excluded.device_name,
                status = excluded.status,
                attempts = excluded.attempts,
                garmin_id = COALESCE(excluded.garmin_id, sync_item.garmin_id),
                response_json = excluded.response_json,
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (
                strava_id,
                fingerprint,
                activity_start,
                distance_m,
                device_name,
                status,
                attempts,
                garmin_id,
                response_json,
                error,
                now,
            ),
        )
        self.connection.commit()

    def summary(self) -> dict[str, int]:
        with closing(
            self.connection.execute(
                "SELECT status, COUNT(*) AS count FROM sync_item GROUP BY status ORDER BY status"
            )
        ) as cursor:
            return {row["status"]: row["count"] for row in cursor.fetchall()}
