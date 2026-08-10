from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "io.github.nrcvoltsync.healthkit.workout"
SCHEMA_VERSION = 1
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_POINTS = 500_000
SAMPLE_RANGES: dict[str, tuple[float, float]] = {
    "heart_rate": (1.0, 255.0),
    "distance": (0.0, 1_000_000.0),
    "running_power": (0.0, 65_534.0),
    "running_speed": (0.0, 50.0),
    "stride_length": (0.0, 10.0),
    "vertical_oscillation": (0.0, 2.0),
    "ground_contact_time": (0.0, 10.0),
}


class HealthKitDataError(ValueError):
    pass


@dataclass(frozen=True)
class TimedValue:
    offset_s: float
    value: float


@dataclass(frozen=True)
class RoutePoint:
    offset_s: float
    latitude: float
    longitude: float
    altitude_m: float | None = None
    speed_m_s: float | None = None


@dataclass(frozen=True)
class HealthWorkout:
    source_id: str
    name: str
    start: datetime
    end: datetime
    duration_s: float
    distance_m: float
    calories: float | None
    timezone_offset_s: int
    device_name: str | None
    source_bundle_id: str | None
    route: tuple[RoutePoint, ...]
    samples: dict[str, tuple[TimedValue, ...]]

    @property
    def elapsed_s(self) -> float:
        return (self.end - self.start).total_seconds()

    @property
    def start_iso(self) -> str:
        return self.start.astimezone(UTC).isoformat()


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HealthKitDataError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise HealthKitDataError(f"{label} must be an array")
    return value


def _number(
    value: Any, label: str, *, minimum: float | None = None, maximum: float | None = None
) -> float:
    if isinstance(value, bool):
        raise HealthKitDataError(f"{label} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise HealthKitDataError(f"{label} must be a number") from None
    if not math.isfinite(number):
        raise HealthKitDataError(f"{label} must be finite")
    if minimum is not None and number < minimum:
        raise HealthKitDataError(f"{label} is below the supported range")
    if maximum is not None and number > maximum:
        raise HealthKitDataError(f"{label} is above the supported range")
    return number


def _date(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise HealthKitDataError(f"{label} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HealthKitDataError(f"{label} is not valid ISO-8601") from None
    if parsed.tzinfo is None:
        raise HealthKitDataError(f"{label} must include a time-zone offset")
    return parsed.astimezone(UTC)


def _offset(value: Any, label: str, elapsed_s: float) -> float:
    return _number(value, label, minimum=0.0, maximum=elapsed_s + 1.0)


def _timed_values(raw: Any, name: str, elapsed_s: float) -> tuple[TimedValue, ...]:
    minimum, maximum = SAMPLE_RANGES[name]
    result: list[TimedValue] = []
    previous = -1.0
    for index, item in enumerate(_list(raw, f"samples.{name}")):
        point = _mapping(item, f"samples.{name}[{index}]")
        offset = _offset(point.get("offset_s"), f"samples.{name}[{index}].offset_s", elapsed_s)
        if offset < previous:
            raise HealthKitDataError(f"samples.{name} must be ordered by offset_s")
        previous = offset
        result.append(
            TimedValue(
                offset_s=offset,
                value=_number(
                    point.get("value"),
                    f"samples.{name}[{index}].value",
                    minimum=minimum,
                    maximum=maximum,
                ),
            )
        )
    return tuple(result)


def parse_workout(payload: Any) -> HealthWorkout:
    data = _mapping(payload, "workout")
    if data.get("schema") != SCHEMA or data.get("schema_version") != SCHEMA_VERSION:
        raise HealthKitDataError("Unsupported HealthKit workout schema")
    try:
        source_id = str(uuid.UUID(str(data.get("id"))))
    except (ValueError, AttributeError, TypeError):
        raise HealthKitDataError("id must be a UUID") from None
    if data.get("activity_type") != "running":
        raise HealthKitDataError("Only running workouts are supported")

    start = _date(data.get("start_date"), "start_date")
    end = _date(data.get("end_date"), "end_date")
    elapsed_s = (end - start).total_seconds()
    if elapsed_s < 1 or elapsed_s > 7 * 24 * 60 * 60:
        raise HealthKitDataError("Workout elapsed time is outside the supported range")
    duration_s = _number(data.get("duration_s"), "duration_s", minimum=1.0)
    if duration_s > elapsed_s + 1.0:
        raise HealthKitDataError("duration_s cannot exceed start/end elapsed time")
    distance_m = _number(data.get("distance_m"), "distance_m", minimum=0.0, maximum=1_000_000)
    calories_raw = data.get("calories")
    calories = (
        None
        if calories_raw is None
        else _number(calories_raw, "calories", minimum=0.0, maximum=100_000.0)
    )
    timezone_offset_s = round(
        _number(
            data.get("timezone_offset_s", 0),
            "timezone_offset_s",
            minimum=-86_400,
            maximum=86_400,
        )
    )
    device_name_raw = data.get("device_name")
    if device_name_raw is not None and not isinstance(device_name_raw, str):
        raise HealthKitDataError("device_name must be a string")
    device_name = str(device_name_raw)[:200] if device_name_raw else None
    source_bundle_raw = data.get("source_bundle_id")
    if source_bundle_raw is not None and not isinstance(source_bundle_raw, str):
        raise HealthKitDataError("source_bundle_id must be a string")
    source_bundle_id = str(source_bundle_raw)[:300] if source_bundle_raw else None

    route: list[RoutePoint] = []
    previous = -1.0
    for index, item in enumerate(_list(data.get("route", []), "route")):
        point = _mapping(item, f"route[{index}]")
        offset = _offset(point.get("offset_s"), f"route[{index}].offset_s", elapsed_s)
        if offset < previous:
            raise HealthKitDataError("route must be ordered by offset_s")
        previous = offset
        altitude = point.get("altitude_m")
        speed = point.get("speed_m_s")
        parsed_speed = (
            None
            if speed is None
            else _number(speed, f"route[{index}].speed_m_s", minimum=-1, maximum=100)
        )
        route.append(
            RoutePoint(
                offset_s=offset,
                latitude=_number(
                    point.get("latitude"), f"route[{index}].latitude", minimum=-90, maximum=90
                ),
                longitude=_number(
                    point.get("longitude"),
                    f"route[{index}].longitude",
                    minimum=-180,
                    maximum=180,
                ),
                altitude_m=(
                    None
                    if altitude is None
                    else _number(
                        altitude,
                        f"route[{index}].altitude_m",
                        minimum=-500,
                        maximum=20_000,
                    )
                ),
                speed_m_s=(
                    None if parsed_speed is None or parsed_speed < 0 else parsed_speed
                ),
            )
        )

    raw_samples = _mapping(data.get("samples", {}), "samples")
    unknown = set(raw_samples) - set(SAMPLE_RANGES)
    if unknown:
        raise HealthKitDataError(f"Unsupported sample type: {sorted(unknown)[0]}")
    samples = {
        name: _timed_values(values, name, elapsed_s)
        for name, values in raw_samples.items()
    }
    point_count = len(route) + sum(len(values) for values in samples.values())
    if point_count > MAX_POINTS:
        raise HealthKitDataError("Workout contains too many route/sample points")

    distance_samples = samples.get("distance", ())
    if any(
        right.value < left.value
        for left, right in zip(distance_samples, distance_samples[1:], strict=False)
    ):
        raise HealthKitDataError("distance samples must be cumulative and non-decreasing")
    if distance_samples:
        last_distance = distance_samples[-1].value
        tolerance = max(25.0, distance_m * 0.02)
        if abs(last_distance - distance_m) > tolerance:
            raise HealthKitDataError("distance samples do not match workout distance")

    name_raw = data.get("name")
    name = str(name_raw).strip()[:200] if isinstance(name_raw, str) else ""
    return HealthWorkout(
        source_id=source_id,
        name=name or "Apple Health Run",
        start=start,
        end=end,
        duration_s=duration_s,
        distance_m=distance_m,
        calories=calories,
        timezone_offset_s=timezone_offset_s,
        device_name=device_name,
        source_bundle_id=source_bundle_id,
        route=tuple(route),
        samples=samples,
    )


def load_workout(path: Path) -> HealthWorkout:
    if path.is_symlink() or not path.is_file():
        raise HealthKitDataError("Workout input must be a regular file, not a symlink")
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise HealthKitDataError("Workout input exceeds the 64 MiB safety limit")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HealthKitDataError("Workout input is not valid UTF-8 JSON") from error
    return parse_workout(payload)


def workout_fingerprint(workout: HealthWorkout) -> str:
    raw = "|".join(
        (
            workout.start_iso,
            str(round(workout.distance_m)),
            str(round(workout.elapsed_s)),
            "running",
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def discover_workouts(outbox: Path) -> list[tuple[Path, HealthWorkout]]:
    root = outbox.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise HealthKitDataError("HealthKit outbox must be a directory")
    workouts: list[tuple[Path, HealthWorkout]] = []
    for path in root.iterdir():
        if path.suffix.lower() != ".json" or path.is_symlink() or not path.is_file():
            continue
        workouts.append((path, load_workout(path)))
    workouts.sort(key=lambda item: (item[1].start, item[1].source_id))
    return workouts
