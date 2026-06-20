# AI Vision Tracker — 작업 변경 이력 (CHANGELOG)

> 이 파일은 모든 코드 변경 작업의 계획과 결과를 기록합니다.
> 에이전트는 작업 전 **계획**을 먼저 작성하고, 완료 후 **결과**를 기록합니다.

---

## 작성 규칙

`
## [날짜] 작업 제목

### 📌 계획
- 변경할 내용 목록
- 변경 이유

### 🔧 변경 파일
- `파일명`: 변경 내용 요약

### ✅ 결과
- 완료된 내용
- 테스트 결과
`

---

## [2026-06-20] 모터 파라미터 UI에서 직접 변경 가능하도록 수정

### 📌 계획
- 기어비(1:5) 기반으로 최대 속도, 가속도 파라미터 상향
- 설정 UI(카메라 추적 탭)에서 steps/px, 최대 속도, 가속도를 직접 입력/적용 가능하게 추가
- 서버 라우트에 steps_per_pix 키 지원 추가
- 모달 오픈 시 현재 서버 값을 자동으로 입력칸에 반영

### 🔧 변경 파일
- esp32_firmware/esp32_firmware.ino
  - MAX_SPEED_LIMIT: 800 → 3000 Hz (1:5 기어비 반영)
  - ACCELERATION_RATE: 2.0 → 8.0 Hz/ms (약 375ms에 최고속 도달)
  - STEPS_PER_PIX: 2.0 → 3.5 (감도 상향)
- state.py
  - esp32_max_speed_hz: 750 → 3000
  - esp32_accel_rate: 5.0 → 8.0
- motor_esp32.py
  - 연결 시 CFG:MSL + CFG:ACC 동시 동기화
- routes.py
  - /set_esp32_mm_config에 steps_per_pix 키 추가 (CFG:SPX 전송)
  - /esp32_mm_settings 응답에 steps_per_px 포함
- templates/index.html
  - 카메라 추적 탭에 steps/px, 최대 속도(Hz), 가속도(Hz/ms) 입력/적용 UI 추가
- static/script.js
  - loadEsp32MmSettings()에서 카메라 추적 탭 입력칸에도 서버 현재값 자동 반영

### ✅ 결과
- 모터 파라미터 설정 → 카메라 추적 탭에서 실시간 변경 가능
- 서버 재시작 없이 즉시 ESP32에 반영됨
- 1:5 기어비 기반 최고속도/가속도 적용 완료

---

## [2026-06-15] 객체 추적 복구 알고리즘 (Competitive Tracking)

### 📌 계획
- 화면 밖으로 나갔다 돌아온 객체를 자동으로 재탐색
- 평소 추적 성능은 그대로 유지하면서 복구 기능만 추가

### 🔧 변경 파일
- detector.py
  - CSRTTracker.__init__(): self.template 추가
  - start_learning(): 학습 시 BGR 템플릿 저장
  - track(): 경쟁적 템플릿 매칭 — 전역 스캔에서 현재보다 0.15 이상 높은 일치 발견 시 점프

### ✅ 결과
- 화면 밖으로 나갔다가 다른 방향으로 돌아와도 자동 복구
- 정상 추적 중에는 불필요한 점프 없음

---

## [2026-06-15] 조이스틱 포인터 튀김 현상 수정

### 📌 계획
- fetch('/pos') 비동기 응답 지연으로 포인터가 원래 위치로 끌려가는 문제 해결

### 🔧 변경 파일
- static/script.js
  - syncPos() 함수: fetch 응답 도착 시점에 조이스틱 사용 여부 재확인하는 이중 체크 추가

### ✅ 결과
- 조이스틱 조작 중 포인터 튀김(Rubber-banding) 현상 해결

---

## [2026-06-20] 전체 코드 리뷰 및 README.md 갱신

### 📌 계획
- 프로젝트 전체 코드 (Python Backend, ESP32 Firmware, Frontend) 리뷰 진행
- 코드 리뷰 결과를 바탕으로 GitHub에 올릴 이쁘고 전문적인 README.md 재작성
- 프로젝트의 전반적인 기능, 기술 스택, 동작 원리 등을 명확히 설명하는 방향으로 작성

### 🔧 변경 파일
- README.md: 전체 문서 갱신

### ✅ 결과
- (작업 후 기록 예정)
- 전체 코드 리뷰 완료 (CSRT Tracking, Competitive Tracking, 1:5 기어비 등 반영 확인)
- README.md 작성 및 내용 최신화 완료
- 이쁘고 직관적인 디자인(배지, 다이어그램, 테이블 등) 적용 완료
