point = [320, 240]

last_point = None

flip_enabled = False

current_frame = None

# Settings

speed = 3

control_mode = "manual"

# Input control mode: "joystick" | "pointer" | "auto"
input_mode = "joystick"


# 야구공 검출 상태

ball = None        # 검출된 공 정보 (dict)
ball_lost = False  # 칼만 예측만 사용 중 여부

# 추적 모드: "none" | "custom"

tracking_mode = "none"

# ORB 학습 진행률 (0~100)

learning_progress = 0
learning_failed = False

# ─── 모터 연결 상태 ────────────────────────────────────────

motor_connected   = False
motor_port        = ""

# ESP32로부터 수신한 실시간 상태 (ST: 메시지 파싱)
motor_target_x    = 320
motor_target_y    = 240
motor_error_x     = 0
motor_error_y     = 0
motor_steps_m1    = 0
motor_steps_m2    = 0
motor_moving      = False
motor_timeout     = False
motor_stopped     = False

# Dynamic UI/Processing attributes
is_running = True
threaded = True

# ─── 연결된 기기 타입 ─────────────────────────────────────────
# "esp32" | "arduino"
device_type = "esp32"

# ─── ESP32 모터 런타임 설정 (CFG: 명령으로 ESP32에 동기화) ───
motor_dead_zone      = 8      # 데드존 (픽셀)
motor_max_steps      = 25     # 한 사이클 최대 스텝
motor_steps_per_px   = 0.060  # 픽셀당 스텝
motor_pulse_us       = 5      # 펄스 폭 (μs)
motor_m1_invert      = False  # M1 방향 반전
motor_m2_invert      = False  # M2 방향 반전
motor_cmd_timeout_ms = 600    # 명령 타임아웃 (ms)

# ─── ESP32 mm 위치 제어 파라미터 ─────────────────────────────────
# 모드: "track" | "pos"
esp32_control_mode    = "track"

esp32_steps_per_mm_m1 = 78.0   # M1 steps/mm (DM542 마이크로스텝 × 기어비)
esp32_steps_per_mm_m2 = 78.0   # M2 steps/mm
esp32_max_speed_hz    = 1000.0 # 최대 구동 주파수 Hz
esp32_accel_rate      = 5.0    # 가속도 (Hz/ms) — 너무 높으면 탈조 발생

# ─── ESP32 mm 위치 피드백 (POS: 메시지 파싱) ─────────────────────
esp32_pos_m1_mm  = 0.0   # M1 현재 위치 (mm)
esp32_pos_m2_mm  = 0.0   # M2 현재 위치 (mm)
esp32_speed_m1   = 0.0   # M1 현재 속도 (Hz)
esp32_speed_m2   = 0.0   # M2 현재 속도 (Hz)

# ─── Arduino Uno 스텝모터 설정 (DM542) ──────────────────────────
arduino_steps_per_rev  = 1600   # 1회전당 스텝 수 (DM542 마이크로스텝 설정에 따름)
arduino_m1_max_speed   = 400    # M1 최대 속도 (steps/s)
arduino_m1_accel       = 100    # M1 가속도 (steps/s²)
arduino_m2_max_speed   = 400    # M2 최대 속도 (steps/s)
arduino_m2_accel       = 100    # M2 가속도 (steps/s²)

# Arduino 피드백 (수신)
arduino_pos_m1 = 0   # M1 현재 위치 (steps)
arduino_pos_m2 = 0   # M2 현재 위치 (steps)

# ─── ESP32 위치 제어 큐 추적 변수 ────────────────────────────
last_queued_target_m1 = 0.0
last_queued_target_m2 = 0.0
