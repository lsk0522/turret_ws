"""ESP32 + DM542 스텝모터 시리얼 통신 — 통합 펌웨어 대응 (thread-safe 개선판)"""

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

_ser      = None
_thread   = None
_port     = None
_ser_lock = threading.Lock()   # Protect _ser from concurrent read/write across threads

# ─── 위치 제어 우선순위 큐 ────────────────────────────────────
_move_queue          = queue.PriorityQueue(maxsize=20)  # Bounded to prevent unbounded growth
_seq_counter         = 0
_seq_lock            = threading.Lock()
_first_pos_sync      = True
_queue_worker_thread = None
_abort_event         = threading.Event()  # Replaces plain bool flag (thread-safe)

import sys

def _find_port():
    """Find the first available serial port, preferring known ESP32 USB VID/PID."""
    if sys.platform.startswith('win'):
        try:
            import serial.tools.list_ports
            # Prefer known ESP32 USB-UART chips by VID (CP210x=0x10C4, CH340=0x1A86, FTDI=0x0403)
            ESP32_VIDS = {0x10C4, 0x1A86, 0x0403}
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                if p.vid in ESP32_VIDS:
                    return p.device
            # Fallback: first available port
            return ports[0].device if ports else None
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
        new_ser = serial.Serial(port, baudrate, timeout=0.05)
        # ESP32 resets on serial connect — wait in background to avoid blocking
        time.sleep(2)
        with _ser_lock:
            _ser  = new_ser
            _port = port
        _first_pos_sync = True
        state.motor_connected = True
        state.motor_port = port
        print(f"[esp32] 연결: {port}")
    except Exception as e:
        print(f"[esp32] 연결 실패 ({port}): {e}")
        state.motor_connected = False
        state.motor_port = ""


def safe_disconnect():
    """Thread-safe disconnect — called from Flask routes without disrupting _run()."""
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
    """Thread-safe serial write."""
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
    """Parse ST: (track mode) or POS: (position mode) feedback from ESP32."""

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
        return


_rx_buf = ""


def _run():
    global _rx_buf, _ser
    last_x, last_y  = 320, 240
    last_t_time     = 0.0
    last_pos_req    = 0.0

    while True:
        # Release port if device type changed
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

        # Serial receive
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

        # Send T:x:y in track mode (throttled + 200ms heartbeat)
        if state.esp32_control_mode == "track":
            x, y = state.point[0], state.point[1]
            if abs(x - last_x) >= 1 or abs(y - last_y) >= 1 or (now - last_t_time > 0.2):
                _send(f"T:{x}:{y}\n")
                last_x, last_y = x, y
                last_t_time = now

        # Periodic POS request every 100ms
        if now - last_pos_req > 0.1:
            _send("POS\n")
            last_pos_req = now

        time.sleep(0.005)


def send_config(key: str, value):
    """Send CFG:KEY:VALUE command (tracking mode parameter)."""
    _send(f"CFG:{key}:{value}\n")


def set_mode(mode: str):
    """Switch mode: 'track' or 'pos'. Only updates state if serial is connected."""
    with _ser_lock:
        connected = _ser is not None and _ser.is_open
    if connected:
        cmd = "MODE:TRACK" if mode == "track" else "MODE:POS"
        _send(cmd + "\n")
        state.esp32_control_mode = mode  # Only update when command actually sent
    # If not connected, leave state unchanged so queue worker doesn't get confused


def _get_next_seq():
    global _seq_counter
    with _seq_lock:
        _seq_counter += 1
        return _seq_counter


def enqueue_move(target: str, val: float, is_absolute: bool = True):
    global _move_queue
    axis = target.upper().replace(' ', '')

    # Sync queued target to real position when queue is idle
    if _move_queue.empty():
        state.last_queued_target_m1 = state.esp32_pos_m1_mm
        state.last_queued_target_m2 = state.esp32_pos_m2_mm

    valid_axes = [a.strip() for a in axis.split(',') if a.strip() in ('M1', 'M2')]
    if not valid_axes:
        return False

    # M1,M2 simultaneous: single queue item → one "MOVE J M1,M2 <mm>" command
    if len(valid_axes) == 2:
        if is_absolute:
            target_abs = val
            priority = 10
        else:
            target_abs = state.last_queued_target_m1 + val
            priority = 20
        state.last_queued_target_m1 = target_abs
        state.last_queued_target_m2 = target_abs
        seq = _get_next_seq()
        try:
            _move_queue.put_nowait((priority, seq, 'M1,M2', target_abs))
        except queue.Full:
            pass  # Drop if queue is full (bounded queue)
        return True

    # Single axis
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
    try:
        _move_queue.put_nowait((priority, seq, a, target_abs))
    except queue.Full:
        pass
    return True


def move_mm(target: str, mm: float):
    """Absolute position move (enqueue)."""
    return enqueue_move(target, mm, is_absolute=True)


def move_relative_mm(target: str, delta: float):
    """Relative position move (enqueue)."""
    return enqueue_move(target, delta, is_absolute=False)


def _queue_worker():
    while True:
        try:
            priority, seq, axis, target_mm = _move_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        with _ser_lock:
            connected = _ser is not None and _ser.is_open
        if not connected:
            print("[esp32-queue] 연결되지 않음. 작업 스킵.")
            _move_queue.task_done()
            continue

        _abort_event.clear()

        # Auto-switch to POS mode
        if state.esp32_control_mode != "pos":
            _send("MODE:POS\n")
            state.esp32_control_mode = "pos"
            time.sleep(0.1)

        cmd = f"MOVE J {axis} {target_mm:.3f}\n"
        print(f"[esp32-queue] 전송: {cmd.strip()} (priority={priority}, seq={seq})")
        _send(cmd)

        dist = 0.0
        if 'M1' in axis:
            dist = max(dist, abs(target_mm - state.esp32_pos_m1_mm))
        if 'M2' in axis:
            dist = max(dist, abs(target_mm - state.esp32_pos_m2_mm))

        max_spd = state.esp32_max_speed_hz / max(state.esp32_steps_per_mm_m1, 1)
        duration_est = dist / max_spd if max_spd > 0 else 0
        timeout = max(2.0, duration_est * 3.0 + 2.0)
        timeout = min(8.0, timeout)

        DONE_THRESHOLD = 0.30

        start_time = time.time()
        time.sleep(0.05)

        while time.time() - start_time < timeout:
            if _abort_event.is_set():
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
    """Set current position as home (0mm)."""
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


def request_status():
    """Request immediate POS feedback."""
    _send("STATUS\n")


def send_mm_config(key: str, value):
    """Send position-control CFG parameter."""
    _send(f"CFG:{key}:{value}\n")


def start(port=None):
    global _thread, _queue_worker_thread
    connect(port)
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()
    _queue_worker_thread = threading.Thread(target=_queue_worker, daemon=True)
    _queue_worker_thread.start()


def stop_motors():
    """Abort active movement and flush the queue."""
    _abort_event.set()
    # Drain queue
    while not _move_queue.empty():
        try:
            _move_queue.get_nowait()
            _move_queue.task_done()
        except Exception:
            break
    # Sync queued target to current real position
    state.last_queued_target_m1 = state.esp32_pos_m1_mm
    state.last_queued_target_m2 = state.esp32_pos_m2_mm
    _send("S\n")
