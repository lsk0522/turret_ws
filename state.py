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

# ESP32로부터 수신한 레거시 track 프로토콜 상태 (호환용으로 유지)
motor_target_x  = 320
motor_target_y  = 240
motor_error_x   = 0
motor_error_y   = 0
motor_steps_m1  = 0
motor_steps_m2  = 0
motor_moving    = False
motor_timeout   = False

# ── 기기 타입 ──────────────────────────────────────────────
device_type = "esp32"   # "esp32" | "arduino"

# ── ESP32 런타임 파라미터 (CFG: 명령으로 동기화) ──────────
motor_dead_zone      = 8
motor_max_steps      = 25
motor_steps_per_px   = 0.060
motor_pulse_us       = 5
motor_m1_invert      = False
motor_m2_invert      = False
motor_cmd_timeout_ms = 600

# ── ESP32 mm 위치 제어 ────────────────────────────────────
esp32_control_mode    = "track"
esp32_steps_per_mm_m1 = 78.0
esp32_steps_per_mm_m2 = 78.0
esp32_max_speed_hz    = 750.0  # speed=5 기본값 (5 × 150Hz)
esp32_accel_rate      = 5.0

# ESP32 mm 위치 피드백
esp32_pos_m1_mm = 0.0
esp32_pos_m2_mm = 0.0
esp32_speed_m1  = 0.0
esp32_speed_m2  = 0.0

# ── Arduino 설정 ──────────────────────────────────────────
arduino_steps_per_rev = 1600
arduino_m1_max_speed  = 400
arduino_m1_accel      = 100
arduino_m2_max_speed  = 400
arduino_m2_accel      = 100
arduino_pos_m1        = 0
arduino_pos_m2        = 0

# ── 큐 추적 변수 ──────────────────────────────────────────
last_queued_target_m1 = 0.0
last_queued_target_m2 = 0.0
