# Troubleshooting / 문제 해결

## Run is in Apple Health but not Strava

Confirm Strava → Settings → Manage Apps and Devices → Health → **Automatic Uploads**. Apple Health must allow Workouts and Workout Routes. Reconnect the watch or iPhone to the internet and open Strava once.

Apple 건강에는 있지만 Strava에 없으면 Strava의 건강 연결과 자동 업로드, 운동·경로 권한을 확인하세요.

## Garmin login returns HTTP 429

Stop retrying. Garmin has temporarily rate-limited the IP. Wait and try once later. Repeated attempts can extend the rate limit.

Garmin 로그인에서 429가 나오면 반복 실행하지 말고 기다렸다가 한 번만 다시 시도하세요.

## Garmin has the run but NRC does not

Verify NRC → Settings → Partners → Garmin. Partner imports can be delayed; refresh the NRC Activity tab. If it remains missing, disconnecting and reconnecting the partner is a last resort because it can change future delivery behavior.

Garmin에는 있지만 NRC에 없으면 파트너의 Garmin 연결과 NRC 활동 화면 새로고침을 확인하세요.

## Map, heart rate, or cadence is missing

Run `inspect-activity` only on your own computer. If Strava exposes no corresponding stream, NRC Volt Sync leaves it blank. It does not estimate private health or route data.

```bash
uv run nrc-volt-sync inspect-activity YOUR_STRAVA_ACTIVITY_ID
```

이 출력에는 활동 ID와 시간이 포함될 수 있으므로 그대로 공개 이슈에 붙이지 마세요.

## Check service and logs

```bash
uv run nrc-volt-sync doctor
uv run nrc-volt-sync status
tail -n 50 "$HOME/Library/Application Support/NRCVoltSync/logs/sync.log"
```

`status` redacts account values. Logs can still contain activity metadata; remove identifiers before sharing.

## Duplicate concern

Stop the service, inspect Garmin and NRC, and do not delete the local state database while investigating.

```bash
uv run nrc-volt-sync uninstall-service
```

Removing the service keeps tokens and sync history, so it can be reinstalled later without losing duplicate protection.
