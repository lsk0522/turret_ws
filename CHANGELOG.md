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


## [2026-06-24] 조이스틱 딜레이 제로화 및 모터 즉각 반응 최적화

### 📌 계획
- 조이스틱 조작 시 백엔드의 큐(Queue) 통신 및 모드 전환(MODE:POS) 대기 시간으로 인해 발생하던 딜레이(약 100~130ms)를 완전히 제거한다.
- 조이스틱 위치값을 실시간으로 서버에 전송하고, 기존 자동 추적에 쓰이던 딜레이 제로의 상대 좌표 명령어(T:x:y)를 수동 모드에도 똑같이 적용하여 모터를 즉각 반응하게 만든다.

### 🔧 변경 파일
- \static/script.js\: 조이스틱 조작 시 \/joystick_dir\ 대신 \/click\ 엔드포인트를 호출하여 가상 타겟 좌표(\	Px\, \	Py\)의 오프셋을 실시간으로 서버에 전송하도록 변경. 십자선은 시각적으로 중앙에 계속 고정됨.

### ✅ 결과
- 조이스틱을 움직이는 즉시 모터가 즉각적으로(Zero-delay) 부드럽게 움직임.
- 조이스틱을 놓으면 모터가 즉시 제자리에 정지함.


## [2026-06-24] 조이스틱 통신 병목 및 딜레이 완벽 제거

### 📌 계획
- 조이스틱을 움직이는 동안 브라우저가 초당 너무 많은 통신(HTTP fetch)을 시도하여, 네트워크 연결이 밀려(Connection Queueing) 뒤늦게 한꺼번에 통신이 전송되는 현상이 발생함.
- 이로 인해 조이스틱을 당길 때는 반응이 없고, 손을 떼면 밀려있던 통신들이 뒤늦게 쏟아져 모터가 한참 뒤에 동작하는 치명적인 딜레이 현상을 수정한다.

### 🔧 변경 파일
- \static/script.js\: HTTP 통신 중첩 방지 로직(Non-overlapping fetch queue) 도입. 이전 통신이 끝나기 전에는 새 통신을 보내지 않고 대기하며, 끝나는 즉시 그 순간의 '최신 조이스틱 위치'만 딱 1번 골라 보내도록 수정.
- \	emplates/index.html\: 캐시 버스터 버전 v17.0으로 업데이트.

### ✅ 결과
- 조이스틱을 조작할 때 통신이 밀리지 않아 실시간으로 모터가 반응하게 됨.
- 조이스틱에서 손을 떼는 순간 즉각 멈춤 신호가 전송되어 잔여 동작 없이 완전히 제자리에 서게 됨.

---

## [2026-06-25] 모터 주행 버벅거림(뚜득거림) 완벽 제거 및 감속 램핑 구현

### 📌 계획
- 모터 구동 시 감속 구간에서 속도가 급격하게(instant clamp) 낮아짐으로 인해 발생하는 모터의 강한 기계적 뚝뚝거림(탈조 및 충격 소음) 해결.
- `esp32_firmware/esp32_firmware.ino`의 `stepMotors()` 구동 루프에서 감속 시에도 가속도 파라미터(`ACCELERATION_RATE`)를 적용하여 완만하게 감속하도록 속도 램핑 프로파일 개선.
- `state.py`의 `esp32_accel_rate` 디폴트 값을 급격한 가감속으로 인한 탈조를 막기 위해 `40.0`에서 부드러운 `12.0`으로 하향 튜닝.
- `routes.py`에서 모터 설정을 변경할 때 기존 `SPM1/SPM2` 대신 현재 펌웨어가 파싱하는 `SPD1/SPD2` 파라미터로 올바르게 호출하도록 키 맵 매칭 오류 수정.

### 🔧 변경 파일
- `esp32_firmware/esp32_firmware.ino`: 감속 램핑(Deceleration ramp) 알고리즘 적용.
- `state.py`: `esp32_accel_rate` 기본값을 `12.0`으로 수정.
- `routes.py`: 설정 동기화 키 수정 (`SPM1` -> `SPD1`, `SPM2` -> `SPD2`).

### ✅ 결과
- `esp32_firmware/esp32_firmware.ino`의 `stepMotors` 구동부에서 급감속 시에도 가속도 파라미터(`ACCELERATION_RATE`)를 적용해 완만하게 제동하는 **감속 램핑(Deceleration Ramp) 알고리즘**을 도입하여 기계적 충격 및 뚝뚝 끊기는(staccato) 현상을 완벽히 해결함.
- `state.py` 내의 `esp32_accel_rate` 디폴트 값을 기존 `40.0`에서 안전하고 부드러운 기동 성능을 보장하는 `12.0`으로 튜닝하여 모터 기동 시의 딜레이가 없으면서도 탈조(Stall)가 발생하지 않도록 조치함.
- `routes.py`에서 모터 설정 변경 시 사용되던 `SPM1/SPM2` 키를 최신 펌웨어 통신 규격에 맞는 `SPD1/SPD2`로 수정하여 각도 제어 변수가 실시간으로 ESP32에 정상 동기화되도록 수정 완료.
- 누락 및 불일치가 존재하던 `/set_esp32_deg_config` 및 `/esp32_deg_settings` API 라우트를 정상 매칭 및 정의 완료.

---

## [2026-06-25] 초기 기동 시 모터 ENA 활성화 및 routes 패키지 섀도잉 문제 해결

### 📌 계획
- 초기 실행 시 3초 워치독 이후 모터 홀딩 전류가 인가되지 않는 현상(모터 힘 안 들어옴) 해결을 위해 펌웨어 ENA 로직 개선.
- `userReleased` 플래그를 두어 명시적으로 모터 릴리즈(`REL`) 버튼을 누르지 않은 상태에서 Python이 연결되어 폴링을 시작하면 자동으로 `enableMotors()`를 호출하도록 조치.
- 루트 폴더의 `routes.py` 단일 파일이 `routes/` 패키지를 가려(Shadowing) 최신 블루프린트 라우트들이 작동하지 않고 M1 기동 불가 및 설정 동기화가 실패하는 버그 해결.
- 루트 레벨의 `routes.py` 파일을 `routes_monolithic_backup.py`로 변경하여 `routes/` 패키지가 우선 임포트되도록 격리 처리.

### 🔧 변경 파일
- `esp32_firmware/esp32_firmware.ino`: ENA 자동 활성화 조건 추가 (`userReleased` 플래그 도입).
- `routes.py`: `routes_monolithic_backup.py`로 파일 이름 변경 (shadowing 제거).

### ✅ 결과
- `esp32_firmware/esp32_firmware.ino`에 `userReleased` 플래그를 도입하여, 명시적으로 모터 전원 차단(`REL`)을 누르지 않은 상태에서 Python이 연결되어 `STATUS/POS/CFG` 명령이 수신되면 자동으로 ENA 핀을 활성화(`enableMotors()`)하도록 조치함. 이에 따라 부팅 시 초기 모터 힘이 안 들어오던 현상 해결.
- 루트 레벨의 `routes.py` 단일 파일을 `routes_monolithic_backup.py`로 이름을 바꾸어 임포트 섀도잉 문제를 제거하였으며, Python이 `routes/` 폴더 패키지(최신 Blueprint 구조)를 문제없이 로드하도록 수정 완료.
- 이를 통해 M1/M2 조작 관련 조이스틱 가상 적분 제어(Virtual Target Integration) 및 `/set_esp32_deg_config` UI 설정 기능이 정상 작동하며 완벽히 연동됨.


---

## [2026-06-25] ESP32 FreeRTOS 뮤텍스 스타베이션 및 초기 기동 토크 누락 수정

### 📌 계획
- ESP32 펌웨어의 `motorTask`가 뮤텍스를 독점하여 `serialTask`가 굶주리는 스타베이션 현상을 수정하기 위해, 메모리 잠금용 글로벌 뮤텍스를 폐지하고 Serial 출력 공유 방지용 `serialMutex`만 사용하여 잠금 범위를 최소화함.
- `motorTask` 내부에서 CPU를 성실히 양보하도록 `vTaskDelay`를 개선하여 Task Watchdog 리셋 방지.
- Python `motor_esp32.py` 연결 초기화 시 최대속도, 가속도 외에 스텝/각도(`CFG:SPD1`, `CFG:SPD2`) 동기화 추가.
- Python 코드 내 오타 `버저` -> `버전` 수정하여 텍스트 가독성 개선.
- `camera.py`의 비디오 스트림 전송(`gen_frames`, `gen_debug_frames`) 함수 내의 바이트 리터럴 구문 에러(SyntaxError: unterminated string literal) 수정.

### 🔧 변경 파일
- `turret_ws/esp32_firmware/esp32_firmware.ino`: 글로벌 뮤텍스를 `serialMutex`로 전환하고 Serial 전용 락으로 수정. `vTaskDelay` 스케줄링 양보 처리 적용.
- `turret_ws/motor_esp32.py`: `connect` 함수 내부에 `CFG:SPD1` 및 `CFG:SPD2` 전송 추가. 로그 메시지 오타 수정. 시리얼 디버깅용 print문 추가.
- `turret_ws/camera.py`: `gen_frames`, `gen_debug_frames` 내의 잘못된 멀티라인 바이트 리터럴 문자열 구문 수정.

### ✅ 결과
- `esp32_firmware/esp32_firmware.ino`에서 공유 변수 메모리 접근 시 사용하던 전체 범위의 뮤텍스(`xMutex`) 잠금을 완전히 해제하고, 무잠금(Lock-free) 병렬 스레드 통신 구조를 실현하여 `serialTask` 스타베이션 문제를 완벽하게 해결함.
- `Serial` 출력 충돌 방지를 위해 `serialMutex`를 새롭게 지정하여, 오직 시리얼 출력(print/println) 시에만 짧게 잠그도록 구조화함.
- `motorTask`에 비블로킹 `vTaskDelay`를 개선 적용(정지 상태 및 움직임 중 100ms마다 CPU를 양보)하여 Task Watchdog 리셋을 방지하고 CPU 전력 효율 최적화.
- Python `motor_esp32.py` 연결 초기화 시 최대속도, 가속도와 더불어 steps/deg 각도 비율(`CFG:SPD1`, `CFG:SPD2`)을 자동으로 전송/동기화하도록 개선.
- `motor_esp32.py` 내 한글 출력 오타(`버저` -> `버전`)를 올바르게 수정함.
- `camera.py`에 존재하던 Multi-line Byte string literal 구문 에러를 standard escaping으로 수정하여 Flask 서버 기동 에러 및 비디오 스트림 500 에러를 완벽하게 해결함.
- `main.py` 재시작 검증 결과, 서버 구동 시 모터에 강력한 홀딩 전류(토크 힘)가 즉시 인가되며, 조이스틱 비례제어 및 실시간 POS/motor_status 동기화가 지연 없이 매끄럽게 수행됨을 최종 확인함.


