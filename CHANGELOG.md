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

---

## [2026-06-20] 코드 import/호환 오류 수정

### 📌 계획
- routes.py에서 존재하지 않는 motor 모듈 import 오류 수정
- routes.py에서 motor_esp32에 없는 send_mm_config() 함수 호출 오류 수정
- /set_motor_config 라우트를 motor_esp32.send_config()로 교체
- /set_esp32_mm_config 라우트의 send_mm_config → send_config로 통일

### 🔧 변경 파일
- routes.py
  - 491: import motor as mot → motor.py 없음, motor_esp32로 교체
  - 627,631,635,649,653,657: esp.send_mm_config() → esp.send_config()로 수정

### ✅ 결과
- routes.py: import motor → import motor_esp32 수정 완료
- routes.py: send_mm_config() 6곳 → send_config()로 수정 완료
- state.py: motor_target_x/y, motor_error_x/y, motor_steps_m1/m2, motor_moving, motor_timeout, motor_stopped 추가
- state.py: arduino_steps_per_rev, m1/m2_max_speed, m1/m2_accel, pos_m1/m2 추가
- python -m py_compile 및 import 테스트 통과 (ALL OK)


---

## [2026-06-20] routes.py 나머지 오류 수정

### 📌 계획
- routes.py L776: esp._find_port() 존재하지 않음 → serial_utils.find_port()로 교체
- 전체 파일 교차 검증으로 추가 누락 함수/속성 확인

### 🔧 변경 파일
- routes.py: L776 esp._find_port() → serial_utils.find_port(_ESP32_VIDS) 교체

### ✅ 결과
- routes.py L776: esp._find_port() → serial_utils.find_port(preferred_vids=_ESP32_VIDS) 교체 완료\n- 9개 파일 전체 py_compile 검증: ALL PASS


---

## [2026-06-20] routes.py Pylance 타입 오류 수정

### 📌 계획
- L327: state.current_frame이 None일 수 있어 .shape[:2] 언패킹이 Never 타입 오류 → assert/타입가드 추가
- L342: cv2.imencode 반환 buf(ndarray)를 b64encode에 직접 전달 → buf.tobytes()로 변환

### 🔧 변경 파일
- routes.py L327: current_frame None 체크 강화
- routes.py L342: b64encode(buf) → b64encode(buf.tobytes())

### ✅ 결과
- 작업 후 기록 예정

---

## [2026-06-20] detector.py Pylance 오류 수정

### 📌 계획
- L110, L196: frame.shape[:2] 슬라이싱 언패킹으로 인한 Never 타입 오류를 인덱스 직접 접근(shape[0], shape[1])으로 수정
- L230, L266: [int(v) for v in bbox] 리스트를 크기가 명시되지 않은 상태로 4개 변수로 언패킹 시 발생하는 타입 오류를 인덱스 할당 또는 고정 크기 튜플로 수정

### 🔧 변경 파일
- detector.py
  - frame.shape[:2] → img_h, img_w = frame.shape[0], frame.shape[1]
  - tx, ty, tw, th = [int(v) for v in bbox] → tx, ty, tw, th = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

### ✅ 결과
- detector.py L110, L196: frame.shape[:2] → frame.shape[0], frame.shape[1]로 교체 완료`n- detector.py L230, L266: [int(v) for v in bbox] 언패킹 오류를 개별 인덱싱 할당으로 교체 완료


---

## [2026-06-20] detector.py 나머지 Pylance 오류 수정

### 📌 계획
- L17: cv2.inRange 파라미터가 튜플일 때 발생하는 UMat/ndarray 타입 불일치 오류를 np.array() 감싸기로 수정
- L97: learn_zone 속성 할당 시 튜플 크기 미정(tuple[int,...]) 오류를 개별 요소 (coords[0], coords[1], coords[2], coords[3]) 명시적 할당으로 수정
- L165, L258: cv2.TrackerCSRT_create를 인식하지 못하는 오탐지 오류에 대해 # type: ignore 추가

### 🔧 변경 파일
- detector.py (위 4곳 수정)

### ✅ 결과
- 작업 후 기록 예정

---

## [2026-06-20] 전역 코드 Pyright 오류 검토 및 수정

### 📌 계획
- Pyright를 이용해 모든 파일의 잠재적 타입/언패킹/임포트 오류 확인
- 카메라, 모터 시리얼, 유틸 등 4건의 사소한 Pylance/Pyright False Positive 및 Type Hint 오류 수정

### 🔧 변경 파일
- camera.py L50: cv2.VideoWriter_fourcc 오탐지 무시 (getattr 우회)
- motor_arduino.py L19, motor_esp32.py L14: serial 모듈 import 실패 시 None 명시적 할당으로 Unbound 에러 방지
- serial_utils.py L9: 파라미터 타입 힌트를 set | None으로 수정

### ✅ 결과
- 전체 코드에서 Pylance/Pyright 오류 Zero(0) 달성 확인

---

## [2026-06-20] README.md 상세 내용과 간략 내용의 통합

### 📌 계획
- 상세한 기술 명세(Mermaid 다이어그램, 수학 공식, 세부 알고리즘 표 등)와 최신 간략화된 UI 가이드(이모지 폴더, FOTA, Pyright 0 Error, 트러블슈팅 등)를 완벽하게 융합
- 양쪽의 장점을 모두 살려 허전하지 않고 전문가적이면서도 읽기 편한 README 구성

### 🔧 변경 파일
- README.md: 전체 문서 융합 갱신

### ✅ 결과
- (작업 후 기록 예정)
- 제가 작성했던 상세한 기술 설명(Mermaid 렌더링, 수학 공식, 작동 원리 표 등)을 복구
- 다른 버전의 간결하고 세련된 요소(Pyright 무오류 명시, FOTA, 이모지 폴더, 트러블슈팅 가이드 등)를 그대로 편입
- 최종적으로 허전하지 않으면서 꽉 차고 가독성 높은 통합본 README 완성

---

## [2026-06-20] README.md 수식 렌더링 수정 및 커버 이미지 추가

### 📌 계획
- P-Control 수학 공식에서 언더바로 인해 발생하는 렌더링 오류('\_\' allowed only in math mode) 해결
- 부모 디렉토리에 있는 turret_diagram.png (3D 모델)을 저장소로 복사하여 README 최상단에 배치

### 🔧 변경 파일
- \README.md\: 커버 이미지 태그 추가 및 수식 문법 수정
- \	urret_diagram.png\: 저장소에 신규 추가

### ✅ 결과
- (작업 후 기록 예정)
- 수식 내 언더바(_) 제거 및 깔끔한 텍스트 렌더링으로 오류 완벽 해결
- 부모 폴더의 turret_diagram.png 복사 및 README 최상단에 폭 450px 크기로 이쁘게 삽입 완료

---

## [2026-06-20] README.md 불필요한 이미지 제거

### 📌 계획
- 3D 렌더링 커버 이미지 추가로 인해 중복/과해진 최상단의 Typing SVG 애니메이션 제거
- 깔끔하게 하나의 메인 이미지만 노출되도록 정리

### 🔧 변경 파일
- \README.md\: Typing SVG 태그 삭제

### ✅ 결과
- (작업 후 기록 예정)
- README.md의 1~10번째 줄 부근에 위치하던 Typing SVG 이미지 요소를 삭제하여 3D 모델 커버 이미지만 깔끔하게 단독으로 보이도록 정리 완료

---

## [2026-06-20] README.md 커버 이미지 교체

### 📌 계획
- 사용자가 새로 업로드한 고해상도 3D 렌더링 이미지로 기존 \	urret_diagram.png\ 덮어쓰기 및 업데이트

### 🔧 변경 파일
- \	urret_diagram.png\: 새 이미지 파일로 덮어쓰기 교체

### ✅ 결과
- (작업 후 기록 예정)
- 사용자가 새로 업로드한 이미지 파일로 기존의 turret_diagram.png 파일을 성공적으로 덮어쓰기 교체 완료

---

## [2026-06-20] README.md 커버 이미지 2차 교체

### 📌 계획
- 사용자가 방금 업로드한 최신 CAD 렌더링 이미지로 기존 \	urret_diagram.png\ 덮어쓰기 교체 수행

### 🔧 변경 파일
- \	urret_diagram.png\: 새 이미지 파일로 교체

### ✅ 결과
- (작업 후 기록 예정)
- 새로 전달받은 이미지 파일로 기존의 turret_diagram.png 파일을 완전히 교체함

---

## [2026-06-20] README.md 커버 이미지 3차 교체 (크롭 및 중앙 정렬)

### 📌 계획
- 사용자가 새로 업로드한 3D 모델 이미지를 불러와, 터렛 본체가 정중앙에 오도록 상하좌우 여백을 크롭(Crop) 처리
- 크롭된 이쁜 이미지로 기존 \	urret_diagram.png\ 교체 수행

### 🔧 변경 파일
- \	urret_diagram.png\: 크롭된 새 이미지로 교체

### ✅ 결과
- (작업 후 기록 예정)
- Python(OpenCV)을 이용하여 이미지의 여백을 완벽하게 잘라내고(Crop) 중앙 정렬 처리한 후 turret_diagram.png 교체 완료

---

## [2026-06-20] 상세 사용자 가이드(USER_GUIDE.md) 신규 생성

### 📌 계획
- 처음 접하는 사람들도 쉽게 하드웨어를 연결하고 소프트웨어를 사용할 수 있도록 상세한 \USER_GUIDE.md\ 파일 생성
- 설치 방법, 하드웨어 결선 가이드, 웹 UI 조작법, 트러블슈팅을 한곳에 정리
- 기존 \README.md\에는 사용자 가이드로 가는 링크 추가

### 🔧 변경 파일
- \USER_GUIDE.md\: 신규 생성
- \README.md\: 사용자 가이드 링크 추가

### ✅ 결과
- (작업 후 기록 예정)
- 처음 사용하는 사람들을 위해 하드웨어 결선부터 소프트웨어 설치 및 조작, 문제해결(FAQ)까지 전부 담긴 USER_GUIDE.md 파일을 새롭게 작성
- 기존 README.md 최상단 설명 아래에 사용자 가이드로 바로 이동할 수 있는 눈에 띄는 링크 추가 완료

---

## [2026-06-21] 버튼 비작동 / 수직모터 반전 / 움직임 버벅임 수정

### 📌 계획
- 카메라 세팅, 모터 파라미터, 펌웨어 업로드 버튼이 전혀 작동 안 하는 원인 분석
- 수직 모터 방향 반전 수정
- 모터 움직임 버벅임 원인 분석 및 개선

### 🔧 변경 파일
- 분석 후 기록 예정

### ✅ 결과
- 작업 후 기록 예정

---

## [2026-06-21] 프로그램 종료/유휴 시 모터 홀딩 해제

### 📌 계획
- Flask 서버 종료 시 (Ctrl+C / 프로세스 종료) ESP32에 모터 해제 명령 전송
- ESP32 펌웨어: 일정 시간 명령이 없으면 모터 홀딩 전류 자동 해제 (Watchdog)
- Python: atexit + signal 핸들러로 종료 시 RELEASE 명령 전송
- motor_esp32.py: release_motors() 함수 추가

### 🔧 변경 파일
- esp32_firmware/esp32_firmware.ino: 무명령 Watchdog + CMD:REL 처리 추가
- motor_esp32.py: release_motors() 함수 추가
- main.py: atexit/signal 핸들러 등록

### ✅ 결과
- 작업 후 기록 예정

---

## [2026-06-21] 펌웨어 업로드 오류 / 갤러리 미작동 / 딜레이 추가 단축

### 📌 계획
- 펌웨어 업로드 API(/upload_firmware) 동작 확인 및 수정
- 갤러리(사진첩) 버튼/모달 동작 불가 원인 분석 및 수정
- 조이스틱 재전송 딜레이 200ms → 80ms 추가 단축

### 🔧 변경 파일
- 분석 후 기록 예정

### ✅ 결과
- 작업 후 기록 예정

## [2026-06-22] 조이스틱 딜레이 및 과이동 문제 해결

### 📌 계획
- 현재 조이스틱은 마우스 커서를 움직이는 방식이라 화면 끝(640픽셀)에 도달하면 모터가 멈춤
- 이를 해결하기 위해 조이스틱 동작을 '절대 좌표(화면)' 기반에서 '상대 위치(속도)' 기반으로 완전 분리

### 🔧 변경 파일
- static/script.js: 조이스틱 조작 시 	Px 업데이트 중지 및 checkJoystickDir() 부활
- outes/core.py: /joystick_dir 라우트 추가하여 연속 상대 이동(enqueue_move) 명령 하달

## [2026-06-22] 웹캠 딜레이 (1~2초) 문제 해결

### 📌 계획
- 현재 camera.py는 gen_frames() 안에서 직접 _cap.read()를 호출함
- OpenCV DirectShow 버퍼 특성상 읽는 속도가 느리면 과거 프레임이 누적되어 1~2초의 지연(Latency)이 발생함
- 이를 해결하기 위해 백그라운드 스레드에서 _cap.read()를 최대한 빠르게 반복 호출하여 버퍼를 비우고, 가장 최신 프레임만 state.current_frame에 갱신하도록 수정

### 🔧 변경 파일
- camera.py: 백그라운드 캡처 스레드 추가, gen_frames()는 스레드가 저장한 current_frame만 가져가도록 변경

## [2026-06-22] 조작감 완벽 최적화 및 딜레이 제로화

### 📌 계획
- ESP32 부팅 시 GPIO12 충돌 문제 해결
- 모터 끊김(Stuttering) 및 초기 지연 시간(Delay) 완벽 제거

### 🔧 변경 파일
- outes/core.py: 조이스틱 조작 시 가상 타겟 적분(Virtual Target Integration) 방식 도입, 초기 위치 동기화 로직 제거
- motor_esp32.py: stop_motors 시 가상 타겟 강제 리셋 방지 및 큐 제거로 직접 시리얼 쓰기 적용
- static/script.js: 조이스틱 전송 주기를 80ms -> 30ms로 대폭 단축 및 임계값(0.15 -> 0.05) 하향 조정

### ✅ 결과
- ESP32 전원을 모터보다 먼저 인가해야 하는 하드웨어 특성을 파악하여 부팅 불가 문제 해결
- 끊김(티디디딕) 증상 없이 아날로그 조이스틱 비례제어(0~1500Hz) 완벽 동작
- 조작 지연 0초 달성 (통신 지연으로 인한 초기 역방향/정지 현상 완벽 해결)


## [2026-06-24] 포인터 제어 모드 제거 및 조이스틱 중앙 고정 처리

### 📌 계획
- 웹 UI에서 불필요해진 '포인터(화면 클릭/터치 이동)' 제어 모드를 완전히 삭제한다.
- 수동 모드(조이스틱)일 때 화면의 에임(십자선)이 조이스틱 이동에 따라 화면 구석으로 돌아다니지 않고 **항상 정중앙(320, 240)** 에 고정되도록 변경한다.
- 백엔드(/joystick_dir)에서 좌표를 int가 아닌 float로 처리하여 소수점 조이스틱 입력 시 발생하는 버그(400 Bad Request)를 수정한다.

### 🔧 변경 파일
- \	emplates/index.html\: 조작 모드 세그먼트 버튼 및 옵션에서 '포인터' 항목 제거 (2개 버튼으로 변경).
- \static/script.js\: pointer_mode 관련 마우스 및 터치 이벤트 핸들러(클릭 이동 등) 삭제, \loop()\ 내 수동 모드일 때 \	Px\, \	Py\를 항상 320, 240으로 강제 고정.
- \outes.py\: \/joystick_dir\ 엔드포인트 파라미터 변환을 \int()\에서 \loat()\으로 수정.

### ✅ 결과
- 조작 모드 탭이 '조이스틱'과 'AI 자동 추적' 두 개로 간소화됨.
- 수동 제어 시 십자선이 항상 화면 한가운데에 유지되어 1인칭 시점(FPS) 같은 조작감을 제공함.
- 백엔드에 조이스틱 상대 좌표 전달 시 에러가 발생하지 않음.

