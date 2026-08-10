# Repository instructions for AI coding agents

## Mission

Preserve a runner's own Apple Watch activity data while moving eligible runs from Strava to Garmin Connect for delivery through the user's Nike Run Club partner connection.

## Non-negotiable privacy rules

- Never read, print, commit, upload, or request files from `~/Library/Application Support/NRCVoltSync/`.
- Never use real FIT files, tokens, emails, activity IDs, GPS coordinates, provider payloads, logs, or screenshots in tests or examples.
- Use synthetic data only. Coordinates and identifiers in tests must be obviously fabricated.
- New configuration fields must remain redacted by default.
- Do not add telemetry, analytics, hosted credential storage, or maintainer-operated data collection.

## Data-fidelity rules

- Do not fabricate GPS, heart rate, cadence, altitude, power, timestamps, or distance.
- A summary-only FIT may use only real activity-level distance and time.
- Preserve source streams at their available resolution.
- Keep Garmin-origin and completed activities out of the upload path.
- Duplicate prevention must remain conservative and independently testable.

## Provider boundaries

- Prefer official Strava and Nike documentation for documented behavior.
- Treat Garmin private API behavior as unstable and isolate it in `garmin.py`.
- Do not imply affiliation with Nike, Strava, Garmin, or Apple.
- Do not add any mechanism that bypasses account authentication or provider authorization.

## Required validation

```bash
uv run pytest -q
uv run ruff check .
```

Add synthetic regression tests for FIT conversion, duplicate detection, redaction, and any provider-response parsing change.
