"""
Arduino Uno + DM542 스텝모터 시리얼 통신

전송: JSON 패킷 1회 (Apply/E-Stop/Home 버튼 클릭 시에만)
수신: {"id":1,"pos":123} 형태 위치 피드백
"""

import json
import threading
import time

import state
from serial_utils import find_port

try:
    import serial
    _serial_ok = True
except ImportError:
    serial = None  # type: ignore
    _serial_ok = False
    print("[arduino] pyserial 없음 → pip install pyserial")

_ser    = None
_thread = None
_port   = None
_lock   = threading.Lock()


def connect(port=None, baudrate=115200):
    global _ser, _port
    if not _serial_ok or state.device_type != "arduino":
        return

    if port is None:
        port = find_port()   # Arduino는 VID 필터 없이 첫 번째 포트

    if port is None:
        print("[arduino] 포트를 찾을 수 없음")
        state.motor_connected = False
        state.motor_port = ""
        return

    try:
        _ser  = serial.Serial(port, baudrate, timeout=0.05) # type: ignore
        _port = port
        time.sleep(2)   # 아두이노 리셋 대기
        state.motor_connected = True
        state.motor_port = port
        print(f"[arduino] 연결: {port}")
    except Exception as e:
        print(f"[arduino] 연결 실패 ({port}): {e}")
        _ser = None
        state.motor_connected = False
        state.motor_port = ""


def _send_packet(packet: dict) -> bool:
    """JSON 패킷 단일 전송."""
    global _ser
    with _lock:
        if not _ser or not _ser.is_open:
            return False
        try:
            _ser.write((json.dumps(packet, separators=(',', ':')) + '\n').encode())
            return True
        except Exception as e:
            print(f"[arduino] 전송 오류: {e}")
            try:
                _ser.close()
            except Exception:
                pass
            _ser = None
            state.motor_connected = False
            return False


def send_config(dead_zone: int, max_steps: int, steps_per_px: float,
                pulse_us: int, cmd_timeout_ms: int,
                m1_invert: bool, m2_invert: bool) -> bool:
    """파라미터 설정 JSON을 Arduino에 1회 전송."""
    return _send_packet({
        "cmd": "CFG",
        "dz":  dead_zone,
        "ms":  max_steps,
        "sp":  round(steps_per_px * 1000),
        "pu":  pulse_us,
        "to":  cmd_timeout_ms,
        "m1i": 1 if m1_invert else 0,
        "m2i": 1 if m2_invert else 0,
    })


def degrees_to_steps(degrees: float) -> int:
    return round(degrees / 360.0 * state.arduino_steps_per_rev)


def run(motor_id: int, degrees: float, max_speed: int, accel: int) -> bool:
    """RUN 명령 패킷 1회 전송."""
    steps = degrees_to_steps(degrees)
    return _send_packet({"id": motor_id, "pos": steps,
                         "spd": max_speed, "acc": accel, "cmd": "RUN"})


def estop() -> bool:
    """비상 정지 — 두 모터 즉시 STOP."""
    ok1 = _send_packet({"id": 1, "cmd": "STOP"})
    ok2 = _send_packet({"id": 2, "cmd": "STOP"})
    return ok1 or ok2


def safe_disconnect():
    """Thread-safe disconnect for shutdown and controller switching."""
    global _ser
    with _lock:
        if _ser and _ser.is_open:
            try:
                _ser.close()
            except Exception:
                pass
        _ser = None
    state.motor_connected = False


def home(motor_id: int) -> bool:
    """원점 복귀."""
    return _send_packet({"id": motor_id, "cmd": "HOME"})


# ── 수신 루프 ─────────────────────────────────────────────
_rx_buf = ""


def _parse_feedback(line: str):
    """{\"id\":1,\"pos\":123} → state 갱신."""
    try:
        d = json.loads(line)
        mid, pos = d.get("id"), d.get("pos")
        if mid == 1 and pos is not None:
            state.arduino_pos_m1 = int(pos)
        elif mid == 2 and pos is not None:
            state.arduino_pos_m2 = int(pos)
    except Exception:
        pass


def _run():
    global _rx_buf, _ser

    while True:
        if state.device_type != "arduino":
            if _ser and _ser.is_open:
                try:
                    _ser.close()
                except Exception:
                    pass
                _ser = None
                state.motor_connected = False
            time.sleep(0.5)
            continue

        if _ser is None or not _ser.is_open:
            state.motor_connected = False
            time.sleep(3)
            connect(_port)
            continue

        state.motor_connected = True

        try:
            waiting = _ser.in_waiting
            if waiting:
                raw = _ser.read(waiting)
                _rx_buf += raw.decode('utf-8', errors='ignore')
                while '\n' in _rx_buf:
                    line, _rx_buf = _rx_buf.split('\n', 1)
                    _parse_feedback(line.strip())
        except Exception as e:
            print(f"[arduino] 수신 오류: {e}")
            try:
                _ser.close()
            except Exception:
                pass
            _ser = None
            state.motor_connected = False

        time.sleep(0.05)   # 20 Hz 수신


def start(port=None):
    global _thread
    connect(port)
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()
