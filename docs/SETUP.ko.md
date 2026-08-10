# 설치 준비 체크리스트

NRC Volt Sync를 설치하기 전에 필요한 자료와 설정입니다. 위에서부터 차례로 확인하세요.

버전 0.3은 포함된 아이폰 HealthKit 직접 연결 또는 Strava 중 하나를 입력원으로 씁니다.
최소 하나를 선택하세요. Strava 없는 경로는
[HEALTHKIT_COMPANION.ko.md](HEALTHKIT_COMPANION.ko.md)를 먼저 완료합니다.

## 1. 기기와 운영체제

- [ ] Apple Watch와 iPhone
- [ ] 애플 기본 **운동** 앱으로 러닝 기록
- [ ] 자동 동기화 시간에 로그인 상태로 켜져 있을 Mac
- [ ] Python 3.12가 설치된 macOS
- [ ] `uv` 설치 확인: `uv --version`

애플워치나 아이폰을 Mac에 계속 연결할 필요는 없습니다. 운동이 Apple 건강에 도착하고 선택한
Files 전송함 또는 Strava가 동기화돼야 Mac이 처리할 수 있습니다.

## 2. Apple 건강 입력원 선택

Strava 없는 직접 입력:

- [ ] 개인 iPhone 서명에 쓸 전체 Xcode와 무료 Apple ID
- [ ] 포함된 보조 앱 설치와 Apple 건강 읽기 허용
- [ ] iPhone과 Mac이 함께 보는 비공개 Files/iCloud Drive 전송함

[HEALTHKIT_COMPANION.ko.md](HEALTHKIT_COMPANION.ko.md)를 따릅니다. Apple 무료 Personal
Team 프로필은 7일 후 만료돼 매주 앱을 다시 설치해야 합니다.

또는 Strava 입력:

- [ ] Strava 계정
- [ ] Strava iPhone 앱 → **설정 → 앱 및 기기 관리 → 건강** 연결
- [ ] **자동 업로드** 켜기
- [ ] Apple 건강에서 Strava의 **운동** 및 **운동 경로** 읽기 허용

공식 안내: [Apple Health and Strava](https://support.strava.com/en-us/articles/15402024-apple-health-and-strava)

## 3. 본인 소유의 Strava API 앱(Strava 입력만)

모든 사용자는 각자의 API 앱을 만들어야 합니다. 다른 사람의 Client Secret을 공유하거나 사용하면 안 됩니다.

1. [Strava API 설정](https://www.strava.com/settings/api)을 엽니다.
2. `NRC Volt Sync`처럼 알아보기 쉬운 이름으로 앱을 만듭니다.
3. **Website**에는 이 GitHub 저장소나 본인 사이트 주소를 넣습니다.
4. **Authorization Callback Domain**에는 정확히 `localhost`를 입력합니다.
5. 화면의 **Client ID**와 **Client Secret**을 준비합니다.

로컬 OAuth 콜백은 `http://localhost:8765/callback`입니다. Secret은 현재 macOS 사용자의 비공개 Application Support 폴더에만 저장됩니다.

## 4. Garmin Connect

- [ ] Garmin Connect 계정
- [ ] 이메일, 비밀번호, MFA 수단 준비
- [ ] [Garmin Connect](https://connect.garmin.com/) 로그인 확인

Garmin 워치는 없어도 됩니다. Garmin은 NRC가 지원하는 활동 파트너 경로로 사용합니다.

로그인을 짧은 시간에 반복하면 Garmin이 HTTP 429로 IP를 제한할 수 있습니다. 그때는 명령을 반복하지 말고 기다린 뒤 다시 시도하세요.

## 5. Nike Run Club

- [ ] 사용할 Nike 계정으로 NRC 로그인
- [ ] NRC → **프로필 → 설정 → 파트너 → Garmin** 연결
- [ ] NRC에 연결한 Garmin 계정과 이 도구에 넣을 계정이 같음

공식 안내: [NRC 파트너 앱과 기기 연결](https://www.nike.com/help/a/connect-nrc-partner-apps-devices)

Nike는 이 도구가 파트너 스위치를 확인할 공개 API를 제공하지 않습니다. 첫 업로드 전에 NRC에서 직접 확인하세요.

## 6. 설치와 인증

```bash
git clone https://github.com/nirvanasangsara-AI/nrc-volt-sync.git
cd nrc-volt-sync
uv sync
uv run nrc-volt-sync configure-healthkit --outbox "/비공개/전송함/경로"
uv run nrc-volt-sync configure-garmin
uv run nrc-volt-sync doctor
```

Strava 입력을 쓸 때는 `configure-healthkit` 대신 `configure-strava`를 실행합니다. 두 입력을
모두 설정해도 자동 모드가 HealthKit을 먼저 처리하고 Garmin 중복 검사를 적용합니다.

`doctor`에서 Python, `at_least_one_source_configured`, Garmin, 비공개 폴더가 모두
`true`여야 합니다. HealthKit 또는 Strava 중 선택한 입력도 `true`로 표시됩니다.

## 7. 안전한 첫 업로드

실제 업로드 없이 한 건을 검증합니다.

```bash
uv run nrc-volt-sync sync --after-days 14 --limit 1 --dry-run
```

한 건만 실제로 올립니다.

```bash
uv run nrc-volt-sync sync --after-days 14 --limit 1
```

Garmin Connect와 NRC에서 날짜·시간·거리·지도·심박을 확인한 뒤 과거 기록을 복구하세요.

## 8. 과거 자료와 자동화

처음에는 한 달처럼 좁은 범위로 실행합니다.

```bash
uv run nrc-volt-sync sync --after 2025-01-01 --before 2025-01-31 --limit 100
```

첫 기록이 정확하면 15분 자동 서비스를 설치합니다.

```bash
uv run nrc-volt-sync install-service
```

인증값, FIT, 로그, 동기화 이력은 Git 저장소에 들어가지 않습니다. 오류 자료를 공유하기 전에 [../PRIVACY.md](../PRIVACY.md)를 읽으세요.
