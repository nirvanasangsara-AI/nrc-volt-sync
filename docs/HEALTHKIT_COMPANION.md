# Direct Apple Health companion (no Strava)

Version 0.3 includes an open-source iPhone companion that exports the runner's own Apple Health
workouts to a folder the runner chooses. The Mac reads that outbox, creates a validated FIT file,
checks Garmin for a duplicate, and uses the existing Garmin–Nike partner route. No maintainer server
or Strava account is involved.

## What to prepare

- iPhone with iOS 17 or later and an Apple Watch using Apple's Workout app
- Mac signed into the same iCloud Drive account, or another private Files provider available on both
- Full Xcode from the Mac App Store
- A free Apple ID added to Xcode; paid Apple Developer membership is not required for personal use
- Free Garmin Connect account connected in NRC under **Settings → Partners → Garmin**
- Python 3.12 and `uv` on the Mac

Apple's free Personal Team provisioning profile expires after 7 days, so the app must be
rebuilt/reinstalled weekly.
App Store or TestFlight distribution would require a paid publisher account, which this project does
not currently operate. This limitation comes from Apple's app distribution rules, not from a paid
feature in NRC Volt Sync.

Apple's current iOS capability table lists HealthKit and Background Modes for the free **Apple
Developer** account tier as well as paid programs. See Apple's
[supported iOS capabilities](https://developer.apple.com/help/account/reference/supported-capabilities-ios/)
and [Personal Team limits](https://developer.apple.com/help/account/basics/about-your-developer-account).

## Build and install the iPhone app

1. Clone this repository on the Mac and open `ios/NRCVoltSyncHealth.xcodeproj` in full Xcode.
2. Select the **NRCVoltSyncHealth** target → **Signing & Capabilities**.
3. Choose your Personal Team. If Xcode reports that the bundle identifier is already used, replace
   it with a unique identifier owned by you.
4. Connect the unlocked iPhone, select it as the run destination, and press **Run**.
5. Follow Xcode/iPhone prompts for Developer Mode and trust if they appear.
6. In the app, allow Apple Health read access, choose a private iCloud Drive/Files folder, and tap
   **Export all running history** once.

Only Apple-origin running workouts are selected. Garmin-origin Health workouts are excluded to
avoid loops. The app exports route, distance, heart rate, running power, speed, stride length,
vertical oscillation, and ground-contact time only when HealthKit contains those fields. HealthKit
does not expose a general running-cadence series here, so cadence is deliberately left absent.

## Connect the outbox on the Mac

Create an optional second private folder if you also want portable FIT copies. Then run:

```bash
uv sync
uv run nrc-volt-sync configure-healthkit \
  --outbox "/path/to/the/same/private/outbox" \
  --fit-export-dir "/path/to/private/portable-fit"
uv run nrc-volt-sync configure-garmin
uv run nrc-volt-sync doctor
```

The outbox path must be the local Mac path synchronized by iCloud Drive or the chosen Files
provider. Do not put either folder inside the Git repository.

Validate one workout without uploading:

```bash
uv run nrc-volt-sync sync --source healthkit --after-days 14 --limit 1 --dry-run
```

Then upload one and verify its date, distance, duration, map, and heart rate in Garmin and NRC:

```bash
uv run nrc-volt-sync sync --source healthkit --after-days 14 --limit 1
```

After verification, backfill history and install the scheduler:

```bash
uv run nrc-volt-sync sync --source healthkit --after 2020-01-01 --limit 1000
uv run nrc-volt-sync install-service --interval-minutes 10080 --lookback-days 30
```

The default `--source auto` processes a configured HealthKit outbox first, then Strava if Strava is
also configured. Garmin duplicate checks protect against the same run arriving from both sources.

## Timing and background limits

The Mac checks every 15 minutes by default, or weekly in the example above. HealthKit background
delivery is requested, but iOS decides when an app gets background time. If a workout has not
appeared in the outbox, open the companion and tap **Export last 7 days**; the Mac scheduler will
pick it up on its next run. The watch and phone do not need to be physically connected to the Mac.

## Other services

The optional FIT export directory contains one validated, portable FIT per run. It can be imported
manually into services that officially accept FIT files. FIT files can contain precise location and
health data, so keep that directory private. Automatic uploads to additional providers require a
separate adapter using that provider's official API and explicit user authorization; a generic
credential-scraping uploader is intentionally out of scope.
