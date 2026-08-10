from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

APP_DIR = Path.home() / "Library" / "Application Support" / "NRCVoltSync"
CONFIG_PATH = APP_DIR / "config.json"
GARMIN_TOKEN_DIR = APP_DIR / "garmin"
STATE_PATH = APP_DIR / "state.sqlite3"
LOCK_PATH = APP_DIR / "sync.lock"
FIT_DIR = APP_DIR / "fit"
LOG_DIR = APP_DIR / "logs"


def ensure_app_dirs() -> None:
    for path in (APP_DIR, GARMIN_TOKEN_DIR, FIT_DIR, LOG_DIR):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)


def load_config() -> dict[str, Any]:
    ensure_app_dirs()
    if not CONFIG_PATH.exists():
        return {}
    mode = CONFIG_PATH.stat().st_mode & 0o777
    if mode & 0o077:
        raise PermissionError(f"Configuration permissions are too broad: {oct(mode)}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict[str, Any]) -> None:
    ensure_app_dirs()
    fd, temporary_name = tempfile.mkstemp(prefix="config.", dir=APP_DIR)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        temporary_path.replace(CONFIG_PATH)
        CONFIG_PATH.chmod(0o600)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def redact_config(config: dict[str, Any]) -> dict[str, Any]:
    # Treat every persisted account field as private. This keeps future config
    # additions safe by default when users paste `status` output into an issue.
    return {key: "<stored>" for key in config}
