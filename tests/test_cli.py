import argparse
import json
import plistlib
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from nrc_volt_sync import cli
from nrc_volt_sync.sync import SyncBatchResult, SyncFailure, SyncResult


def _sync_args(**overrides):
    values = {
        "after": None,
        "before": None,
        "after_days": None,
        "activity_id": None,
        "limit": 25,
        "dry_run": False,
        "all_non_garmin": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_sync_command_reports_failure_and_nonzero(monkeypatch, capsys) -> None:
    batch = SyncBatchResult(
        results=[SyncResult(101, "uploaded", "Synthetic Run", 5000.0, garmin_id="202")],
        failures=[SyncFailure(102, "RuntimeError", "synthetic failure")],
        scanned=2,
    )
    monkeypatch.setattr(cli, "_single_instance", nullcontext)
    monkeypatch.setattr(cli, "sync_many", lambda **_kwargs: batch)

    assert cli._sync(_sync_args(after="2024-01-01", before="2024-01-31")) == 1
    output = capsys.readouterr()
    assert "5.00 km" in output.out
    assert "FAILED activity 102" in output.err


def test_sync_command_reports_clean_empty_run(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_single_instance", nullcontext)
    monkeypatch.setattr(
        cli, "sync_many", lambda **_kwargs: SyncBatchResult([], [], scanned=0)
    )
    assert cli._sync(_sync_args(after_days=14)) == 0
    assert "No new Apple Watch runs" in capsys.readouterr().out


def test_inspect_prints_safe_metadata_only(monkeypatch, capsys) -> None:
    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def activity(self, _activity_id):
            return {"id": 101, "name": "Synthetic", "distance": 5000, "token": "secret"}

        def streams(self, _activity_id):
            return {"time": {"data": [0, 1]}, "latlng": {"data": [[0, 0]]}}

    monkeypatch.setattr(cli, "StravaClient", Client)
    assert cli._inspect(argparse.Namespace(activity_id=101)) == 0
    printed = capsys.readouterr().out
    assert json.loads(printed)["streams"] == {"time": 2, "latlng": 1}
    assert "secret" not in printed


def test_doctor_redacts_and_checks_requirements(tmp_path, monkeypatch, capsys) -> None:
    token_dir = tmp_path / "garmin"
    token_dir.mkdir()
    (token_dir / "garmin_tokens.json").write_text("{}", encoding="utf-8")
    app_dir = tmp_path / "app"
    app_dir.mkdir(mode=0o700)
    config = {
        "strava_client_id": "x",
        "strava_client_secret": "secret",
        "strava_access_token": "secret",
        "strava_refresh_token": "secret",
        "strava_expires_at": 1,
    }
    monkeypatch.setattr(cli, "GARMIN_TOKEN_DIR", token_dir)
    monkeypatch.setattr(cli, "APP_DIR", app_dir)
    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(cli.sys, "version_info", (3, 12, 0))

    assert cli._doctor(argparse.Namespace()) == 0
    printed = capsys.readouterr().out
    assert json.loads(printed)["automatic_service_loaded"] is True
    assert "secret" not in printed


def test_install_and_uninstall_service(tmp_path, monkeypatch, capsys) -> None:
    plist_path = tmp_path / "LaunchAgents" / "service.plist"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    commands = []
    monkeypatch.setattr(cli, "PLIST_PATH", plist_path)
    monkeypatch.setattr(cli, "LOG_DIR", log_dir)
    monkeypatch.setattr(cli, "ensure_app_dirs", lambda: None)
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda command, **kwargs: commands.append((command, kwargs))
        or SimpleNamespace(returncode=0),
    )
    args = argparse.Namespace(interval_minutes=15, lookback_days=14, limit=10)

    assert cli._install_service(args) == 0
    plist = plistlib.loads(plist_path.read_bytes())
    assert plist["StartInterval"] == 900
    assert "--after-days" in plist["ProgramArguments"]
    assert all(command[0][0] == "/bin/launchctl" for command in commands)
    assert cli._uninstall_service(argparse.Namespace()) == 0
    assert not plist_path.exists()
    assert "kept" in capsys.readouterr().out


def test_install_service_rejects_nonpositive_values() -> None:
    with pytest.raises(SystemExit, match="must all be positive"):
        cli._install_service(
            argparse.Namespace(interval_minutes=0, lookback_days=14, limit=10)
        )


def test_parser_routes_status_command() -> None:
    args = cli.build_parser().parse_args(["status"])
    assert args.func is cli._status
    assert cli._date_epoch("1970-01-01") == 0
    assert cli._date_epoch("1970-01-01", end=True) == 86400
