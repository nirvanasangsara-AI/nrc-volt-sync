# Copilot instructions

NRC Volt Sync is a privacy-sensitive personal data-portability CLI. Follow `AGENTS.md` and read `PRIVACY.md` before changing authentication, logging, FIT generation, or local storage.

Use only synthetic workout data. Never suggest attaching real FIT files or unredacted logs to issues. Missing sensor fields must stay missing. Maintain conservative duplicate checks and owner-only runtime file permissions.

Run `uv run pytest -q` and `uv run ruff check .` after every code change.
