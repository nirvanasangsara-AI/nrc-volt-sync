# Public beta testing

Version 0.3 is a beta because iOS background delivery, Strava, Garmin Connect, and Nike Run Club can change behavior outside
this project's control. Automated tests use synthetic records and never require contributor
credentials or health data.

## Safe test sequence

1. Complete `docs/SETUP.md`, then run `uv run nrc-volt-sync doctor`.
2. Run `uv run nrc-volt-sync sync --after-days 14 --limit 1 --dry-run`.
3. Upload one recent run and compare its date, distance, duration, route, and available heart rate in
   Apple Health or Strava, Garmin Connect, and NRC.
4. Run the same command again and verify that it does not create a duplicate.
5. Install the automatic service only after that comparison passes.

## Test matrix

Useful reports include the macOS/iOS versions, selected source, Apple Watch model, whether the source was Apple Workout,
and whether the result reached Garmin and NRC. Test cases of particular value are outdoor GPS,
indoor treadmill, missing cadence, delayed HealthKit/Strava import, and a second run within two minutes of the
first.

## Privacy-safe reports

Run `uv run nrc-volt-sync status` and `uv run nrc-volt-sync doctor`; both are designed to avoid
printing stored secret values. Still review all text before posting it. Never attach FIT files,
route screenshots, raw provider responses, logs, email addresses, activity IDs, or files from
`~/Library/Application Support/NRCVoltSync/`.

Open a GitHub issue using synthetic identifiers. State clearly whether the problem is reproducible,
which stage failed, and whether retrying later changed the result.
