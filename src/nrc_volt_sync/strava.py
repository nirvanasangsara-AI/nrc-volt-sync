from __future__ import annotations

import secrets
import time
import urllib.parse
import webbrowser
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import httpx

from .config import load_config, save_config

AUTH_URL = "https://www.strava.com/oauth/authorize"
# Public OAuth endpoint, not a credential.
TOKEN_URL = "https://www.strava.com/oauth/token"  # nosec B105
API_ROOT = "https://www.strava.com/api/v3"
REDIRECT_URI = "http://localhost:8765/callback"
USER_AGENT = "NRCVoltSync/0.2 personal-use"


class StravaError(RuntimeError):
    pass


class _OAuthHandler(BaseHTTPRequestHandler):
    code: str | None = None
    returned_state: str | None = None
    oauth_error: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        type(self).code = query.get("code", [None])[0]
        type(self).returned_state = query.get("state", [None])[0]
        type(self).oauth_error = query.get("error", [None])[0]
        body = (
            "<html><body><h2>NRC Volt Sync authorization complete.</h2>"
            "<p>You can close this window. 인증이 완료되었습니다.</p></body></html>"
        )
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def authorize(client_id: str, client_secret: str) -> dict[str, Any]:
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "approval_prompt": "force",
        "scope": "activity:read_all",
        "state": state,
    }
    _OAuthHandler.code = None
    _OAuthHandler.returned_state = None
    _OAuthHandler.oauth_error = None
    server = HTTPServer(("127.0.0.1", 8765), _OAuthHandler)
    server.timeout = 180
    webbrowser.open(f"{AUTH_URL}?{urllib.parse.urlencode(params)}")
    server.handle_request()
    server.server_close()
    if _OAuthHandler.oauth_error:
        raise StravaError(f"Strava authorization failed: {_OAuthHandler.oauth_error}")
    if not _OAuthHandler.code or _OAuthHandler.returned_state != state:
        raise StravaError("Strava authorization did not return a valid code")
    with httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": _OAuthHandler.code,
                "grant_type": "authorization_code",
            },
        )
    response.raise_for_status()
    token = response.json()
    return {
        "strava_client_id": str(client_id),
        "strava_client_secret": client_secret,
        "strava_access_token": token["access_token"],
        "strava_refresh_token": token["refresh_token"],
        "strava_expires_at": int(token["expires_at"]),
        "strava_athlete_id": int(token["athlete"]["id"]),
    }


class StravaClient:
    def __init__(self) -> None:
        self.config = load_config()
        required = (
            "strava_client_id",
            "strava_client_secret",
            "strava_access_token",
            "strava_refresh_token",
            "strava_expires_at",
        )
        missing = [key for key in required if key not in self.config]
        if missing:
            raise StravaError("Strava setup is incomplete; run configure-strava")
        self.client = httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT})

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> StravaClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _refresh_if_needed(self) -> None:
        if int(self.config["strava_expires_at"]) > int(time.time()) + 300:
            return
        response = self.client.post(
            TOKEN_URL,
            data={
                "client_id": self.config["strava_client_id"],
                "client_secret": self.config["strava_client_secret"],
                "grant_type": "refresh_token",
                "refresh_token": self.config["strava_refresh_token"],
            },
        )
        response.raise_for_status()
        token = response.json()
        self.config.update(
            {
                "strava_access_token": token["access_token"],
                "strava_refresh_token": token["refresh_token"],
                "strava_expires_at": int(token["expires_at"]),
            }
        )
        save_config(self.config)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._refresh_if_needed()
        response = self.client.get(
            f"{API_ROOT}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self.config['strava_access_token']}"},
        )
        if response.status_code == 429:
            raise StravaError("Strava API rate limit reached; retry after the reset window")
        if response.is_error:
            raise StravaError(f"Strava API returned HTTP {response.status_code}")
        return response.json()

    def athlete(self) -> dict[str, Any]:
        return self._get("/athlete")

    def activities(
        self,
        *,
        after: int | None = None,
        before: int | None = None,
        page_limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        page = 1
        while page_limit is None or page <= page_limit:
            params: dict[str, Any] = {"page": page, "per_page": 100}
            if after is not None:
                params["after"] = after
            if before is not None:
                params["before"] = before
            rows = self._get("/athlete/activities", params=params)
            if not rows:
                return
            yield from rows
            if len(rows) < 100:
                return
            page += 1

    def activity(self, activity_id: int) -> dict[str, Any]:
        return self._get(f"/activities/{activity_id}", params={"include_all_efforts": "false"})

    def streams(self, activity_id: int) -> dict[str, dict[str, Any]]:
        keys = "time,distance,latlng,altitude,heartrate,cadence,watts,moving"
        data = self._get(
            f"/activities/{activity_id}/streams",
            params={"keys": keys, "key_by_type": "true", "resolution": "high"},
        )
        return data if isinstance(data, dict) else {row["type"]: row for row in data}
