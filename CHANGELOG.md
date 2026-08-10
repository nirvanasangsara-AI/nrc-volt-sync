# Changelog

All notable changes are documented here. NRC Volt Sync follows semantic versioning while the
provider integrations remain beta.

## Unreleased

## 0.3.0 - 2026-08-10

- Add an open-source iOS 17 HealthKit companion and user-selected Files outbox for direct,
  Strava-free Apple Watch run ingestion.
- Preserve real HealthKit route and sensor timestamps, including heart rate, distance, speed, power,
  stride length, vertical oscillation, and ground-contact time; never synthesize cadence.
- Add `configure-healthkit`, source auto-selection, historical HealthKit backfill, optional portable
  FIT export, Garmin-origin filtering, and automatic-service compatibility.
- Migrate the duplicate database from a Strava-only key to `(source, source ID)` while preserving
  prior completion state and removing legacy raw provider payloads.
- Add synthetic Python and Swift schema tests plus a CI-built unsigned iOS simulator target.
- Document free Apple personal signing, iOS background timing, privacy boundaries, and manual FIT
  reuse for services with official import support.

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
