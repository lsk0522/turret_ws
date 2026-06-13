"""ESP32 + DM542 스텝모터 시리얼 통신 — 통합 펌웨어 대응 (thread-safe)"""

import threading
import time
import queue

import state
from serial_utils import find_port

try:
    import serial
    _serial_ok = True
except ImportError:
    _serial_ok = False
    print("[esp32] pyserial 없음 → pip install pyserial")

# ── 전역 상태 ─────────────────────────────────────────────
_ser      = None
_thread   = None
_port     = None
_ser_lock = threading.Lock()

# ── 위치 제어 우선순위 큐 ──────────────────────────────────
_move_queue          = queue.PriorityQueue(maxsize=20)
_seq_counter         = 0
_seq_lock            = threading.Lock()
_first_pos_sync      = True
_queue_worker_thread = None
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
        new_ser = serial.Serial(port, baudrate, timeout=0.05)
        time.sleep(2)   # ESP32 리셋 대기
        with _ser_lock:
            _ser  = new_ser
            _port = port
        _first_pos_sync = True
        state.motor_connected = True
        state.motor_port = port
        print(f"[esp32] 연결: {port}")
        # 연결 직후 현재 감도(MSL)를 ESP32에 즉시 동기화
        hz = state.speed * 150
        state.esp32_max_speed_hz = hz
        _send(f"CFG:MSL:{hz}\n")
        print(f"[esp32] 초기 속도 동기화: MSL={hz}Hz (speed={state.speed})")
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
    """POS: 피드백 파싱."""
    if line.startswith("POS:"):
        global _first_pos_sync
        try:
            parts = line[4:].split(":")
            if len(parts) < 4:
                return
            state.esp32_pos_m1_mm = int(parts[0]) / 100.0
            state.esp32_pos_m2_mm = int(parts[1]) / 100.0
            state.esp32_speed_m1  = float(parts[2])
            state.esp32_speed_m2  = float(parts[3])

            if _first_pos_sync:
                state.last_queued_target_m1 = state.esp32_pos_m1_mm
                state.last_queued_target_m2 = state.esp32_pos_m2_mm
                _first_pos_sync = False
        except Exception:
            pass


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

        # track 모드: T:x:y 전송 (throttled + 200ms heartbeat)
        if state.esp32_control_mode == "track":
            x, y = state.point[0], state.point[1]
            if abs(x - last_x) >= 1 or abs(y - last_y) >= 1 or (now - last_t_time > 0.2):
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


def enqueue_move(target: str, val: float, is_absolute: bool = True):
    """이동 명령을 우선순위 큐에 추가."""
    global _move_queue
    axis = target.upper().replace(' ', '')

    # 큐가 비었으면 queued target을 실제 위치에 동기화
    if _move_queue.empty():
        state.last_queued_target_m1 = state.esp32_pos_m1_mm
        state.last_queued_target_m2 = state.esp32_pos_m2_mm

    valid_axes = [a.strip() for a in axis.split(',') if a.strip() in ('M1', 'M2')]
    if not valid_axes:
        return False

    # M1,M2 동시 이동
    if len(valid_axes) == 2:
        if is_absolute:
            target_abs, priority = val, 10
        else:
            target_abs, priority = state.last_queued_target_m1 + val, 20
        state.last_queued_target_m1 = target_abs
        state.last_queued_target_m2 = target_abs
        try:
            _move_queue.put_nowait((_get_next_seq(), priority, 'M1,M2', target_abs))
        except queue.Full:
            pass
        return True

    # 단일 축
    a = valid_axes[0]
    if is_absolute:
        target_abs, priority = val, 10
    else:
        base = state.last_queued_target_m1 if a == 'M1' else state.last_queued_target_m2
        target_abs, priority = base + val, 20

    if a == 'M1':
        state.last_queued_target_m1 = target_abs
    else:
        state.last_queued_target_m2 = target_abs

    try:
        _move_queue.put_nowait((_get_next_seq(), priority, a, target_abs))
    except queue.Full:
        pass
    return True


def move_mm(target: str, mm: float):
    """절대 위치 이동 (큐 추가)."""
    return enqueue_move(target, mm, is_absolute=True)


def move_relative_mm(target: str, delta: float):
    """상대 위치 이동 (큐 추가)."""
    return enqueue_move(target, delta, is_absolute=False)


def _queue_worker():
    while True:
        try:
            seq, priority, axis, target_mm = _move_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        with _ser_lock:
            connected = _ser is not None and _ser.is_open
        if not connected:
            _move_queue.task_done()
            continue

        _abort_event.clear()

        # POS 모드 자동 전환
        if state.esp32_control_mode != "pos":
            _send("MODE:POS\n")
            state.esp32_control_mode = "pos"
            time.sleep(0.1)

        cmd = f"MOVE J {axis} {target_mm:.3f}\n"
        _send(cmd)

        dist = 0.0
        if 'M1' in axis:
            dist = max(dist, abs(target_mm - state.esp32_pos_m1_mm))
        if 'M2' in axis:
            dist = max(dist, abs(target_mm - state.esp32_pos_m2_mm))

        max_spd = state.esp32_max_speed_hz / max(state.esp32_steps_per_mm_m1, 1)
        timeout = min(8.0, max(2.0, dist / max_spd * 3.0 + 2.0) if max_spd > 0 else 2.0)

        DONE_THRESHOLD = 0.30
        start_time = time.time()
        time.sleep(0.05)

        while time.time() - start_time < timeout:
            if _abort_event.is_set():
                break
            m1_ok = (abs(state.esp32_pos_m1_mm - target_mm) < DONE_THRESHOLD) if 'M1' in axis else True
            m2_ok = (abs(state.esp32_pos_m2_mm - target_mm) < DONE_THRESHOLD) if 'M2' in axis else True
            if m1_ok and m2_ok:
                break
            time.sleep(0.01)

        _move_queue.task_done()


def set_home():
    """현재 위치를 원점(0mm)으로 설정."""
    with _ser_lock:
        connected = _ser is not None and _ser.is_open
    if connected:
        _send("SETHOME\n")
        state.esp32_pos_m1_mm = 0.0
        state.esp32_pos_m2_mm = 0.0
        state.last_queued_target_m1 = 0.0
        state.last_queued_target_m2 = 0.0
        return True
    return False


def stop_motors():
    """활성 이동 중단 및 큐 비우기."""
    _abort_event.set()
    while not _move_queue.empty():
        try:
            _move_queue.get_nowait()
            _move_queue.task_done()
        except Exception:
            break
    state.last_queued_target_m1 = state.esp32_pos_m1_mm
    state.last_queued_target_m2 = state.esp32_pos_m2_mm
    _send("S\n")


def start(port=None):
    global _thread, _queue_worker_thread
    connect(port)
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()
    _queue_worker_thread = threading.Thread(target=_queue_worker, daemon=True)
    _queue_worker_thread.start()
