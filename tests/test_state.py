import sqlite3

from nrc_volt_sync.state import SCHEMA_VERSION, State


def _record(state: State, *, strava_id: int = 101, status: str = "uploaded") -> None:
    state.record(
        strava_id=strava_id,
        fingerprint="synthetic-fingerprint",
        activity_start="2024-01-15T08:00:00Z",
        distance_m=5000.0,
        device_name="Synthetic Watch",
        status=status,
        garmin_id="202",
        increment_attempts=True,
    )


def test_state_records_completion_and_summary(tmp_path) -> None:
    path = tmp_path / "state.sqlite3"
    with State(path) as state:
        _record(state)

        assert state.is_complete(101)
        assert state.summary() == {"uploaded": 1}
        assert state.get(101)["attempts"] == 1

    assert path.stat().st_mode & 0o777 == 0o600


def test_migrates_legacy_response_payload_out_of_database(tmp_path) -> None:
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sync_item (
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
        CREATE INDEX sync_item_status ON sync_item(status);
        INSERT INTO sync_item VALUES (
            101, 'fingerprint', '2024-01-15T08:00:00Z', 5000.0,
            'Synthetic Watch', 'uploaded', 1, '202',
            '{"private_provider_payload": true}', NULL, '2024-01-15T09:00:00Z'
        );
        """
    )
    connection.commit()
    connection.close()

    with State(path) as state:
        columns = {
            row["name"] for row in state.connection.execute("PRAGMA table_info(sync_item)")
        }
        row = state.get(101)
        version = state.connection.execute("PRAGMA user_version").fetchone()[0]

        assert "response_json" not in columns
        assert row["garmin_id"] == "202"
        assert row["status"] == "uploaded"
        assert version == SCHEMA_VERSION
