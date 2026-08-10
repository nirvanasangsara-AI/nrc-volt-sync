# Strava 없는 Apple 건강 직접 연결

버전 0.3에는 사용자의 Apple 건강 러닝을 사용자가 고른 폴더로 내보내는 오픈소스 아이폰
보조 앱이 포함됩니다. Mac은 이 전송함을 읽어 검증된 FIT를 만들고 Garmin 중복을 확인한 뒤
기존 Garmin–Nike 파트너 경로로 전달합니다. 운영자 서버와 Strava 계정은 필요 없습니다.

## 미리 준비할 것

- iOS 17 이상 iPhone과 애플 기본 운동 앱을 쓰는 Apple Watch
- 같은 iCloud Drive 계정에 로그인한 Mac, 또는 두 기기에서 쓰는 비공개 Files 저장소
- Mac App Store의 전체 Xcode
- Xcode에 등록할 무료 Apple ID; 개인 사용에는 유료 개발자 가입이 필수는 아님
- NRC **설정 → 파트너 → Garmin**에 연결한 무료 Garmin Connect 계정
- Mac의 Python 3.12와 `uv`

무료 Personal Team 프로비저닝은 Apple 정책상 7일 후 만료되므로 앱을 매주 다시 빌드·설치해야
합니다.
App Store나 TestFlight 배포에는 유료 게시자 계정이 필요하지만 현재 이 프로젝트는 그 계정을
운영하지 않습니다. NRC Volt Sync의 유료 기능이 아니라 Apple의 앱 배포 제한입니다.

Apple의 현재 iOS 기능표에는 HealthKit과 Background Modes가 유료 프로그램뿐 아니라 무료
**Apple Developer** 계정에도 지원되는 것으로 표시됩니다. Apple 공식
[iOS 지원 기능표](https://developer.apple.com/help/account/reference/supported-capabilities-ios/)와
[Personal Team 제한](https://developer.apple.com/help/account/basics/about-your-developer-account)을
확인할 수 있습니다.

## 아이폰 앱 설치

1. 저장소를 Mac에 받은 뒤 전체 Xcode에서 `ios/NRCVoltSyncHealth.xcodeproj`를 엽니다.
2. **NRCVoltSyncHealth** 타깃 → **Signing & Capabilities**를 엽니다.
3. 본인의 Personal Team을 선택합니다. 번들 ID가 이미 사용 중이라는 오류가 나오면 본인만의
   고유한 값으로 바꿉니다.
4. 잠금 해제한 iPhone을 연결하고 실행 대상을 iPhone으로 고른 뒤 **Run**을 누릅니다.
5. Xcode와 iPhone에 Developer Mode 또는 신뢰 안내가 나오면 따릅니다.
6. 앱에서 Apple 건강 읽기를 허용하고 비공개 iCloud Drive/Files 폴더를 고른 뒤 최초 한 번
   **Export all running history**를 누릅니다.

Apple에서 생성된 러닝만 고르고 Garmin에서 건강으로 들어온 기록은 순환 방지를 위해
제외합니다. GPS 경로, 거리, 심박, 러닝 파워, 속도, 보폭, 수직 진폭, 지면 접촉 시간은
HealthKit 원본에 있을 때만 내보냅니다. 이 경로에서 HealthKit이 일반 러닝 케이던스 시계열을
제공하지 않으므로 케이던스는 추정하거나 만들지 않습니다.

## Mac 전송함 연결

다른 서비스로 가져갈 개별 FIT도 원하면 별도의 비공개 폴더를 하나 더 만든 뒤 실행합니다.

```bash
uv sync
uv run nrc-volt-sync configure-healthkit \
  --outbox "/같은/비공개/전송함/경로" \
  --fit-export-dir "/비공개/개별-fit/경로"
uv run nrc-volt-sync configure-garmin
uv run nrc-volt-sync doctor
```

전송함은 iCloud Drive나 선택한 Files 저장소가 Mac에 동기화한 실제 로컬 경로여야 합니다.
전송함과 FIT 폴더를 Git 저장소 안에 두면 안 됩니다.

먼저 실제 업로드 없이 한 건을 검사합니다.

```bash
uv run nrc-volt-sync sync --source healthkit --after-days 14 --limit 1 --dry-run
```

한 건만 올린 뒤 Garmin과 NRC에서 날짜·거리·시간·지도·심박을 확인합니다.

```bash
uv run nrc-volt-sync sync --source healthkit --after-days 14 --limit 1
```

확인이 끝나면 과거 자료를 처리하고 일주일 주기 자동 실행을 설치할 수 있습니다.

```bash
uv run nrc-volt-sync sync --source healthkit --after 2020-01-01 --limit 1000
uv run nrc-volt-sync install-service --interval-minutes 10080 --lookback-days 30
```

기본값인 `--source auto`는 HealthKit 전송함을 먼저 처리하고 Strava도 설정돼 있으면 이어서
검사합니다. 같은 운동이 두 입력원에 있어도 Garmin의 날짜·거리·시간 중복 검사가 다시 막습니다.

## 자동 처리 시차

Mac은 기본 15분마다, 위 예시는 일주일마다 확인합니다. 아이폰 앱은 HealthKit 백그라운드
알림을 요청하지만 실제 실행 시각은 iOS가 정합니다. 운동이 전송함에 아직 없다면 앱을 열어
**Export last 7 days**를 한 번 누르면 되고, 다음 Mac 실행 때 처리됩니다. 아이폰을 Mac에
케이블로 계속 연결할 필요는 없습니다.

## 다른 서비스에도 올리기

선택한 FIT 폴더에는 러닝마다 검증된 표준 FIT 하나가 생깁니다. FIT 가져오기를 공식 지원하는
서비스에 사용자가 직접 넣을 수 있습니다. 이 파일에는 정확한 위치와 건강 정보가 들어갈 수
있으므로 반드시 비공개로 보관하세요. 다른 서비스까지 자동화하려면 각 서비스의 공식 API와
명시적인 사용자 승인을 쓰는 목적지별 어댑터가 필요합니다. 계정정보를 긁어 모으는 공통
업로더는 만들지 않습니다.
