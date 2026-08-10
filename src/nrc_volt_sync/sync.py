from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .config import FIT_DIR
from .fit import FitValidation, activity_fingerprint, write_validated_fit
from .garmin import activity_id as garmin_activity_id
from .garmin import connect_garmin, find_matching_activity, upload_and_confirm
from .state import State
from .strava import StravaClient

LOGGER = logging.getLogger(__name__)
RUN_TYPES = {"run", "trailrun", "virtualrun"}


@dataclass(frozen=True)
class SyncResult:
    strava_id: int
    status: str
    name: str
    distance_m: float
    validation: FitValidation | None = None
    garmin_id: str | None = None


def _is_run(activity: dict[str, Any]) -> bool:
    sport = str(activity.get("sport_type") or activity.get("type") or "").lower()
    return sport in RUN_TYPES


def _source_text(activity: dict[str, Any]) -> str:
    return " ".join(
        str(activity.get(key) or "")
        for key in ("device_name", "external_id", "name", "description")
    ).lower()


def _is_garmin_source(activity: dict[str, Any]) -> bool:
    text = _source_text(activity)
    return "garmin" in text or str(activity.get("upload_id_str") or "").startswith("garmin")


def _is_apple_watch_source(activity: dict[str, Any]) -> bool:
    text = _source_text(activity)
    return any(
        marker in text for marker in ("apple watch", "apple_workout", "apple workout", "healthfit")
    )


def _start(detail: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(str(detail["start_date"]).replace("Z", "+00:00")).astimezone(UTC)


def sync_activity(
    strava: StravaClient,
    state: State,
    activity: dict[str, Any],
    *,
    dry_run: bool,
    only_apple_watch: bool,
) -> SyncResult | None:
    if not _is_run(activity):
        return None
    strava_id = int(activity["id"])
    if state.is_complete(strava_id):
        return None
    detail = strava.activity(strava_id)
    name = str(detail.get("name") or f"Strava Run {strava_id}")
    distance_m = float(detail.get("distance") or 0)
    elapsed_s = float(detail.get("elapsed_time") or 0)
    fingerprint = activity_fingerprint(detail)
    device_name = str(detail.get("device_name") or "") or None
    if _is_garmin_source(detail):
        state.record(
            strava_id=strava_id,
            fingerprint=fingerprint,
            activity_start=str(detail["start_date"]),
            distance_m=distance_m,
            device_name=device_name,
            status="skipped",
            error="Garmin-origin activity",
        )
        return SyncResult(strava_id, "skipped_garmin_source", name, distance_m)
    if only_apple_watch and not _is_apple_watch_source(detail):
        return None

    streams = strava.streams(strava_id)
    fit_path = FIT_DIR / f"strava-{strava_id}.fit"
    validation = write_validated_fit(detail, streams, fit_path)
    state.record(
        strava_id=strava_id,
        fingerprint=fingerprint,
        activity_start=str(detail["start_date"]),
        distance_m=distance_m,
        device_name=device_name,
        status="validated",
    )
    if dry_run:
        return SyncResult(strava_id, "validated", name, distance_m, validation)

    garmin = connect_garmin()
    start = _start(detail)
    existing = find_matching_activity(
        garmin, start=start, distance_m=distance_m, elapsed_s=elapsed_s
    )
    if existing:
        existing_id = garmin_activity_id(existing)
        state.record(
            strava_id=strava_id,
            fingerprint=fingerprint,
            activity_start=str(detail["start_date"]),
            distance_m=distance_m,
            device_name=device_name,
            status="already_on_garmin",
            garmin_id=existing_id,
        )
        return SyncResult(strava_id, "already_on_garmin", name, distance_m, validation, existing_id)

    try:
        response, confirmed = upload_and_confirm(
            garmin,
            fit_path,
            start=start,
            distance_m=distance_m,
            elapsed_s=elapsed_s,
        )
        confirmed_id = garmin_activity_id(confirmed) or garmin_activity_id(response)
        state.record(
            strava_id=strava_id,
            fingerprint=fingerprint,
            activity_start=str(detail["start_date"]),
            distance_m=distance_m,
            device_name=device_name,
            status="uploaded",
            garmin_id=confirmed_id,
            response=response,
            increment_attempts=True,
        )
        return SyncResult(strava_id, "uploaded", name, distance_m, validation, confirmed_id)
    except Exception as error:
        state.record(
            strava_id=strava_id,
            fingerprint=fingerprint,
            activity_start=str(detail["start_date"]),
            distance_m=distance_m,
            device_name=device_name,
            status="failed",
            error=f"{type(error).__name__}: {error}"[:1000],
            increment_attempts=True,
        )
        raise


def sync_many(
    *,
    activity_id: int | None = None,
    after: int | None = None,
    before: int | None = None,
    limit: int = 25,
    dry_run: bool = False,
    only_apple_watch: bool = True,
) -> list[SyncResult]:
    results: list[SyncResult] = []
    with StravaClient() as strava, State() as state:
        if activity_id is not None:
            activities = [strava.activity(activity_id)]
        else:
            activities = strava.activities(after=after, before=before)
        for activity in activities:
            if len(results) >= limit:
                break
            try:
                result = sync_activity(
                    strava,
                    state,
                    activity,
                    dry_run=dry_run,
                    only_apple_watch=only_apple_watch,
                )
            except Exception:
                LOGGER.exception("Activity %s failed", activity.get("id"))
                continue
            if result is not None:
                results.append(result)
    return results
