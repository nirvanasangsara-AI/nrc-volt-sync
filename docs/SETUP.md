# Setup checklist

This page lists everything to prepare before installing NRC Volt Sync. Complete the checkboxes in order.

Version 0.3 accepts either the included direct iPhone HealthKit companion or Strava. Choose at least
one source. For the zero-Strava path, complete [HEALTHKIT_COMPANION.md](HEALTHKIT_COMPANION.md).

## 1. Hardware and operating system

- [ ] Apple Watch and iPhone
- [ ] Runs are recorded with Apple's native **Workout** app
- [ ] A Mac that stays signed in when automatic sync should run
- [ ] macOS with Python 3.12
- [ ] `uv` installed: `uv --version`

The watch and phone do not have to remain connected to the Mac. The workout must reach Apple Health,
and the selected Files outbox or Strava must synchronize before the Mac can process it.

## 2. Choose an Apple Health input

Direct, no-Strava source:

- [ ] Full Xcode and free Apple ID are available for personal iPhone signing
- [ ] Included companion is installed and has Apple Health read permission
- [ ] A private Files/iCloud Drive outbox is available on the iPhone and Mac

Follow [HEALTHKIT_COMPANION.md](HEALTHKIT_COMPANION.md). Free Apple Personal Team profiles expire
after 7 days and require weekly reinstall.

Or use Strava:

- [ ] A Strava account
- [ ] Strava iPhone app → **Settings → Manage Apps and Devices → Health** is connected
- [ ] **Automatic Uploads** is enabled
- [ ] Apple Health grants Strava access to **Workouts** and **Workout Routes**

Official guide: [Apple Health and Strava](https://support.strava.com/en-us/articles/15402024-apple-health-and-strava)

Only activities recorded with Apple's native Workout app inside Strava's supported import window are eligible for this Apple Health import path.

## 3. Your own Strava API application (Strava source only)

Every user should create a separate personal API app. Never share another person's client secret.

1. Open [Strava API settings](https://www.strava.com/settings/api).
2. Create an application with any recognizable name, such as `NRC Volt Sync`.
3. Set **Website** to this repository URL or your own site.
4. Set **Authorization Callback Domain** to exactly `localhost`.
5. Keep the displayed **Client ID** and **Client Secret** ready.

The local OAuth callback is `http://localhost:8765/callback`. The secret is stored only under the current macOS user's private Application Support directory.

## 4. Garmin Connect

- [ ] A Garmin Connect account
- [ ] Email, password, and MFA method are available
- [ ] You can sign in at [Garmin Connect](https://connect.garmin.com/)

You do not need a Garmin watch. Garmin is used as NRC's connected activity partner.

Avoid repeated sign-in attempts. Garmin can temporarily return HTTP 429 when it rate-limits an IP address. Wait before retrying instead of repeatedly running the setup command.

## 5. Nike Run Club

- [ ] NRC is signed into the intended Nike account
- [ ] NRC → **Profile → Settings → Partners → Garmin** is connected
- [ ] The Garmin account is the same one configured in this tool

Official guide: [Connect NRC to partner apps and devices](https://www.nike.com/help/a/connect-nrc-partner-apps-devices)

Nike does not provide a public API for this project to verify the partner switch. Confirm it manually before the first upload.

## 6. Install and authenticate

```bash
git clone https://github.com/nirvanasangsara-AI/nrc-volt-sync.git
cd nrc-volt-sync
uv sync
uv run nrc-volt-sync configure-healthkit --outbox "/path/to/private/outbox"
uv run nrc-volt-sync configure-garmin
uv run nrc-volt-sync doctor
```

For the Strava source, run `configure-strava` instead of `configure-healthkit`. Both may be
configured; automatic mode processes HealthKit first and uses Garmin duplicate checks.

Expected `doctor` results:

- `python_3_12`: true
- `at_least_one_source_configured`: true
- either `healthkit_outbox_configured` or `strava_configured`: true
- `garmin_configured`: true
- `private_app_directory`: true
- `nike_garmin_link`: manual verification reminder

## 7. Safe first upload

Validate without uploading:

```bash
uv run nrc-volt-sync sync --after-days 14 --limit 1 --dry-run
```

Upload one activity:

```bash
uv run nrc-volt-sync sync --after-days 14 --limit 1
```

Verify the date, duration, distance, map, and heart rate in Garmin Connect and NRC before backfilling history.

## 8. Historical data and automation

Use narrow date ranges first:

```bash
uv run nrc-volt-sync sync --after 2025-01-01 --before 2025-01-31 --limit 100
```

Install the default 15-minute service only after the first activity is correct:

```bash
uv run nrc-volt-sync install-service
```

Runtime credentials, FIT files, logs, and history are not kept in the Git repository. Read [../PRIVACY.md](../PRIVACY.md) before sharing diagnostics.
