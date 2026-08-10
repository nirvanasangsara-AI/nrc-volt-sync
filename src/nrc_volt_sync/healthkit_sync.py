from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

from .config import FIT_DIR
from .fit import FitValidation, write_validated_healthkit_fit
from .garmin import activity_id as garmin_activity_id
from .garmin import connect_garmin, find_matching_activity, upload_and_confirm
from .healthkit import HealthKitDataError, HealthWorkout, load_workout, workout_fingerprint
from .state import State
from .sync import SyncBatchResult, SyncFailure, SyncResult

LOGGER = logging.getLogger(__name__)


def _is_garmin_origin(workout: HealthWorkout) -> bool:
    source = f"{workout.device_name or ''} {workout.source_bundle_id or ''}".lower()
    return "garmin" in source


def _export_fit(source: Path, export_dir: Path, source_id: str) -> Path:
    root = export_dir.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise HealthKitDataError("FIT export destination must be a directory")
    destination = root / f"healthkit-{source_id}.fit"
    fd, temporary_name = tempfile.mkstemp(prefix=".nrc-volt-sync-", suffix=".fit", dir=root)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as target, source.open("rb") as input_file:
            shutil.copyfileobj(input_file, target)
        temporary.replace(destination)
        destination.chmod(0o600)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def sync_healthkit_workout(
    state: State,
    workout: HealthWorkout,
    *,
    dry_run: bool,
    fit_export_dir: Path | None,
) -> SyncResult | None:
    if state.is_complete("healthkit", workout.source_id):
        return None
    fingerprint = workout_fingerprint(workout)
    if _is_garmin_origin(workout):
        state.record(
            source="healthkit",
            source_id=workout.source_id,
            fingerprint=fingerprint,
            activity_start=workout.start_iso,
            distance_m=workout.distance_m,
            device_name=workout.device_name,
            status="skipped",
            error="Garmin-origin activity",
        )
        return SyncResult(
            "healthkit",
            workout.source_id,
            "skipped_garmin_source",
            workout.name,
            workout.distance_m,
        )

    fit_path = FIT_DIR / f"healthkit-{workout.source_id}.fit"
    validation: FitValidation = write_validated_healthkit_fit(workout, fit_path)
    if fit_export_dir is not None:
        _export_fit(fit_path, fit_export_dir, workout.source_id)
    state.record(
        source="healthkit",
        source_id=workout.source_id,
        fingerprint=fingerprint,
        activity_start=workout.start_iso,
        distance_m=workout.distance_m,
        device_name=workout.device_name,
        status="validated",
    )
    if dry_run:
        return SyncResult(
            "healthkit",
            workout.source_id,
            "validated",
            workout.name,
            workout.distance_m,
            validation,
        )

    garmin = connect_garmin()
    existing = find_matching_activity(
        garmin,
        start=workout.start,
        distance_m=workout.distance_m,
        elapsed_s=workout.elapsed_s,
    )
    if existing:
        existing_id = garmin_activity_id(existing)
        state.record(
            source="healthkit",
            source_id=workout.source_id,
            fingerprint=fingerprint,
            activity_start=workout.start_iso,
            distance_m=workout.distance_m,
            device_name=workout.device_name,
            status="already_on_garmin",
            garmin_id=existing_id,
        )
        return SyncResult(
            "healthkit",
            workout.source_id,
            "already_on_garmin",
            workout.name,
            workout.distance_m,
            validation,
            existing_id,
        )

    try:
        response, confirmed = upload_and_confirm(
            garmin,
            fit_path,
            start=workout.start,
            distance_m=workout.distance_m,
            elapsed_s=workout.elapsed_s,
        )
        confirmed_id = garmin_activity_id(confirmed) or garmin_activity_id(response)
        state.record(
            source="healthkit",
            source_id=workout.source_id,
            fingerprint=fingerprint,
            activity_start=workout.start_iso,
            distance_m=workout.distance_m,
            device_name=workout.device_name,
            status="uploaded",
            garmin_id=confirmed_id,
            increment_attempts=True,
        )
        return SyncResult(
            "healthkit",
            workout.source_id,
            "uploaded",
            workout.name,
            workout.distance_m,
            validation,
            confirmed_id,
        )
    except Exception as error:
        state.record(
            source="healthkit",
            source_id=workout.source_id,
            fingerprint=fingerprint,
            activity_start=workout.start_iso,
            distance_m=workout.distance_m,
            device_name=workout.device_name,
            status="failed",
            error=f"{type(error).__name__}: {error}"[:1000],
            increment_attempts=True,
        )
        raise


def sync_healthkit_many(
    *,
    outbox: Path,
    workout_id: str | None = None,
    after: int | None = None,
    before: int | None = None,
    limit: int = 25,
    dry_run: bool = False,
    fit_export_dir: Path | None = None,
) -> SyncBatchResult:
    root = outbox.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise HealthKitDataError("HealthKit outbox must be a directory")
    results: list[SyncResult] = []
    failures: list[SyncFailure] = []
    scanned = 0
    paths = sorted(
        path
        for path in root.iterdir()
        if path.suffix.lower() == ".json" and not path.is_symlink() and path.is_file()
    )
    with State() as state:
        for path in paths:
            if len(results) >= limit:
                break
            current_id: str | None = None
            try:
                workout = load_workout(path)
                current_id = workout.source_id
                if workout_id is not None and workout.source_id != workout_id:
                    continue
                timestamp = int(workout.start.timestamp())
                if after is not None and timestamp < after:
                    continue
                if before is not None and timestamp >= before:
                    continue
                scanned += 1
                result = sync_healthkit_workout(
                    state,
                    workout,
                    dry_run=dry_run,
                    fit_export_dir=fit_export_dir,
                )
            except Exception as error:
                LOGGER.exception("HealthKit workout failed")
                failures.append(
                    SyncFailure(
                        source="healthkit",
                        source_id=current_id,
                        error_type=type(error).__name__,
                        message=str(error)[:500],
                    )
                )
                continue
            if result is not None:
                results.append(result)
    return SyncBatchResult(results=results, failures=failures, scanned=scanned)
