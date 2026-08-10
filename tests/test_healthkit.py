import json
from pathlib import Path

import pytest

from nrc_volt_sync.healthkit import (
    HealthKitDataError,
    discover_workouts,
    load_workout,
    parse_workout,
    workout_fingerprint,
)


def synthetic_payload() -> dict:
    return {
        "schema": "io.github.nrcvoltsync.healthkit.workout",
        "schema_version": 1,
        "id": "11111111-2222-4333-8444-555555555555",
        "activity_type": "running",
        "name": "Synthetic Apple Health Run",
        "start_date": "2024-03-01T00:00:00Z",
        "end_date": "2024-03-01T00:10:00Z",
        "duration_s": 580,
        "distance_m": 1500,
        "calories": 100,
        "timezone_offset_s": 32400,
        "device_name": "Synthetic Watch",
        "source_bundle_id": "com.example.synthetic-health",
        "route": [
            {
                "offset_s": 0,
                "latitude": 10.0,
                "longitude": 20.0,
                "altitude_m": -2.0,
                "speed_m_s": -1.0,
            },
            {
                "offset_s": 600,
                "latitude": 10.001,
                "longitude": 20.001,
                "altitude_m": 3.0,
                "speed_m_s": 2.5,
            },
        ],
        "samples": {
            "heart_rate": [
                {"offset_s": 2.25, "value": 140},
                {"offset_s": 599.1, "value": 145},
            ],
            "distance": [
                {"offset_s": 0, "value": 0},
                {"offset_s": 600, "value": 1500},
            ],
            "running_power": [{"offset_s": 300, "value": 250}],
            "running_speed": [{"offset_s": 300, "value": 2.6}],
            "stride_length": [{"offset_s": 300, "value": 1.1}],
            "vertical_oscillation": [{"offset_s": 300, "value": 0.08}],
            "ground_contact_time": [{"offset_s": 300, "value": 0.25}],
        },
    }


def test_parses_healthkit_payload_without_fabricating_samples() -> None:
    workout = parse_workout(synthetic_payload())

    assert workout.source_id == "11111111-2222-4333-8444-555555555555"
    assert workout.elapsed_s == 600
    assert workout.duration_s == 580
    assert workout.route[0].altitude_m == -2
    assert workout.route[0].speed_m_s is None
    assert len(workout.samples["heart_rate"]) == 2
    assert "cadence" not in workout.samples
    assert workout_fingerprint(workout) == workout_fingerprint(workout)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data.update(id="real-watch-id"), "UUID"),
        (lambda data: data.update(activity_type="cycling"), "running"),
        (lambda data: data["samples"].update(cadence=[]), "Unsupported sample"),
        (
            lambda data: data["samples"].update(
                distance=[
                    {"offset_s": 0, "value": 100},
                    {"offset_s": 600, "value": 50},
                ]
            ),
            "non-decreasing",
        ),
    ],
)
def test_rejects_invalid_or_fabrication_prone_payloads(mutation, message) -> None:
    payload = synthetic_payload()
    mutation(payload)

    with pytest.raises(HealthKitDataError, match=message):
        parse_workout(payload)


def test_load_and_discover_ignore_symlinks(tmp_path) -> None:
    first = tmp_path / "first.json"
    first.write_text(json.dumps(synthetic_payload()), encoding="utf-8")
    symlink = tmp_path / "linked.json"
    symlink.symlink_to(first)

    found = discover_workouts(tmp_path)

    assert [path.name for path, _workout in found] == ["first.json"]
    assert load_workout(first).distance_m == 1500
    with pytest.raises(HealthKitDataError, match="symlink"):
        load_workout(symlink)


def test_public_synthetic_example_matches_parser_contract() -> None:
    example = Path(__file__).parents[1] / "examples" / "healthkit-workout.synthetic.json"

    workout = load_workout(example)

    assert workout.distance_m == 1500
    assert workout.source_bundle_id == "com.example.synthetic-health"
