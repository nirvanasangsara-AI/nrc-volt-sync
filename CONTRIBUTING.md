# Contributing

Contributions that improve data fidelity, duplicate prevention, privacy, documentation, and provider-change resilience are welcome.

## Development setup

```bash
uv sync --dev
uv run pytest -q
uv run ruff check .
```

## Privacy rules for contributions

- Use synthetic activity IDs, dates, coordinates, names, and account values.
- Never commit FIT files, SQLite databases, local configuration, logs, OAuth tokens, Garmin session files, screenshots of routes, or exported provider responses.
- Do not paste private API payloads into issues or pull requests.
- Add a regression test using fabricated data for every data-conversion fix.
- Keep secret redaction safe by default: new persisted config fields must be hidden automatically.

## Pull requests

Explain why the change is needed, which data fields it affects, and how it was tested. Provider-specific behavior should link to official documentation when available. For unofficial APIs, describe the observed behavior without publishing credentials or personal payloads.

## Scope

NRC Volt Sync is a personal data-portability utility, not a hosted synchronization service. Features that require collecting other users' credentials or health data on a maintainer-operated server are out of scope.
