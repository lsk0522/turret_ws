"""ESP32 + DM542 스텝모터 시리얼 통신 — 통합 펌웨어 대응 (thread-safe)"""

import time
import threading
from queue import Queue

# Pylance 에러를 해결하기 위한 전역 변수 선언 (이 부분이 누락되었을 확률이 높습니다)
_move_queue = Queue()
_abort_event = threading.Event()

import state
from serial_utils import find_port

try:
    import serial   
    _serial_ok = True
except ImportError:
    serial = None  # type: ignore
    _serial_ok = False
    print("[esp32] pyserial 없음 → pip install pyserial")

# ── 전역 상태 ─────────────────────────────────────────────
_ser      = None
_thread   = None
_port     = None
_ser_lock = threading.Lock()

# ── 위치 제어 우선순위 큐 ──────────────────────────────────
_seq_counter         = 0
_seq_lock            = threading.Lock()
_first_pos_sync      = True
_abort_event         = threading.Event()

# ESP32 USB VID (CP210x, CH340, FTDI)
_ESP32_VIDS = {0x10C4, 0x1A86, 0x0403}


def connect(port=None, baudrate=115200):
    global _ser, _port, _first_pos_sync
    if not _serial_ok or state.device_type != "esp32":
        return

    if port is None:
        port = find_port(preferred_vids=_ESP32_VIDS)

    if port is None:
        print("[esp32] 포트를 찾을 수 없음")
        state.motor_connected = False
        state.motor_port = ""
        return

    try:
        new_ser = serial.Serial(port, baudrate, timeout=0.05)  # type: ignore
        new_ser.dtr = False
        new_ser.rts = False
        time.sleep(2)   # ESP32 리셋 대기
        with _ser_lock:
            _ser  = new_ser
            _port = port
        _first_pos_sync = True
        state.motor_connected = True
        state.motor_port = port
        print(f"[esp32] 연결: {port}")
        # 연결 직후 속도 & 가속도를 ESP32에 즉시 동기화 (1:5 기어비 기반 설정값)
        msl = int(state.esp32_max_speed_hz)
        acc = int(state.esp32_accel_rate * 10)  # ACC 명령은 x10 배율
        m1i = 1 if state.motor_m1_invert else 0
        m2i = 1 if state.motor_m2_invert else 0
        _send(f"CFG:MSL:{msl}\n")
        _send(f"CFG:ACC:{acc}\n")
        _send(f"CFG:M1I:{m1i}\n")
        _send(f"CFG:M2I:{m2i}\n")
        print(f"[esp32] 초기 동기화: MSL={msl}Hz, ACC={state.esp32_accel_rate}Hz/ms, M1I={m1i}, M2I={m2i}")
    except Exception as e:
        print(f"[esp32] 연결 실패 ({port}): {e}")
        state.motor_connected = False
        state.motor_port = ""


def safe_disconnect():
    """Thread-safe disconnect — Flask 라우트에서 호출 가능."""
    global _ser
    with _ser_lock:
        if _ser and _ser.is_open:
            try:
                _ser.close()
            except Exception:
                pass
        _ser = None
    state.motor_connected = False


def release_motors():
    """ESP32에 REL 명령 전송 → 홀딩 전류 즉시 해제.
    프로그램 종료 시 또는 수동 해제 시 호출.
    """
    _send("REL\n")
    if _ser:
        try:
            _ser.flush()
        except:
            pass
    import time
    time.sleep(0.1)
    print("[esp32] 모터 홀딩 전류 해제 (REL)")


def enable_motors():
    """ESP32에 ENA 명령 전송 → 홀딩 전류 재활성화."""
    _send("ENA\n")
    if _ser:
        try:
            _ser.flush()
        except:
            pass
    time.sleep(0.1)
    print("[esp32] 모터 홀딩 전류 활성화 (ENA)")


def _send(cmd: str):
    """Thread-safe 시리얼 쓰기."""
    global _ser
    with _ser_lock:
        if _ser is None:
            return
        try:
            _ser.write(cmd.encode())
        except Exception as e:
            print(f"[esp32] 전송 오류: {e}")
            try:
                _ser.close()
            except Exception:
                pass
            _ser = None
            state.motor_connected = False


def _parse_status(line: str):
    """POS: / VER: 피드백 파싱."""
    # ── 펌웨어 버전 수신 ──────────────────────────────────────────
    if line.startswith("VER:"):
        actual = line[4:].strip()
        state.firmware_version_actual = actual
        state.firmware_mismatch = (actual != state.EXPECTED_FIRMWARE_VERSION)
        if state.firmware_mismatch:
            print(f"[esp32] ⚠️ 펌웨어 버전 불일치! "
                  f"연결됨={actual!r}, 기대={state.EXPECTED_FIRMWARE_VERSION!r}")
        else:
            print(f"[esp32] ✅ 펌웨어 버저 확인: {actual}")
        return

    # ── 위치 피드백 ──────────────────────────────────────────
    if line.startswith("POS:"):
        global _first_pos_sync
        try:
            parts = line[4:].split(":")
            if len(parts) < 4:
                return
            state.esp32_pos_m1_deg = int(parts[0]) / 100.0
            state.esp32_pos_m2_deg = int(parts[1]) / 100.0
            state.esp32_speed_m1  = float(parts[2])
            state.esp32_speed_m2  = float(parts[3])

            if _first_pos_sync:
                state.last_queued_target_m1 = state.esp32_pos_m1_deg
                state.last_queued_target_m2 = state.esp32_pos_m2_deg
                _first_pos_sync = False
        except Exception:
            pass
        return

    # ── 기타 피드백 출력 (디버그용) ──────────────────────────
    if line.strip():
        print(f"[esp32 feedback] {line.strip()}")


_rx_buf = ""


def _run():
    global _rx_buf, _ser
    last_x, last_y = 320, 240
    last_t_time    = 0.0
    last_pos_req   = 0.0

    while True:
        # device_type이 esp32가 아니면 포트 해제
        if state.device_type != "esp32":
            with _ser_lock:
                if _ser and _ser.is_open:
                    try:
                        _ser.close()
                    except Exception:
                        pass
                    _ser = None
                    state.motor_connected = False
            time.sleep(0.5)
            continue

        with _ser_lock:
            ser_alive = _ser is not None and _ser.is_open

        if not ser_alive:
            state.motor_connected = False
            time.sleep(3)
            if not getattr(state, "pause_reconnect", False):
                connect(_port)
            continue

        state.motor_connected = True

        # 시리얼 수신
        try:
            with _ser_lock:
                if _ser and _ser.is_open:
                    waiting = _ser.in_waiting
                    if waiting:
                        raw = _ser.read(waiting)
                        _rx_buf += raw.decode('utf-8', errors='ignore')
                        while '\n' in _rx_buf:
                            line, _rx_buf = _rx_buf.split('\n', 1)
                            _parse_status(line.strip())
        except Exception as e:
            print(f"[esp32] 수신 오류: {e}")
            with _ser_lock:
                try:
                    if _ser:
                        _ser.close()
                except Exception:
                    pass
                _ser = None
            state.motor_connected = False

        now = time.time()

        # track 모드: T:x:y 전송 (좌표 변경 시 즉시 + 50ms heartbeat)
        if state.esp32_control_mode == "track":
            x, y = state.point[0], state.point[1]
            if abs(x - last_x) >= 1 or abs(y - last_y) >= 1 or (now - last_t_time > 0.05):
                _send(f"T:{x}:{y}\n")
                last_x, last_y = x, y
                last_t_time = now

        # POS 주기 요청 (100ms)
        if now - last_pos_req > 0.1:
            _send("POS\n")
            last_pos_req = now

        time.sleep(0.005)


def send_config(key: str, value):
    """CFG:KEY:VALUE 명령 전송 (속도/가속도/steps 등 실시간 변경)."""
    _send(f"CFG:{key}:{value}\n")


def set_mode(mode: str):
    """'track' 또는 'pos' 모드 전환. 연결 시에만 state 업데이트."""
    with _ser_lock:
        connected = _ser is not None and _ser.is_open
    if connected:
        cmd = "MODE:TRACK" if mode == "track" else "MODE:POS"
        _send(cmd + "\n")
        state.esp32_control_mode = mode


def _get_next_seq():
    global _seq_counter
    with _seq_lock:
        _seq_counter += 1
        return _seq_counter


def move_deg(target: str, mm: float):
    """절대 위치 이동."""
    _send(f"MOVE J {target} {mm:.3f}\n")


def move_relative_deg(target: str, delta: float):
    """상대 위치 이동."""
    cur = state.esp32_pos_m1_deg if target == "M1" else state.esp32_pos_m2_deg
    _send(f"MOVE J {target} {cur + delta:.3f}\n")

def set_home():
    """현재 위치를 원점(0mm)으로 설정."""
    with _ser_lock:
        connected = _ser is not None and _ser.is_open
    if connected:
        _send("SETHOME\n")
        state.esp32_pos_m1_deg = 0.0
        state.esp32_pos_m2_deg = 0.0
        state.last_queued_target_m1 = 0.0
        state.last_queued_target_m2 = 0.0
        return True
    return False


def stop_motors():
    """조이스틱 릴리즈 시 즉시 정지.
    펌웨어 v2.0.7부터 S 명령이 targetPos=currentPos, speed=0 즉시 적용.
    """
    state.motor_stopped = True
    state.motor_moving = False
    _send("JOG 0.0 0.0\n")  # JOG 모드 확실히 종료
    _send("S\n")            # 혹시 모를 관성 강제 정지
    print("\n[esp32] 🛑 조이스틱 정지 명령(JOG 0 0 + S) 전송됨! (즉시 멈춰야 정상)\n")
    _abort_event.set()
    while not _move_queue.empty():
        try:
            _move_queue.get_nowait()
            _move_queue.task_done()
        except Exception:
            break
    state.last_queued_target_m1 = state.esp32_pos_m1_deg
    state.last_queued_target_m2 = state.esp32_pos_m2_deg


def start(port=None):
    global _thread
    connect(port)
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()
