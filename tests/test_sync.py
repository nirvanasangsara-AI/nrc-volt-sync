from nrc_volt_sync import sync
from nrc_volt_sync.fit import FitValidation
from nrc_volt_sync.state import State


class FakeStrava:
    def __init__(self, activities: list[dict] | None = None) -> None:
        self.rows = activities or []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def activities(self, **_kwargs):
        yield from self.rows

    def activity(self, activity_id: int):
        return next(row for row in self.rows if row["id"] == activity_id)

    def streams(self, _activity_id: int):
        return {
            "time": {"data": [0, 1800]},
            "distance": {"data": [0.0, 5000.0]},
        }


def _apple_run(activity_id: int = 101) -> dict:
    return {
        "id": activity_id,
        "name": "Synthetic Run",
        "sport_type": "Run",
        "start_date": "2024-01-15T08:00:00Z",
        "distance": 5000.0,
        "elapsed_time": 1800,
        "moving_time": 1800,
        "device_name": "Apple Watch Synthetic",
    }


def _validation() -> FitValidation:
    return FitValidation(
        record_count=2,
        distance_m=5000.0,
        elapsed_s=1800,
        heart_rate_records=0,
        gps_records=0,
        fingerprint="fit-fingerprint",
    )


def test_sync_activity_uploads_and_records_only_minimum_state(tmp_path, monkeypatch) -> None:
    activity = _apple_run()
    strava = FakeStrava([activity])
    monkeypatch.setattr(sync, "FIT_DIR", tmp_path)
    monkeypatch.setattr(sync, "write_validated_fit", lambda *_args: _validation())
    monkeypatch.setattr(sync, "connect_garmin", lambda: object())
    monkeypatch.setattr(sync, "find_matching_activity", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sync,
        "upload_and_confirm",
        lambda *_args, **_kwargs: ({"provider_payload": "not persisted"}, {"activityId": 202}),
    )

    with State(tmp_path / "state.sqlite3") as state:
        result = sync.sync_activity(
            strava, state, activity, dry_run=False, only_apple_watch=True
        )
        columns = {
            row["name"] for row in state.connection.execute("PRAGMA table_info(sync_item)")
        }

        assert result.status == "uploaded"
        assert result.garmin_id == "202"
        assert state.get("strava", "101")["status"] == "uploaded"
        assert "response_json" not in columns


def test_sync_activity_detects_existing_garmin_run(tmp_path, monkeypatch) -> None:
    activity = _apple_run()
    monkeypatch.setattr(sync, "FIT_DIR", tmp_path)
    monkeypatch.setattr(sync, "write_validated_fit", lambda *_args: _validation())
    monkeypatch.setattr(sync, "connect_garmin", lambda: object())
    monkeypatch.setattr(
        sync,
        "find_matching_activity",
        lambda *_args, **_kwargs: {"activityId": 202},
    )

    with State(tmp_path / "state.sqlite3") as state:
        result = sync.sync_activity(
            FakeStrava([activity]), state, activity, dry_run=False, only_apple_watch=True
        )

        assert result.status == "already_on_garmin"
        assert state.get("strava", "101")["garmin_id"] == "202"


def test_sync_many_reports_failures_instead_of_hiding_them(tmp_path, monkeypatch) -> None:
    rows = [_apple_run(101), _apple_run(102)]
    fake_strava = FakeStrava(rows)

    class FakeState(State):
        def __init__(self):
            super().__init__(tmp_path / "batch.sqlite3")

    def fake_sync_activity(_strava, _state, activity, **_kwargs):
        if activity["id"] == 102:
            raise RuntimeError("synthetic provider failure")
        return sync.SyncResult("strava", "101", "uploaded", "Synthetic Run", 5000.0)

    monkeypatch.setattr(sync, "StravaClient", lambda: fake_strava)
    monkeypatch.setattr(sync, "State", FakeState)
    monkeypatch.setattr(sync, "sync_activity", fake_sync_activity)

    batch = sync.sync_many(after=0, limit=10)

    assert len(batch.results) == 1
    assert batch.scanned == 2
    assert batch.failures[0].source == "strava"
    assert batch.failures[0].source_id == "102"
    assert batch.failures[0].error_type == "RuntimeError"
    assert "synthetic provider failure" in batch.failures[0].message
