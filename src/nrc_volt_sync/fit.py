from __future__ import annotations

import hashlib
import math
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from garmin_fit_sdk import FIT_EPOCH_S, Decoder, Encoder, Stream
from garmin_fit_sdk.profile import Profile


class FitDataError(ValueError):
    pass


@dataclass(frozen=True)
class FitValidation:
    record_count: int
    distance_m: float
    elapsed_s: float
    heart_rate_records: int
    gps_records: int
    fingerprint: str


def _data(streams: dict[str, dict[str, Any]], name: str) -> list[Any]:
    stream = streams.get(name) or {}
    values = stream.get("data") or []
    return values if isinstance(values, list) else []


def _at(values: list[Any], index: int) -> Any:
    return values[index] if index < len(values) else None


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _semicircles(degrees: float) -> int:
    return round(float(degrees) * (2**31 / 180.0))


def _positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _summary(values: list[Any]) -> tuple[float | None, float | None]:
    numbers = [_positive_number(value) for value in values]
    clean = [number for number in numbers if number is not None]
    if not clean:
        return None, None
    return statistics.fmean(clean), max(clean)


def _elevation_change(altitudes: list[Any]) -> tuple[float, float]:
    clean = [_positive_number(value) for value in altitudes]
    ascent = 0.0
    descent = 0.0
    previous: float | None = None
    for altitude in clean:
        if altitude is None:
            continue
        if previous is not None:
            change = altitude - previous
            if change > 0:
                ascent += change
            else:
                descent -= change
        previous = altitude
    return ascent, descent


def _cadence_multiplier(cadences: list[Any]) -> int:
    clean = [float(value) for value in cadences if _positive_number(value) is not None]
    if not clean:
        return 1
    # Strava commonly exposes running cadence as strides/minute while FIT uses steps/minute.
    return 2 if statistics.median(clean) < 130 else 1


def activity_fingerprint(detail: dict[str, Any]) -> str:
    raw = "|".join(
        (
            str(detail.get("start_date", "")),
            str(round(float(detail.get("distance", 0)))),
            str(round(float(detail.get("elapsed_time", 0)))),
            str(detail.get("sport_type") or detail.get("type") or ""),
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def encode_activity(detail: dict[str, Any], streams: dict[str, dict[str, Any]]) -> bytes:
    if not detail.get("start_date"):
        raise FitDataError("Activity has no UTC start date")
    times = _data(streams, "time")
    distances = _data(streams, "distance")
    if len(times) < 2 or len(distances) < 2:
        # Some Apple Watch uploads retain only activity-level distance and time in
        # Strava. Preserve those real summary values in two endpoint records;
        # never fabricate a route, heart rate, or cadence stream.
        elapsed_summary = _positive_number(detail.get("elapsed_time"))
        distance_summary = _positive_number(detail.get("distance"))
        if not elapsed_summary or distance_summary is None:
            raise FitDataError("Activity has insufficient time/distance data")
        times = [0, int(elapsed_summary)]
        distances = [0.0, distance_summary]

    latlng = _data(streams, "latlng")
    altitudes = _data(streams, "altitude")
    heart_rates = _data(streams, "heartrate")
    cadences = _data(streams, "cadence")
    watts = _data(streams, "watts")
    moving = _data(streams, "moving")

    start_dt = _parse_utc(str(detail["start_date"]))
    start_time = int(start_dt.timestamp()) - FIT_EPOCH_S
    stream_elapsed = max(int(float(value)) for value in times)
    elapsed_s = max(stream_elapsed, int(float(detail.get("elapsed_time") or 0)))
    moving_s = int(float(detail.get("moving_time") or elapsed_s))
    end_time = start_time + elapsed_s
    timezone_offset = int(float(detail.get("utc_offset") or 0))
    distance_m = float(detail.get("distance") or distances[-1] or 0)
    average_speed = _positive_number(detail.get("average_speed"))
    max_speed = _positive_number(detail.get("max_speed"))
    average_hr, max_hr = _summary(heart_rates)
    cadence_factor = _cadence_multiplier(cadences)
    corrected_cadences = [
        float(value) * cadence_factor for value in cadences if _positive_number(value) is not None
    ]
    average_cadence, max_cadence = _summary(corrected_cadences)
    average_power, max_power = _summary(watts)
    calculated_ascent, calculated_descent = _elevation_change(altitudes)
    total_ascent = _positive_number(detail.get("total_elevation_gain"))
    if total_ascent is None:
        total_ascent = calculated_ascent
    calories = _positive_number(detail.get("calories"))
    serial_number = int(detail.get("id") or 1) & 0xFFFFFFFF

    messages: list[dict[str, Any]] = [
        {
            "mesg_num": Profile["mesg_num"]["FILE_ID"],
            "type": "activity",
            "manufacturer": "development",
            "product": 0,
            "time_created": start_time,
            "serial_number": serial_number,
        },
        {
            "mesg_num": Profile["mesg_num"]["DEVICE_INFO"],
            "device_index": "creator",
            "manufacturer": "development",
            "product": 0,
            "product_name": "NRC Volt Sync",
            "serial_number": serial_number,
            "software_version": 0.1,
            "timestamp": start_time,
        },
        {
            "mesg_num": Profile["mesg_num"]["EVENT"],
            "timestamp": start_time,
            "event": "timer",
            "event_type": "start",
        },
    ]

    previous_moving = True
    for index, offset in enumerate(times):
        offset_s = int(float(offset))
        timestamp = start_time + offset_s
        is_moving = bool(_at(moving, index)) if moving else True
        if is_moving != previous_moving:
            messages.append(
                {
                    "mesg_num": Profile["mesg_num"]["EVENT"],
                    "timestamp": timestamp,
                    "event": "timer",
                    "event_type": "start" if is_moving else "stop_all",
                }
            )
            previous_moving = is_moving

        record: dict[str, Any] = {
            "mesg_num": Profile["mesg_num"]["RECORD"],
            "timestamp": timestamp,
        }
        point_distance = _positive_number(_at(distances, index))
        if point_distance is not None:
            record["distance"] = point_distance
        if index > 0:
            previous_distance = _positive_number(_at(distances, index - 1))
            previous_time = int(float(_at(times, index - 1)))
            delta_time = offset_s - previous_time
            if point_distance is not None and previous_distance is not None and delta_time > 0:
                record["enhanced_speed"] = max(
                    0.0, (point_distance - previous_distance) / delta_time
                )
        heart_rate = _positive_number(_at(heart_rates, index))
        if heart_rate is not None:
            record["heart_rate"] = min(255, round(heart_rate))
        cadence = _positive_number(_at(cadences, index))
        if cadence is not None:
            record["cadence"] = min(255, round(cadence * cadence_factor))
        power = _positive_number(_at(watts, index))
        if power is not None:
            record["power"] = min(65534, round(power))
        altitude = _positive_number(_at(altitudes, index))
        if altitude is not None:
            record["enhanced_altitude"] = altitude
        coordinate = _at(latlng, index)
        if isinstance(coordinate, list) and len(coordinate) == 2:
            latitude, longitude = coordinate
            if latitude is not None and longitude is not None:
                record["position_lat"] = _semicircles(float(latitude))
                record["position_long"] = _semicircles(float(longitude))
        messages.append(record)

    messages.append(
        {
            "mesg_num": Profile["mesg_num"]["EVENT"],
            "timestamp": end_time,
            "event": "timer",
            "event_type": "stop_all",
        }
    )

    common_summary: dict[str, Any] = {
        "timestamp": end_time,
        "start_time": start_time,
        "total_elapsed_time": elapsed_s,
        "total_timer_time": moving_s,
        "total_distance": distance_m,
        "sport": "running",
        "sub_sport": "generic",
        "total_ascent": round(total_ascent),
        "total_descent": round(calculated_descent),
    }
    optional = {
        "avg_speed": average_speed,
        "max_speed": max_speed,
        "avg_heart_rate": round(average_hr) if average_hr is not None else None,
        "max_heart_rate": round(max_hr) if max_hr is not None else None,
        "avg_running_cadence": (round(average_cadence) if average_cadence is not None else None),
        "max_running_cadence": round(max_cadence) if max_cadence is not None else None,
        "avg_power": round(average_power) if average_power is not None else None,
        "max_power": round(max_power) if max_power is not None else None,
        "total_calories": round(calories) if calories is not None else None,
    }
    common_summary.update({key: value for key, value in optional.items() if value is not None})

    lap = dict(common_summary)
    lap.update(
        {
            "mesg_num": Profile["mesg_num"]["LAP"],
            "message_index": 0,
            "event": "lap",
            "event_type": "stop",
            "lap_trigger": "session_end",
        }
    )
    messages.append(lap)

    session = dict(common_summary)
    session.update(
        {
            "mesg_num": Profile["mesg_num"]["SESSION"],
            "message_index": 0,
            "event": "session",
            "event_type": "stop",
            "first_lap_index": 0,
            "num_laps": 1,
        }
    )
    messages.append(session)
    messages.append(
        {
            "mesg_num": Profile["mesg_num"]["ACTIVITY"],
            "timestamp": end_time,
            "num_sessions": 1,
            "local_timestamp": end_time + timezone_offset,
            "total_timer_time": moving_s,
        }
    )

    encoder = Encoder()
    for message in messages:
        encoder.write_mesg(message)
    return bytes(encoder.close())


def validate_activity(
    data: bytes, *, expected_distance_m: float, expected_elapsed_s: float
) -> FitValidation:
    if not Decoder(Stream.from_byte_array(bytearray(data))).check_integrity():
        raise FitDataError("FIT CRC/integrity validation failed")
    decoded, errors = Decoder(Stream.from_byte_array(bytearray(data))).read()
    if errors:
        raise FitDataError(f"FIT decode validation failed: {errors[0]}")
    records = decoded.get("record_mesgs") or []
    sessions = decoded.get("session_mesgs") or []
    if len(records) < 2 or len(sessions) != 1:
        raise FitDataError("FIT activity structure is incomplete")
    session = sessions[0]
    actual_distance = float(session.get("total_distance") or 0)
    actual_elapsed = float(session.get("total_elapsed_time") or 0)
    distance_tolerance = max(5.0, expected_distance_m * 0.001)
    if abs(actual_distance - expected_distance_m) > distance_tolerance:
        raise FitDataError(
            f"FIT distance mismatch ({actual_distance:.1f} vs {expected_distance_m:.1f} m)"
        )
    if abs(actual_elapsed - expected_elapsed_s) > 2:
        raise FitDataError(
            f"FIT elapsed-time mismatch ({actual_elapsed:.1f} vs {expected_elapsed_s:.1f} s)"
        )
    return FitValidation(
        record_count=len(records),
        distance_m=actual_distance,
        elapsed_s=actual_elapsed,
        heart_rate_records=sum(1 for record in records if record.get("heart_rate") is not None),
        gps_records=sum(
            1
            for record in records
            if record.get("position_lat") is not None and record.get("position_long") is not None
        ),
        fingerprint=hashlib.sha256(data).hexdigest(),
    )


def write_validated_fit(
    detail: dict[str, Any], streams: dict[str, dict[str, Any]], destination: Path
) -> FitValidation:
    data = encode_activity(detail, streams)
    validation = validate_activity(
        data,
        expected_distance_m=float(detail.get("distance") or 0),
        expected_elapsed_s=float(detail.get("elapsed_time") or 0),
    )
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.write_bytes(data)
    destination.chmod(0o600)
    return validation
