import httpx
import pytest

from nrc_volt_sync import strava


def _config(**overrides):
    config = {
        "strava_client_id": "synthetic-client",
        "strava_client_secret": "synthetic-secret",
        "strava_access_token": "synthetic-access",
        "strava_refresh_token": "synthetic-refresh",
        "strava_expires_at": 4_102_444_800,
    }
    config.update(overrides)
    return config


def test_activity_and_stream_requests_use_authorized_api(monkeypatch) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/streams"):
            return httpx.Response(200, json={"time": {"data": [0, 1]}})
        return httpx.Response(200, json={"id": 101, "sport_type": "Run"})

    monkeypatch.setattr(strava, "load_config", _config)
    client = strava.StravaClient()
    client.client.close()
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        assert client.activity(101)["id"] == 101
        assert client.streams(101)["time"]["data"] == [0, 1]
    finally:
        client.close()

    assert all(
        request.headers["Authorization"] == "Bearer synthetic-access" for request in requests
    )


def test_rate_limit_is_reported(monkeypatch) -> None:
    monkeypatch.setattr(strava, "load_config", _config)
    client = strava.StravaClient()
    client.client.close()
    client.client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(429, json={}))
    )
    try:
        with pytest.raises(strava.StravaError, match="rate limit"):
            client.activity(101)
    finally:
        client.close()


def test_expired_token_refreshes_without_exposing_values(monkeypatch) -> None:
    saved = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_at": 4_102_444_800,
                },
            )
        return httpx.Response(200, json={"id": 101})

    monkeypatch.setattr(strava, "load_config", lambda: _config(strava_expires_at=0))
    monkeypatch.setattr(strava, "save_config", lambda value: saved.append(dict(value)))
    client = strava.StravaClient()
    client.client.close()
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        client.activity(101)
    finally:
        client.close()

    assert saved[0]["strava_access_token"] == "new-access"
    assert saved[0]["strava_refresh_token"] == "new-refresh"
