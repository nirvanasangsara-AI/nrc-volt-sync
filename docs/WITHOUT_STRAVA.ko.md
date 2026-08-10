# Strava를 쓰지 않는 사람을 위한 방법

NRC Volt Sync 0.2는 Strava를 애플 기본 운동의 자동 입력원으로 사용합니다. 평소 Strava를
쓰지 않는 사람도 현재 무료 경로가 두 가지 있지만 자동 경로는 한 가지뿐입니다. Strava를
전혀 거치지 않으면서 GPS와 센서까지 자동 보존하려면 아이폰 보조 앱이 필요합니다. Apple이
macOS 앱의 HealthKit 데이터 읽기를 허용하지 않기 때문입니다.

## 어떤 방법을 선택하나요?

| 목적 | 무료 | 자동 | GPS | 심박·케이던스 | 현재 가능 |
| --- | --- | --- | --- | --- | --- |
| 비공개 Strava 계정을 중계소로만 사용 | 예 | 예 | Strava가 주는 경우 보존 | Strava가 주는 항목만 보존 | 예 |
| Strava 계정 없이 야외 과거 기록 복구 | 예 | 아니요 | Apple 내보내기에 시간 포함 경로가 있으면 보존 | GPX에는 대개 불완전, 실내는 경로 없음 | 예, 수동 대안 |
| Strava 없이 GPS·센서 전체 자동 동기화 | 무료로 개발 예정 | 예 | 원본 보존 목표 | 원본 보존 목표 | 아직 없음, [이슈 2](https://github.com/nirvanasangsara-AI/nrc-volt-sync/issues/2) |

## 방법 1: 무료 비공개 Strava 중계 계정

Strava를 평소 사용하지 않는 사람에게 현재 가장 현실적인 자동 방법입니다. 무료 계정을
운동 운반용으로만 사용할 수 있고, 공개 게시·친구 추가·유료 구독은 필요하지 않습니다.

1. 무료 Strava 계정을 만들고 기본 운동 공개 범위를 원하는 비공개 수준으로 설정합니다.
2. Strava 아이폰 앱에서 **설정 → 앱 및 기기 관리 → 건강**을 엽니다.
3. Apple 건강을 연결하고 **운동**과 **운동 경로**를 허용한 뒤 **자동 업로드**를 켭니다.
4. [SETUP.ko.md](SETUP.ko.md)에 따라 그 계정을 NRC Volt Sync와 연결합니다.

Strava 공식 안내에 따르면 애플 기본 운동 앱으로 기록한 최근 30일 활동을 가져올 수 있고,
새 운동은 자동 업로드할 수 있습니다. 다만 Apple 건강 러닝의 케이던스는 항상 제공되지
않으므로 원본이 주지 않은 값은 이 도구도 복원할 수 없습니다.

공식 안내: [Apple Health and Strava](https://support.strava.com/en-us/articles/15402024-apple-health-and-strava)

NRC 안에서 Strava만 직접 연결해도 이 문제가 해결되지는 않습니다. Nike–Strava 연결은
Nike에서 새로 기록한 운동을 Strava로 보내는 방향이고, Strava의 애플워치 기록을 NRC로
가져오는 방향은 지원하지 않습니다.

공식 안내: [Nike and Strava](https://support.strava.com/en-us/articles/15401850-nike-and-strava)

## 방법 2: Strava 계정 없이 Apple 건강 수동 내보내기

야외 과거 러닝을 무료로 옮기는 대안입니다. 자동 서비스처럼 계속 알아서 처리되는 방식은
아닙니다.

1. 아이폰에서 **건강 → 요약 → 프로필 사진 또는 이니셜 → 모든 건강 데이터 내보내기**를
   선택합니다.
2. 파일, AirDrop 등 본인만 접근하는 방법으로 압축파일을 Mac에 옮깁니다.
3. 이 압축파일에는 러닝뿐 아니라 전체 건강 이력이 들어갈 수 있으므로 절대 공개하지 않습니다.
4. 압축을 푼 뒤 운동 경로 폴더에서 해당 야외 러닝의 시간이 포함된 GPX를 찾습니다.
5. 파일을 넣기 전에 NRC의 파트너 설정에서 Garmin을 연결합니다.
6. Garmin Connect 웹의 업로드 아이콘 → **Import Data**에서 해당 GPX를 가져옵니다.
7. 필요하면 Garmin의 활동 유형을 **Running**으로 바꾸고 NRC 도착 여부를 확인합니다.

Apple은 전체 건강·운동 데이터를 XML로 내보내는 기능을 공식 지원합니다. 야외 운동 경로
GPX도 내보내기 압축파일에 포함될 수 있습니다. Garmin은 FIT, 시간이 포함된 GPX, TCX
활동 파일을 공식 지원하며, 시간이 없는 GPX는 활동으로 가져올 수 없습니다.

- Apple: [전체 건강 데이터 내보내기](https://support.apple.com/guide/iphone/share-health-and-fitness-data-iph5ede58c3d/ios)
- Garmin: [활동 파일 수동 업로드](https://support.garmin.com/en-CA/?faq=Ht3ZP52Kju075uKvqTqu99)

### 수동 내보내기의 정보 한계

- 야외 GPS와 시각은 경로 GPX가 있으면 살릴 수 있습니다.
- GPX에는 전체 심박·케이던스·파워·러닝 다이내믹스가 대부분 들어 있지 않습니다.
- 실내 러닝에는 GPS 경로가 없으므로 HealthKit 센서로 만든 FIT 또는 TCX가 필요합니다.
- 별도 XML 센서 기록을 특정 운동과 연결하는 과정은 모호할 수 있습니다. 이 프로젝트는
  없는 값을 추측하거나 만들지 않습니다.
- Garmin에 수동으로 넣은 기록이 NRC로 전달되는지는 Garmin–Nike 파트너 연결이 결정하며,
  Garmin의 파일 가져오기 문서가 NRC 전달까지 보장하지는 않습니다. 한 건부터 시험해야 합니다.

현재 CLI는 Apple 내보내기 압축파일을 직접 읽지 않습니다. 건강 ZIP·XML·GPX·FIT 파일을
Git 저장소 안에 넣으면 안 됩니다.

## 다른 운동 서비스에도 올리려면

현재 NRC Volt Sync가 자동 업로드하는 목적지는 Garmin Connect 한 곳이며, 그 뒤에는 사용자의
Garmin–Nike 파트너 연결이 동작합니다. 현재 Strava 경로에서 검증해 만든 FIT는 비공개 로컬
실행 폴더에 남습니다. 사용자는 개별 FIT 하나를 별도의 비공개 위치로 복사한 뒤, FIT 활동을
공식 지원하는 다른 서비스에 직접 가져올 수 있습니다.

전체 실행 폴더나 FIT를 공개하면 안 됩니다. FIT에는 시각, GPS 경로, 심박 등 건강 정보가
들어갈 수 있습니다. 여러 서비스로 자동 전송하는 공통 버튼은 만들 수 없으며 목적지마다
공식 API, 권한 범위, 중복 규칙, 사용자 승인이 별도로 필요합니다.

## 왜 Mac만으로 완전 자동화할 수 없나요?

Apple 공식 문서상 HealthKit 프레임워크가 macOS에도 존재하지만 macOS 앱은 HealthKit
데이터를 읽거나 쓸 수 없고 `isHealthDataAvailable()`도 거짓을 반환합니다. 전체 경로와
센서를 읽으려면 사용자가 HealthKit 권한을 허용한 아이폰 앱이 필요합니다.

- [HealthKit 사용 가능 기기](https://developer.apple.com/documentation/healthkit/hkhealthstore/ishealthdataavailable())
- [운동 경로 데이터](https://developer.apple.com/documentation/healthkit/hkworkoutroute)
- [HealthKit 권한](https://developer.apple.com/documentation/healthkit/authorizing-access-to-health-data)

[이슈 2](https://github.com/nirvanasangsara-AI/nrc-volt-sync/issues/2)에 공개한 다음 구조가
Strava 없는 자동 경로입니다.

```text
애플워치 기본 운동 → 아이폰 HealthKit → 로컬 보조 앱과 전송함
→ Mac의 NRC Volt Sync → 표준 FIT → Garmin Connect → Nike Run Club
```

표준 FIT 전송함은 사용자가 다른 운동 서비스로 직접 가져갈 때도 사용할 수 있습니다.
다만 다른 서비스까지 자동 업로드하려면 서비스별 공식 API와 사용자 승인이 각각 필요합니다.
서비스를 몰래 긁거나 운영자 서버에 계정·건강 데이터를 모으는 방식은 사용하지 않습니다.
