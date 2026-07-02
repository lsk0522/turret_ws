point = [320, 240]
last_point = None
flip_enabled = False
current_frame = None

# 조작 설정
speed        = 5
control_mode = "manual"
input_mode   = "joystick"   # "joystick" | "pointer" | "auto"

# 볼/추적 상태
ball             = None    # 검출된 공 정보 (dict)
ball_lost        = False   # 칼만 예측만 사용 중 여부
tracking_mode    = "none"  # "none" | "custom"
learning_progress = 0
learning_failed   = False

# ── 모터 연결 상태 ─────────────────────────────────────────
motor_connected = False
motor_port      = ""



# ── 기기 타입 ──────────────────────────────────────────────
device_type = "esp32"   # "esp32" | "arduino"

# ── ESP32 런타임 파라미터 (CFG: 명령으로 동기화) ──────────
motor_dead_zone      = 8
motor_max_steps      = 25
motor_steps_per_px   = 3.5
motor_pulse_us       = 5
motor_m1_invert      = False
motor_m2_invert      = True   # 수직(Tilt) 모터는 물리적으로 반전 — 기본값 True
motor_cmd_timeout_ms = 600

# ── ESP32 mm 위치 제어 ────────────────────────────────────
esp32_control_mode    = "pos"
esp32_steps_per_deg_m1 = 44.44
esp32_steps_per_deg_m2 = 44.44
esp32_max_speed_hz    = 3000.0
esp32_accel_rate      = 15.0     # 0→3000Hz 도달에 200ms (매우 빠른 반응성)
# ESP32 deg 위치 피드백
esp32_pos_m1_deg = 0.0
esp32_pos_m2_deg = 0.0
esp32_speed_m1  = 0.0
esp32_speed_m2  = 0.0


# ── 큐 추적 변수 ──────────────────────────────────────────
last_queued_target_m1 = 0.0
last_queued_target_m2 = 0.0

# ── 펌웨어 버전 관리 ──────────────────────────────────────
# 백엔드가 기대하는 ESP32 펌웨어 버전 (펌웨어 수정 시 이 값도 함께 올리세요)
EXPECTED_FIRMWARE_VERSION = "2.0.7"

# 실제로 연결된 ESP32가 보고한 버전
firmware_version_actual   = ""      # VER: 수신 전까지 빈 문자열
firmware_mismatch         = False   # True 이면 UI가 경고 모달을 표시

# ── 모터 실시간 상태 (motor_status 라우트용) ─────────────
motor_target_x  = 0
motor_target_y  = 0
motor_error_x   = 0
motor_error_y   = 0
motor_steps_m1  = 0
motor_steps_m2  = 0
motor_moving    = False
motor_timeout   = False
motor_stopped   = True

# ── Arduino Uno 호환 파라미터 ─────────────────────────────
# (device_type == "arduino" 선택 시 사용)
arduino_steps_per_rev = 1600
arduino_m1_max_speed  = 800
arduino_m1_accel      = 400
arduino_m2_max_speed  = 800
arduino_m2_accel      = 400
arduino_pos_m1        = 0
arduino_pos_m2        = 0

pause_reconnect       = False   # 펌웨어 업로드 중 재연결 방지 플래그
