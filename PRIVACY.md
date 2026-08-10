# Privacy

NRC Volt Sync is local-first. It has no developer-operated server, analytics, telemetry, advertising, or crash-reporting endpoint.

## Data flows

The program communicates directly from the user's Mac with:

- Strava OAuth and API to read the user's authorized activities and streams.
- Garmin Connect to authenticate, check duplicates, and upload FIT activities.
- Nike Run Club indirectly through the user's existing Garmin–Nike partner connection.

No project maintainer receives these requests or credentials.

## Local sensitive data

Runtime data is stored under `~/Library/Application Support/NRCVoltSync/` with owner-only permissions. It can include:

- Garmin email and session tokens
- Strava client ID, client secret, OAuth access token, and refresh token
- Strava and Garmin activity identifiers
- Activity dates, device names, distances, and synchronization results
- FIT files containing GPS routes, timestamps, heart rate, altitude, power, or cadence
- Rotating logs and a SQLite duplicate-prevention database

The Garmin password is passed to the authentication client during setup and is not written to the NRC Volt Sync configuration file.

## Repository safeguards

- Runtime files are outside the repository.
- Common token, configuration, database, log, and FIT filenames are ignored by Git.
- Config files and tokens are created with mode `0600`; data directories use `0700`.
- `status` replaces every persisted account value with `<stored>` and abbreviates the home directory as `~`.
- HTTP client request logs are suppressed at normal log level.

## Before sharing diagnostics

Never publish:

- `~/Library/Application Support/NRCVoltSync/`
- `.fit` files or route screenshots
- Strava or Garmin activity URLs and IDs
- email addresses, athlete IDs, client IDs, client secrets, OAuth tokens, cookies, or session files
- raw logs without reviewing every line

Use synthetic data in bug reports. The issue template intentionally asks users to confirm that all identifiers were removed.

## Removing local data

`nrc-volt-sync uninstall-service` removes only the automatic scheduler. It intentionally keeps credentials and history to preserve duplicate protection.

To remove all local account and health data, first stop the service, then manually archive or delete `~/Library/Application Support/NRCVoltSync/`. That action is irreversible unless the folder is backed up.

## 한국어 요약

이 프로그램은 운영자가 관리하는 서버나 분석 기능이 없는 로컬 도구입니다. 계정 토큰, FIT, GPS, 심박, 활동 ID, 로그는 Git 저장소가 아니라 사용자의 `~/Library/Application Support/NRCVoltSync/`에만 저장됩니다. 해당 폴더와 실제 FIT·로그·화면 캡처는 공개하지 마세요.
