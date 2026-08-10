from __future__ import annotations

import argparse
import fcntl
import getpass
import json
import logging
import logging.handlers
import os
import plistlib
import subprocess  # nosec B404
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .config import (
    APP_DIR,
    CONFIG_PATH,
    GARMIN_TOKEN_DIR,
    LOCK_PATH,
    LOG_DIR,
    STATE_PATH,
    ensure_app_dirs,
    load_config,
    redact_config,
    save_config,
)
from .garmin import configure_garmin
from .healthkit_sync import sync_healthkit_many
from .state import State
from .strava import StravaClient, authorize
from .sync import SyncBatchResult, SyncFailure, SyncResult, sync_many

# Only fixed /bin/launchctl argument lists are executed.
LABEL = "io.github.nrcvoltsync"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LAUNCHCTL = "/bin/launchctl"


def _logging(verbose: bool = False) -> None:
    ensure_app_dirs()
    level = logging.DEBUG if verbose else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "sync.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    if sys.stderr.isatty():
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        root.addHandler(console)


@contextmanager
def _single_instance() -> Any:
    ensure_app_dirs()
    with LOCK_PATH.open("a+", encoding="utf-8") as lock:
        LOCK_PATH.chmod(0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("A sync is already running.") from None
        yield


def _date_epoch(value: str, *, end: bool = False) -> int:
    parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    if end:
        parsed += timedelta(days=1)
    return int(parsed.timestamp())


def _configure_strava(_args: argparse.Namespace) -> int:
    client_id = input("Strava Client ID: ").strip()
    client_secret = getpass.getpass("Strava Client Secret (hidden): ").strip()
    if not client_id or not client_secret:
        raise SystemExit("Strava Client ID and Secret are required.")
    token_config = authorize(client_id, client_secret)
    config = load_config()
    config.update(token_config)
    save_config(config)
    print("Strava connection complete.")
    return 0


def _configure_garmin(args: argparse.Namespace) -> int:
    configure_garmin(args.email)
    print("Garmin connection complete.")
    return 0


def _existing_directory(value: str, label: str) -> Path:
    try:
        path = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"{label} is not accessible: {error}") from error
    if not path.is_dir():
        raise SystemExit(f"{label} must be an existing directory.")
    return path


def _configure_healthkit(args: argparse.Namespace) -> int:
    raw_outbox = args.outbox or input("Apple Health outbox folder: ").strip()
    if not raw_outbox:
        raise SystemExit("Apple Health outbox folder is required.")
    outbox = _existing_directory(raw_outbox, "Apple Health outbox")
    config = load_config()
    config["healthkit_outbox"] = str(outbox)
    if args.fit_export_dir:
        config["fit_export_dir"] = str(
            _existing_directory(args.fit_export_dir, "FIT export destination")
        )
    elif args.no_fit_export:
        config.pop("fit_export_dir", None)
    save_config(config)
    print("Apple Health outbox connection complete.")
    return 0


def _inspect(args: argparse.Namespace) -> int:
    with StravaClient() as client:
        detail = client.activity(args.activity_id)
        streams = client.streams(args.activity_id)
    safe = {
        "id": detail.get("id"),
        "name": detail.get("name"),
        "sport_type": detail.get("sport_type"),
        "start_date": detail.get("start_date"),
        "distance_m": detail.get("distance"),
        "moving_time_s": detail.get("moving_time"),
        "elapsed_time_s": detail.get("elapsed_time"),
        "device_name": detail.get("device_name"),
        "external_id": detail.get("external_id"),
        "streams": {key: len(value.get("data") or []) for key, value in streams.items()},
    }
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0


def _print_result(result: SyncResult) -> None:
    distance_km = result.distance_m / 1000
    details = ""
    if result.validation:
        details = (
            f", GPS records {result.validation.gps_records}, "
            f"heart-rate records {result.validation.heart_rate_records}"
        )
    print(
        f"{result.status}: {result.name} / {distance_km:.2f} km{details}"
        + (f" / Garmin {result.garmin_id}" if result.garmin_id else "")
    )


def _sync(args: argparse.Namespace) -> int:
    if args.limit < 1 or (args.after_days is not None and args.after_days < 1):
        raise SystemExit("Limit and lookback days must be positive.")
    after = _date_epoch(args.after) if args.after else None
    before = _date_epoch(args.before, end=True) if args.before else None
    if args.after_days is not None:
        after = int((datetime.now(UTC) - timedelta(days=args.after_days)).timestamp())
    source = args.source
    config: dict[str, Any] = {}
    if source in {"auto", "healthkit"}:
        config = load_config()
    strava_fields = {
        "strava_client_id",
        "strava_client_secret",
        "strava_access_token",
        "strava_refresh_token",
        "strava_expires_at",
    }
    sources: list[str]
    if source == "auto":
        sources = []
        if config.get("healthkit_outbox"):
            sources.append("healthkit")
        if strava_fields.issubset(config):
            sources.append("strava")
    else:
        sources = [source]
    if args.activity_id is not None:
        sources = [item for item in sources if item == "strava"]
    if args.healthkit_id is not None:
        sources = [item for item in sources if item == "healthkit"]
    if not sources:
        raise SystemExit("No requested source is configured. Run a configure command first.")

    results: list[SyncResult] = []
    failures: list[SyncFailure] = []
    scanned = 0
    with _single_instance():
        for selected in sources:
            remaining = max(0, args.limit - len(results))
            if remaining == 0:
                break
            if selected == "healthkit":
                outbox = config.get("healthkit_outbox")
                if not outbox:
                    raise SystemExit("Apple Health outbox is not configured.")
                fit_export = config.get("fit_export_dir")
                current = sync_healthkit_many(
                    outbox=Path(str(outbox)),
                    workout_id=args.healthkit_id,
                    after=after,
                    before=before,
                    limit=remaining,
                    dry_run=args.dry_run,
                    fit_export_dir=Path(str(fit_export)) if fit_export else None,
                )
            else:
                current = sync_many(
                    activity_id=args.activity_id,
                    after=after,
                    before=before,
                    limit=remaining,
                    dry_run=args.dry_run,
                    only_apple_watch=not args.all_non_garmin,
                )
            results.extend(current.results)
            failures.extend(current.failures)
            scanned += current.scanned
    batch = SyncBatchResult(results=results, failures=failures, scanned=scanned)
    for result in batch.results:
        _print_result(result)
    for failure in batch.failures:
        identifier = failure.source_id or "unknown"
        print(
            f"FAILED {failure.source} activity {identifier}: "
            f"{failure.error_type}: {failure.message}",
            file=sys.stderr,
        )
    if batch.failures:
        print(
            f"Sync completed with {len(batch.failures)} failure(s); failed activities will retry.",
            file=sys.stderr,
        )
        return 1
    if not batch.results:
        print("No new eligible runs to upload.")
    return 0


def _status(_args: argparse.Namespace) -> int:
    config = load_config()
    with State() as state:
        summary = state.summary()
    # Fixed absolute macOS system command with no shell interpolation.
    service = subprocess.run(  # nosec B603
        [LAUNCHCTL, "print", f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
        check=False,
    )
    safe_status = {
        "config": redact_config(config),
        "config_path": str(CONFIG_PATH).replace(str(Path.home()), "~", 1),
        "garmin_tokens": (GARMIN_TOKEN_DIR / "garmin_tokens.json").exists(),
        "state_path": str(STATE_PATH).replace(str(Path.home()), "~", 1),
        "sync_summary": summary,
        "automatic_service_loaded": service.returncode == 0,
    }
    print(json.dumps(safe_status, ensure_ascii=False, indent=2))
    return 0


def _doctor(_args: argparse.Namespace) -> int:
    config = load_config()
    strava_fields = {
        "strava_client_id",
        "strava_client_secret",
        "strava_access_token",
        "strava_refresh_token",
        "strava_expires_at",
    }
    # Fixed absolute macOS system command with no shell interpolation.
    service = subprocess.run(  # nosec B603
        [LAUNCHCTL, "print", f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
        check=False,
    )
    healthkit_value = config.get("healthkit_outbox")
    healthkit_configured = bool(
        healthkit_value and Path(str(healthkit_value)).expanduser().is_dir()
    )
    checks = {
        "python_3_12": sys.version_info[:2] == (3, 12),
        "strava_configured": strava_fields.issubset(config),
        "healthkit_outbox_configured": healthkit_configured,
        "at_least_one_source_configured": healthkit_configured
        or strava_fields.issubset(config),
        "garmin_configured": (GARMIN_TOKEN_DIR / "garmin_tokens.json").exists(),
        "private_app_directory": (APP_DIR.stat().st_mode & 0o077) == 0,
        "automatic_service_loaded": service.returncode == 0,
        "nike_garmin_link": "verify manually in NRC Settings > Partners",
    }
    print(json.dumps(checks, indent=2))
    required = (
        "python_3_12",
        "at_least_one_source_configured",
        "garmin_configured",
        "private_app_directory",
    )
    return 0 if all(checks[key] is True for key in required) else 1


def _install_service(args: argparse.Namespace) -> int:
    ensure_app_dirs()
    if args.interval_minutes < 1 or args.lookback_days < 1 or args.limit < 1:
        raise SystemExit("Interval, lookback, and limit must all be positive.")
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            "-m",
            "nrc_volt_sync.cli",
            "sync",
            "--after-days",
            str(args.lookback_days),
            "--limit",
            str(args.limit),
        ],
        "RunAtLoad": True,
        "StartInterval": args.interval_minutes * 60,
        "ProcessType": "Background",
        "StandardOutPath": str(LOG_DIR / "launchd.out.log"),
        "StandardErrorPath": str(LOG_DIR / "launchd.err.log"),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
    }
    temporary = PLIST_PATH.with_suffix(".plist.tmp")
    temporary.write_bytes(plistlib.dumps(plist, sort_keys=True))
    temporary.chmod(0o600)
    temporary.replace(PLIST_PATH)
    PLIST_PATH.chmod(0o600)
    domain = f"gui/{os.getuid()}"
    # Fixed absolute macOS system commands with no shell interpolation.
    subprocess.run(  # nosec B603
        [LAUNCHCTL, "bootout", domain, str(PLIST_PATH)],
        capture_output=True,
        check=False,
    )
    subprocess.run(  # nosec B603
        [LAUNCHCTL, "bootstrap", domain, str(PLIST_PATH)], check=True
    )
    subprocess.run(  # nosec B603
        [LAUNCHCTL, "enable", f"{domain}/{LABEL}"], check=True
    )
    subprocess.run(  # nosec B603
        [LAUNCHCTL, "kickstart", f"{domain}/{LABEL}"], check=True
    )
    print(f"Installed and started automatic sync every {args.interval_minutes} minute(s).")
    return 0


def _uninstall_service(_args: argparse.Namespace) -> int:
    domain = f"gui/{os.getuid()}"
    # Fixed absolute macOS system command with no shell interpolation.
    subprocess.run(  # nosec B603
        [LAUNCHCTL, "bootout", domain, str(PLIST_PATH)],
        capture_output=True,
        check=False,
    )
    PLIST_PATH.unlink(missing_ok=True)
    print("Automatic sync service removed. Account tokens and sync history were kept.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nrc-volt-sync")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    command = sub.add_parser("configure-strava", help="Connect Strava OAuth")
    command.set_defaults(func=_configure_strava)

    command = sub.add_parser("configure-garmin", help="Connect Garmin")
    command.add_argument("--email")
    command.set_defaults(func=_configure_garmin)

    command = sub.add_parser(
        "configure-healthkit", help="Connect an iPhone Apple Health outbox folder"
    )
    command.add_argument("--outbox")
    export = command.add_mutually_exclusive_group()
    export.add_argument("--fit-export-dir")
    export.add_argument("--no-fit-export", action="store_true")
    command.set_defaults(func=_configure_healthkit)

    command = sub.add_parser("inspect-activity", help="Inspect activity and stream metadata")
    command.add_argument("activity_id", type=int)
    command.set_defaults(func=_inspect)

    command = sub.add_parser("sync", help="Sync Apple Watch runs")
    command.add_argument("--source", choices=("auto", "strava", "healthkit"), default="auto")
    command.add_argument("--activity-id", type=int)
    command.add_argument("--healthkit-id")
    command.add_argument("--after", help="YYYY-MM-DD")
    command.add_argument("--before", help="YYYY-MM-DD")
    command.add_argument("--after-days", type=int)
    command.add_argument("--limit", type=int, default=25)
    command.add_argument("--dry-run", action="store_true")
    command.add_argument(
        "--all-non-garmin",
        action="store_true",
        help="Include non-Garmin runs without an Apple Watch source marker",
    )
    command.set_defaults(func=_sync)

    command = sub.add_parser("status", help="Show redacted connection and sync status")
    command.set_defaults(func=_status)

    command = sub.add_parser("doctor", help="Check prerequisites without exposing secrets")
    command.set_defaults(func=_doctor)

    command = sub.add_parser("install-service", help="Install 15-minute automatic sync")
    command.add_argument("--interval-minutes", type=int, default=15)
    command.add_argument("--lookback-days", type=int, default=14)
    command.add_argument("--limit", type=int, default=10)
    command.set_defaults(func=_install_service)

    command = sub.add_parser("uninstall-service", help="Remove automatic sync")
    command.set_defaults(func=_uninstall_service)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _logging(args.verbose)
    started = time.monotonic()
    try:
        return int(args.func(args))
    finally:
        logging.getLogger(__name__).info(
            "command=%s elapsed=%.2fs", args.command, time.monotonic() - started
        )


if __name__ == "__main__":
    raise SystemExit(main())
