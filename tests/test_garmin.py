from datetime import UTC, datetime

from nrc_volt_sync.garmin import _looks_like_same_activity, activity_id


def test_matches_remote_activity_with_small_rounding_differences() -> None:
    start = datetime(2024, 1, 15, 8, 0, tzinfo=UTC)
    remote = {
        "activityId": 987654,
        "activityType": {"typeKey": "running"},
        "beginTimestamp": int((start.timestamp() + 30) * 1000),
        "distance": 9_950,
        "elapsedDuration": 3_650,
    }

    assert _looks_like_same_activity(remote, start=start, distance_m=10_000, elapsed_s=3_600)
    assert activity_id({"result": {"activityId": 987654}}) == "987654"


def test_rejects_different_run() -> None:
    start = datetime(2024, 1, 15, 8, 0, tzinfo=UTC)
    remote = {
        "activityType": {"typeKey": "running"},
        "beginTimestamp": int(start.timestamp() * 1000),
        "distance": 5_000,
        "elapsedDuration": 1_800,
    }

    assert not _looks_like_same_activity(remote, start=start, distance_m=10_000, elapsed_s=3_600)
