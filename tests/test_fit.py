from nrc_volt_sync.fit import activity_fingerprint, encode_activity, validate_activity


def synthetic_activity() -> tuple[dict, dict]:
    record_count = 100
    activity = {
        "id": 123456789,
        "sport_type": "Run",
        "start_date": "2024-01-15T08:00:00Z",
        "distance": 990.0,
        "elapsed_time": 99,
        "moving_time": 95,
        "utc_offset": 32_400,
        "average_speed": 10.0,
        "max_speed": 11.2,
        "total_elevation_gain": 20.0,
        "calories": 70,
    }
    streams = {
        "time": {"data": list(range(record_count))},
        "distance": {"data": [index * 10.0 for index in range(record_count)]},
        "latlng": {
            "data": [
                [37.5 + index / 100_000, 127.0 + index / 100_000] for index in range(record_count)
            ]
        },
        "altitude": {"data": [100 + (index % 10) for index in range(record_count)]},
        "heartrate": {"data": [140 + (index % 5) for index in range(record_count)]},
        "cadence": {"data": [85 for _ in range(record_count)]},
        "moving": {"data": [not 40 <= index < 44 for index in range(record_count)]},
    }
    return activity, streams


def test_encodes_complete_valid_fit_activity() -> None:
    activity, streams = synthetic_activity()
    data = encode_activity(activity, streams)
    validation = validate_activity(data, expected_distance_m=990.0, expected_elapsed_s=99)

    assert validation.record_count == 100
    assert validation.gps_records == 100
    assert validation.heart_rate_records == 100
    assert validation.distance_m == 990.0


def test_activity_fingerprint_is_stable() -> None:
    activity, _ = synthetic_activity()

    assert activity_fingerprint(activity) == activity_fingerprint(dict(activity))


def test_encodes_summary_only_activity_without_inventing_sensor_data() -> None:
    activity = {
        "id": 456,
        "sport_type": "Run",
        "start_date": "2024-02-20T08:00:00Z",
        "distance": 5000.0,
        "moving_time": 1800,
        "elapsed_time": 1800,
        "average_speed": 2.778,
    }
    streams = {"time": {"data": [0, 1800]}, "moving": {"data": [True, True]}}

    data = encode_activity(activity, streams)
    validation = validate_activity(
        data, expected_distance_m=5000.0, expected_elapsed_s=1800
    )

    assert validation.record_count == 2
    assert validation.distance_m == 5000.0
    assert validation.gps_records == 0
    assert validation.heart_rate_records == 0
