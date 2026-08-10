from __future__ import annotations

import getpass
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from garminconnect import Garmin

from .config import GARMIN_TOKEN_DIR, load_config, save_config


class GarminError(RuntimeError):
    pass


def configure_garmin(email: str | None = None) -> str:
    config = load_config()
    email = email or str(config.get("garmin_email") or input("Garmin email: ").strip())
    if not email:
        raise GarminError("Garmin email is required")
    password = getpass.getpass("Garmin password (not stored): ")
    if not password:
        raise GarminError("Garmin password is required")
    client = Garmin(
        email,
        password,
        prompt_mfa=lambda: input("Garmin verification code: ").strip(),
    )
    client.login(str(GARMIN_TOKEN_DIR))
    config["garmin_email"] = email
    save_config(config)
    return str(client.full_name or client.display_name or email)


def connect_garmin() -> Garmin:
    client = Garmin()
    try:
        client.login(str(GARMIN_TOKEN_DIR))
    except Exception as error:
        raise GarminError("Garmin authentication needs to be configured again") from error
    return client


def _value(activity: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if activity.get(key) is not None:
            return activity[key]
    return None


def _garmin_start(activity: dict[str, Any]) -> datetime | None:
    millis = _value(activity, "beginTimestamp", "startTimestampGMT", "startTimestamp")
    if millis is not None:
        try:
            return datetime.fromtimestamp(float(millis) / 1000, tz=UTC)
        except (TypeError, ValueError, OSError):
            pass
    value = _value(activity, "startTimeGMT", "startTimeLocal")
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)
        except ValueError:
            pass
    return None


def _activity_type(activity: dict[str, Any]) -> str:
    value = activity.get("activityType") or activity.get("activityTypeDTO") or {}
    if isinstance(value, dict):
        return str(value.get("typeKey") or value.get("parentTypeId") or "").lower()
    return str(value).lower()


def _looks_like_same_activity(
    activity: dict[str, Any], *, start: datetime, distance_m: float, elapsed_s: float
) -> bool:
    activity_type = _activity_type(activity)
    if activity_type and "run" not in activity_type:
        return False
    remote_start = _garmin_start(activity)
    if remote_start is None or abs((remote_start - start).total_seconds()) > 120:
        return False
    try:
        remote_distance = float(_value(activity, "distance", "distanceMeters") or 0)
        remote_duration = float(
            _value(activity, "elapsedDuration", "duration", "movingDuration") or 0
        )
    except (TypeError, ValueError):
        return False
    distance_tolerance = max(100.0, distance_m * 0.015)
    duration_tolerance = max(180.0, elapsed_s * 0.03)
    return (
        abs(remote_distance - distance_m) <= distance_tolerance
        and abs(remote_duration - elapsed_s) <= duration_tolerance
    )


def find_matching_activity(
    client: Garmin, *, start: datetime, distance_m: float, elapsed_s: float
) -> dict[str, Any] | None:
    first_date = (start - timedelta(days=1)).date().isoformat()
    last_date = (start + timedelta(days=1)).date().isoformat()
    activities = client.get_activities_by_date(
        first_date, last_date, activitytype="running", sortorder="asc"
    )
    for activity in activities:
        if _looks_like_same_activity(
            activity, start=start, distance_m=distance_m, elapsed_s=elapsed_s
        ):
            return activity
    return None


def activity_id(activity: Any) -> str | None:
    if isinstance(activity, dict):
        for key, value in activity.items():
            if key.lower() in {"activityid", "activity_id"} and value is not None:
                return str(value)
        for value in activity.values():
            found = activity_id(value)
            if found:
                return found
    elif isinstance(activity, list):
        for value in activity:
            found = activity_id(value)
            if found:
                return found
    return None


def upload_and_confirm(
    client: Garmin,
    fit_path: Path,
    *,
    start: datetime,
    distance_m: float,
    elapsed_s: float,
) -> tuple[Any, dict[str, Any]]:
    response = client.upload_activity(str(fit_path))
    for attempt in range(6):
        match = find_matching_activity(
            client, start=start, distance_m=distance_m, elapsed_s=elapsed_s
        )
        if match:
            return response, match
        if attempt < 5:
            time.sleep(5)
    raise GarminError(
        "Garmin accepted the upload but the activity did not appear within 30 seconds"
    )
