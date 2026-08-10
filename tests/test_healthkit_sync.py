import json

import pytest
from test_healthkit import synthetic_payload

from nrc_volt_sync import healthkit_sync
from nrc_volt_sync.fit import FitValidation
from nrc_volt_sync.healthkit import parse_workout
from nrc_volt_sync.state import State


def _validation() -> FitValidation:
    return FitValidation(
        record_count=5,
        distance_m=1500,
        elapsed_s=600,
        heart_rate_records=2,
        gps_records=2,
        fingerprint="synthetic-fit-fingerprint",
    )


def test_healthkit_workout_uploads_and_records_generic_state(tmp_path, monkeypatch) -> None:
    workout = parse_workout(synthetic_payload())
    monkeypatch.setattr(healthkit_sync, "FIT_DIR", tmp_path)
    monkeypatch.setattr(
        healthkit_sync, "write_validated_healthkit_fit", lambda *_args: _validation()
    )
    monkeypatch.setattr(healthkit_sync, "connect_garmin", lambda: object())
    monkeypatch.setattr(
        healthkit_sync, "find_matching_activity", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        healthkit_sync,
        "upload_and_confirm",
        lambda *_args, **_kwargs: ({"private": "not persisted"}, {"activityId": 303}),
    )

    with State(tmp_path / "state.sqlite3") as state:
        result = healthkit_sync.sync_healthkit_workout(
            state, workout, dry_run=False, fit_export_dir=None
        )
        row = state.get("healthkit", workout.source_id)

    assert result.status == "uploaded"
    assert result.garmin_id == "303"
    assert row["status"] == "uploaded"
    assert row["garmin_id"] == "303"


def test_healthkit_workout_skips_garmin_origin(tmp_path) -> None:
    payload = synthetic_payload()
    payload["source_bundle_id"] = "com.garmin.connect.mobile"
    workout = parse_workout(payload)

    with State(tmp_path / "state.sqlite3") as state:
        result = healthkit_sync.sync_healthkit_workout(
            state, workout, dry_run=True, fit_export_dir=None
        )

    assert result.status == "skipped_garmin_source"


def test_healthkit_workout_detects_existing_garmin_run(tmp_path, monkeypatch) -> None:
    workout = parse_workout(synthetic_payload())
    monkeypatch.setattr(healthkit_sync, "FIT_DIR", tmp_path)
    monkeypatch.setattr(
        healthkit_sync, "write_validated_healthkit_fit", lambda *_args: _validation()
    )
    monkeypatch.setattr(healthkit_sync, "connect_garmin", lambda: object())
    monkeypatch.setattr(
        healthkit_sync,
        "find_matching_activity",
        lambda *_args, **_kwargs: {"activityId": 404},
    )

    with State(tmp_path / "state.sqlite3") as state:
        result = healthkit_sync.sync_healthkit_workout(
            state, workout, dry_run=False, fit_export_dir=None
        )

    assert result.status == "already_on_garmin"
    assert result.garmin_id == "404"


def test_healthkit_upload_failure_is_retryable_state(tmp_path, monkeypatch) -> None:
    workout = parse_workout(synthetic_payload())
    monkeypatch.setattr(healthkit_sync, "FIT_DIR", tmp_path)
    monkeypatch.setattr(
        healthkit_sync, "write_validated_healthkit_fit", lambda *_args: _validation()
    )
    monkeypatch.setattr(healthkit_sync, "connect_garmin", lambda: object())
    monkeypatch.setattr(
        healthkit_sync, "find_matching_activity", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        healthkit_sync,
        "upload_and_confirm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("synthetic failure")),
    )

    with State(tmp_path / "state.sqlite3") as state:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            healthkit_sync.sync_healthkit_workout(
                state, workout, dry_run=False, fit_export_dir=None
            )
        row = state.get("healthkit", workout.source_id)

    assert row["status"] == "failed"
    assert row["attempts"] == 1


def test_healthkit_batch_continues_after_invalid_json(tmp_path, monkeypatch) -> None:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "a-invalid.json").write_text("not-json", encoding="utf-8")
    (outbox / "b-valid.json").write_text(json.dumps(synthetic_payload()), encoding="utf-8")

    class FakeState(State):
        def __init__(self):
            super().__init__(tmp_path / "batch.sqlite3")

    monkeypatch.setattr(healthkit_sync, "State", FakeState)
    monkeypatch.setattr(
        healthkit_sync,
        "sync_healthkit_workout",
        lambda _state, workout, **_kwargs: healthkit_sync.SyncResult(
            "healthkit", workout.source_id, "validated", workout.name, workout.distance_m
        ),
    )

    batch = healthkit_sync.sync_healthkit_many(outbox=outbox, dry_run=True, limit=10)

    assert len(batch.results) == 1
    assert batch.scanned == 1
    assert len(batch.failures) == 1
    assert batch.failures[0].source_id is None
    assert batch.failures[0].error_type == "HealthKitDataError"


def test_portable_fit_export_is_private_and_atomic(tmp_path) -> None:
    source = tmp_path / "source.fit"
    source.write_bytes(b"synthetic-fit")
    destination_dir = tmp_path / "export"
    destination_dir.mkdir()

    destination = healthkit_sync._export_fit(
        source, destination_dir, "11111111-2222-4333-8444-555555555555"
    )

    assert destination.read_bytes() == b"synthetic-fit"
    assert destination.stat().st_mode & 0o777 == 0o600
    assert not list(destination_dir.glob(".nrc-volt-sync-*"))
