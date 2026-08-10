from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from nrc_volt_sync import garmin


def _remote_activity(**overrides):
    row = {
        "activityId": 202,
        "activityType": {"typeKey": "running"},
        "startTimeGMT": "2024-01-15T08:00:00Z",
        "distance": 5000.0,
        "elapsedDuration": 1800.0,
    }
    row.update(overrides)
    return row


def test_matching_activity_handles_provider_shapes() -> None:
    start = datetime(2024, 1, 15, 8, tzinfo=UTC)
    assert garmin._looks_like_same_activity(
        _remote_activity(), start=start, distance_m=5000.0, elapsed_s=1800.0
    )
    assert not garmin._looks_like_same_activity(
        _remote_activity(activityType={"typeKey": "cycling"}),
        start=start,
        distance_m=5000.0,
        elapsed_s=1800.0,
    )
    assert not garmin._looks_like_same_activity(
        _remote_activity(distance=6000), start=start, distance_m=5000.0, elapsed_s=1800.0
    )
    assert garmin.activity_id({"nested": [{"activity_id": 202}]}) == "202"
    assert garmin.activity_id({"unrelated": True}) is None


def test_find_matching_activity_queries_bounded_dates() -> None:
    client = SimpleNamespace(
        get_activities_by_date=lambda *args, **kwargs: [_remote_activity()]
    )
    match = garmin.find_matching_activity(
        client,
        start=datetime(2024, 1, 15, 8, tzinfo=UTC),
        distance_m=5000.0,
        elapsed_s=1800.0,
    )
    assert match["activityId"] == 202


def test_connect_garmin_wraps_authentication_failure(monkeypatch) -> None:
    class FailingGarmin:
        def login(self, _path):
            raise RuntimeError("synthetic credential failure")

    monkeypatch.setattr(garmin, "Garmin", FailingGarmin)
    with pytest.raises(garmin.GarminError, match="configured again"):
        garmin.connect_garmin()


def test_configure_garmin_stores_email_not_password(monkeypatch) -> None:
    saved = []

    class FakeGarmin:
        full_name = "Synthetic Runner"
        display_name = None

        def __init__(self, email, password, prompt_mfa):
            assert email == "runner@example.test"
            assert password == "synthetic-password"
            assert prompt_mfa is not None

        def login(self, _path):
            return None

    monkeypatch.setattr(garmin, "Garmin", FakeGarmin)
    monkeypatch.setattr(garmin, "load_config", lambda: {})
    monkeypatch.setattr(garmin, "save_config", lambda value: saved.append(dict(value)))
    monkeypatch.setattr(garmin.getpass, "getpass", lambda _prompt: "synthetic-password")

    assert garmin.configure_garmin("runner@example.test") == "Synthetic Runner"
    assert saved == [{"garmin_email": "runner@example.test"}]


def test_upload_and_confirm_retries_without_persisting_payload(monkeypatch, tmp_path) -> None:
    calls = []

    class Client:
        def upload_activity(self, path):
            assert path.endswith("activity.fit")
            return {"uploadId": 303}

    def find(*_args, **_kwargs):
        calls.append(True)
        return _remote_activity() if len(calls) == 2 else None

    monkeypatch.setattr(garmin, "find_matching_activity", find)
    monkeypatch.setattr(garmin.time, "sleep", lambda _seconds: None)
    response, confirmed = garmin.upload_and_confirm(
        Client(),
        tmp_path / "activity.fit",
        start=datetime(2024, 1, 15, 8, tzinfo=UTC),
        distance_m=5000.0,
        elapsed_s=1800.0,
    )
    assert response["uploadId"] == 303
    assert confirmed["activityId"] == 202
