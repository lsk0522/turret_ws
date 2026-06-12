"""ESP32 + DM542 스텝모터 시리얼 통신 — 통합 펌웨어 대응"""

import glob
import threading
import time
import queue

import state

try:
    import serial
    _serial_ok = True
except ImportError:
    _serial_ok = False
    print("[esp32] pyserial 없음 → pip install pyserial")

_ser    = None
_thread = None
_port   = None

# ─── 위치 제어 우선순위 큐 상태 ─────────────────────────────────
_move_queue = queue.PriorityQueue()
_seq_counter = 0
_seq_lock = threading.Lock()
_first_pos_sync = True
_queue_worker_thread = None
_abort_active_job = False

import sys

def _find_port():
    if sys.platform.startswith('win'):
        try:
            import serial.tools.list_ports
            ports = [p.device for p in serial.tools.list_ports.comports()]
            return ports[0] if ports else None
        except Exception:
            return None
    else:
        candidates = sorted(
            glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        )
        return candidates[0] if candidates else None


def connect(port=None, baudrate=115200):
    global _ser, _port, _first_pos_sync
    if not _serial_ok or state.device_type != "esp32":
        return

    if port is None:
        port = _find_port()

    if port is None:
        print("[esp32] 포트를 찾을 수 없음")
        state.motor_connected = False
        state.motor_port = ""
        return

    try:
        _ser  = serial.Serial(port, baudrate, timeout=0.05)
        _port = port
        time.sleep(2)
        state.motor_connected = True
        state.motor_port = port
        _first_pos_sync = True
        print(f"[esp32] 연결: {port}")
    except Exception as e:
        print(f"[esp32] 연결 실패 ({port}): {e}")
        _ser = None
        state.motor_connected = False
        state.motor_port = ""


def _send(cmd: str):
    global _ser
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
    """ST: (추적 모드) 또는 POS: (위치 모드) 메시지 파싱"""

    # ── 추적 모드 피드백 ────────────────────────────────────────────────
    if line.startswith("ST:"):
        try:
            parts = line[3:].split(":")
            if len(parts) < 8:
                return
            state.motor_target_x = int(parts[0])
            state.motor_target_y = int(parts[1])
            state.motor_error_x  = int(parts[2])
            state.motor_error_y  = int(parts[3])
            state.motor_steps_m1 = int(parts[4])
            state.motor_steps_m2 = int(parts[5])
            st = int(parts[6])
            state.motor_moving  = (st == 1)
            state.motor_timeout = (st == 2)
            state.motor_stopped = (st == 3)
        except Exception:
            pass
        return

    # ── 위치 제어 피드백 ─────────────────────────────────────────────────
    if line.startswith("POS:"):
        global _first_pos_sync
        try:
            parts = line[4:].split(":")
            if len(parts) < 4:
                return
            # mm × 100 정수 → mm 실수
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
        return


_rx_buf = ""


def _run():
    global _rx_buf, _ser
    last_x, last_y = 320, 240

    while True:
        # device_type이 esp32가 아니면 포트 해제 후 대기
        if state.device_type != "esp32":
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
                    _parse_status(line.strip())
        except Exception as e:
            print(f"[esp32] 수신 오류: {e}")
            try:
                _ser.close()
            except Exception:
                pass
            _ser = None
            state.motor_connected = False

        # 추적 모드일 때만 T:x:y 좌표 전송
        now = time.time()
        if state.esp32_control_mode == "track":
            x = state.point[0]
            y = state.point[1]
            if abs(x - last_x) >= 1 or abs(y - last_y) >= 1 or (now - getattr(state, '_last_t_time', 0) > 0.2):
                _send(f"T:{x}:{y}\n")
                last_x, last_y = x, y
                state._last_t_time = now

        # ESP32는 POS/STATUS 요청을 받아야 위치 피드백(POS:x:y)을 보냅니다.
        # 위치 제어 모드 등에서 상태를 알기 위해 주기적(약 100ms)으로 POS 요청을 보냅니다.
        if now - getattr(state, '_last_pos_req_time', 0) > 0.1:
            _send("POS\n")
            state._last_pos_req_time = now

        time.sleep(0.005)


def send_config(key: str, value):
    """CFG:KEY:VALUE 명령 전송 (추적 모드 파라미터)"""
    if _ser and _ser.is_open:
        _send(f"CFG:{key}:{value}\n")


def set_mode(mode: str):
    """모드 전환: 'track' 또는 'pos'"""
    if _ser and _ser.is_open:
        cmd = "MODE:TRACK" if mode == "track" else "MODE:POS"
        _send(cmd + "\n")
    state.esp32_control_mode = mode


def _get_next_seq():
    global _seq_counter
    with _seq_lock:
        _seq_counter += 1
        return _seq_counter


def enqueue_move(target: str, val: float, is_absolute: bool = True):
    global _move_queue
    axis = target.upper().replace(' ', '')

    # If the queue is empty, sync our 'last queued target' to the real current position
    # so that relative jumps don't start from an old, stale coordinate.
    if _move_queue.empty():
        state.last_queued_target_m1 = state.esp32_pos_m1_mm
        state.last_queued_target_m2 = state.esp32_pos_m2_mm

    valid_axes = [a.strip() for a in axis.split(',') if a.strip() in ('M1', 'M2')]
    if not valid_axes:
        return False

    # ── M1,M2 동시 명령: 큐에 단일 항목으로 삽입 ───────────────────
    # 분리하면 순차 실행되므로, 'M1,M2' 축을 그대로 하나의 큐 항목으로 넣어
    # ESP32에 "MOVE J M1,M2 <mm>" 명령을 한 번에 전송한다.
    if len(valid_axes) == 2:
        if is_absolute:
            target_abs = val
            priority = 10
        else:
            # 상대 이동: 두 축 모두 같은 delta 적용
            target_abs = state.last_queued_target_m1 + val
            priority = 20
        state.last_queued_target_m1 = target_abs
        state.last_queued_target_m2 = target_abs
        seq = _get_next_seq()
        _move_queue.put((priority, seq, 'M1,M2', target_abs))
        return True

    # ── 단일 축 명령 ────────────────────────────────────────────────
    a = valid_axes[0]
    if is_absolute:
        target_abs = val
        priority = 10
    else:
        if a == 'M1':
            target_abs = state.last_queued_target_m1 + val
        else:
            target_abs = state.last_queued_target_m2 + val
        priority = 20

    if a == 'M1':
        state.last_queued_target_m1 = target_abs
    else:
        state.last_queued_target_m2 = target_abs

    seq = _get_next_seq()
    _move_queue.put((priority, seq, a, target_abs))
    return True


def move_mm(target: str, mm: float):
    """절대 위치 이동 명령 (큐 삽입)"""
    return enqueue_move(target, mm, is_absolute=True)


def move_relative_mm(target: str, delta: float):
    """상대 위치 이동 명령 (큐 삽입)"""
    return enqueue_move(target, delta, is_absolute=False)


def _queue_worker():
    global _move_queue, _abort_active_job
    while True:
        try:
            priority, seq, axis, target_mm = _move_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        if not _ser or not _ser.is_open:
            print("[esp32-queue] 연결되지 않음. 작업 스킵.")
            _move_queue.task_done()
            continue

        _abort_active_job = False

        # Auto-switch to POS mode if needed
        if state.esp32_control_mode != "pos":
            _send("MODE:POS\n")
            state.esp32_control_mode = "pos"
            time.sleep(0.1)  # brief settle time

        cmd = f"MOVE J {axis} {target_mm:.3f}\n"
        print(f"[esp32-queue] 전송: {cmd.strip()} (priority={priority}, seq={seq})")
        _send(cmd)

        # Wait for movement completion via POS feedback
        # Timeout: generous but bounded
        dist = 0.0
        if 'M1' in axis:
            dist = max(dist, abs(target_mm - state.esp32_pos_m1_mm))
        if 'M2' in axis:
            dist = max(dist, abs(target_mm - state.esp32_pos_m2_mm))

        max_spd = state.esp32_max_speed_hz / max(state.esp32_steps_per_mm_m1, 1)
        duration_est = dist / max_spd if max_spd > 0 else 0
        timeout = max(2.0, duration_est * 3.0 + 2.0)
        timeout = min(8.0, timeout)  # 최대 8초로 제한 (이전: 20초)

        start_time = time.time()
        time.sleep(0.05)  # wait for first POS feedback

        # 완료 판정 임계값: 0.30mm (이전 0.10mm보다 넓혀서 근사 위치에서 빠르게 완료)
        DONE_THRESHOLD = 0.30

        while time.time() - start_time < timeout:
            if _abort_active_job:
                print(f"[esp32-queue] 중단됨: {axis} -> {target_mm:.3f}mm")
                break

            m1_done = True
            m2_done = True
            if 'M1' in axis:
                m1_done = (abs(state.esp32_pos_m1_mm - target_mm) < DONE_THRESHOLD)
            if 'M2' in axis:
                m2_done = (abs(state.esp32_pos_m2_mm - target_mm) < DONE_THRESHOLD)

            if m1_done and m2_done:
                break
            time.sleep(0.01)

        elapsed = time.time() - start_time
        print(f"[esp32-queue] 완료: {axis} -> {target_mm:.3f}mm (경과: {elapsed:.2f}s)")
        _move_queue.task_done()




def set_home():
    """현재 위치를 원점(0mm)으로 설정"""
    if _ser and _ser.is_open:
        _send("SETHOME\n")
        state.esp32_pos_m1_mm = 0.0
        state.esp32_pos_m2_mm = 0.0
        state.last_queued_target_m1 = 0.0
        state.last_queued_target_m2 = 0.0
        return True
    return False


def request_status():
    """즉시 POS 피드백 요청"""
    if _ser and _ser.is_open:
        _send("STATUS\n")


def send_mm_config(key: str, value):
    """위치 제어 전용 CFG 파라미터 전송"""
    if _ser and _ser.is_open:
        _send(f"CFG:{key}:{value}\n")


def start(port=None):
    global _thread, _queue_worker_thread
    connect(port)
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()
    _queue_worker_thread = threading.Thread(target=_queue_worker, daemon=True)
    _queue_worker_thread.start()


def stop_motors():
    global _move_queue, _abort_active_job
    _abort_active_job = True
    # 큐 비우기
    while not _move_queue.empty():
        try:
            _move_queue.get_nowait()
            _move_queue.task_done()
        except Exception:
            break
    # 목표 지점 트래커를 현재 위치로 강제 동기화
    state.last_queued_target_m1 = state.esp32_pos_m1_mm
    state.last_queued_target_m2 = state.esp32_pos_m2_mm
    if _ser and _ser.is_open:
        _send("S\n")
