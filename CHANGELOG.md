# Changelog

All notable changes are documented here. NRC Volt Sync follows semantic versioning while the
provider integrations remain beta.

## Unreleased

- Document free paths for runners without an existing Strava account, including the manual Apple
  Health export fallback and its sensor-data limits.
- Publish the source boundary and roadmap for a direct iPhone HealthKit companion and portable FIT
  outbox.

## 0.2.0 - 2026-08-10

- Return a non-zero exit code when any activity fails, while continuing the remaining batch.
- Remove raw Garmin provider responses from the local state database and migrate existing data.
- Discard orphan sensor streams when a FIT file must use a summary-only timeline.
- Use the absolute macOS `launchctl` path for background-service operations.
- Expand synthetic test coverage to the CLI, configuration, Strava, Garmin, state migration,
  duplicate handling, and upload failure paths; enforce at least 80% coverage in CI.
- Add dependency-update automation, third-party notices, and a public beta test guide.

## 0.1.0 - 2026-08-09

- Initial public alpha with Apple Watch/Strava to Garmin Connect run conversion and sync.
