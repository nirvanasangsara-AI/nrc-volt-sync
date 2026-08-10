import json

import pytest

from nrc_volt_sync import config


def _use_temp_paths(monkeypatch, tmp_path) -> None:
    app = tmp_path / "NRCVoltSync"
    monkeypatch.setattr(config, "APP_DIR", app)
    monkeypatch.setattr(config, "CONFIG_PATH", app / "config.json")
    monkeypatch.setattr(config, "GARMIN_TOKEN_DIR", app / "garmin")
    monkeypatch.setattr(config, "FIT_DIR", app / "fit")
    monkeypatch.setattr(config, "LOG_DIR", app / "logs")


def test_config_round_trip_and_permissions(tmp_path, monkeypatch) -> None:
    _use_temp_paths(monkeypatch, tmp_path)
    assert config.load_config() == {}

    config.save_config({"token": "synthetic-secret", "athlete": 101})

    assert config.load_config()["athlete"] == 101
    assert config.CONFIG_PATH.stat().st_mode & 0o777 == 0o600
    assert config.APP_DIR.stat().st_mode & 0o777 == 0o700
    assert config.redact_config(config.load_config()) == {
        "athlete": "<stored>",
        "token": "<stored>",
    }


def test_load_config_rejects_public_permissions(tmp_path, monkeypatch) -> None:
    _use_temp_paths(monkeypatch, tmp_path)
    config.ensure_app_dirs()
    config.CONFIG_PATH.write_text(json.dumps({"token": "synthetic"}), encoding="utf-8")
    config.CONFIG_PATH.chmod(0o644)

    with pytest.raises(PermissionError, match="too broad"):
        config.load_config()
