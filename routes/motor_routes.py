"""모터 제어 라우트 (ESP32 + Arduino + 펌웨어 업로드)."""
import subprocess
import time
from flask import Blueprint, request, jsonify
import state

bp = Blueprint('motor', __name__)

# ── 공통 상태 조회 ─────────────────────────────────────────
@bp.route('/motor_status')
def motor_status():
    tx, ty = state.point[0], state.point[1]
    frame = state.current_frame
    if frame is not None:
        frame_h = frame.shape[0]
        frame_w = frame.shape[1]
        center_x, center_y = frame_w // 2, frame_h // 2
    else:
        center_x, center_y = 320, 240
    ex, ey = tx - center_x, ty - center_y
    steps1 = int(state.esp32_pos_m1_deg * state.esp32_steps_per_deg_m1)
    steps2 = int(state.esp32_pos_m2_deg * state.esp32_steps_per_deg_m2)
    moving = (abs(state.esp32_speed_m1) > 0.1 or abs(state.esp32_speed_m2) > 0.1)

    return jsonify(
        connected=state.motor_connected,
        port=state.motor_port,
        target_x=tx,
        target_y=ty,
        error_x=ex,
        error_y=ey,
        steps_m1=steps1,
        steps_m2=steps2,
        moving=moving,
        timeout=False,
    )


@bp.route('/device_status')
def device_status():
    try:
        import serial.tools.list_ports as lp
        ports = [p.device for p in lp.comports()]
    except Exception:
        ports = []
    return jsonify(
        connected=state.motor_connected,
        port=state.motor_port,
        device_type=state.device_type,
        available_ports=ports,
    )


# ── ESP32 설정 조회/변경 ───────────────────────────────────
@bp.route('/esp32_deg_settings')
def esp32_deg_settings():
    return jsonify(
        control_mode=state.esp32_control_mode,
        steps_per_deg_m1=state.esp32_steps_per_deg_m1,
        steps_per_deg_m2=state.esp32_steps_per_deg_m2,
        max_speed_hz=state.esp32_max_speed_hz,
        accel_rate=state.esp32_accel_rate,
        dead_zone=state.motor_dead_zone,
        max_steps=state.motor_max_steps,
        steps_per_px=state.motor_steps_per_px,
        pulse_us=state.motor_pulse_us,
        m1_invert=state.motor_m1_invert,
        m2_invert=state.motor_m2_invert,
        cmd_timeout_ms=state.motor_cmd_timeout_ms,
    )


@bp.route('/set_esp32_deg_config')
def set_esp32_deg_config():
    import motor_esp32 as esp
    key   = request.args.get('key', '')
    value = request.args.get('value', '')
    _CFG = {
        'steps_per_deg_m1': ('esp32_steps_per_deg_m1', float, 'SPD1', lambda v: int(v * 10)),
        'steps_per_deg_m2': ('esp32_steps_per_deg_m2', float, 'SPD2', lambda v: int(v * 10)),
        'max_speed_hz':    ('esp32_max_speed_hz',    float, 'MSL',  int),
        'accel_rate':      ('esp32_accel_rate',      float, 'ACC',  lambda v: int(v * 10)),
        'steps_per_pix':   ('motor_steps_per_px',    float, 'SPX',  lambda v: int(v * 1000)),
        'steps_per_px':    ('motor_steps_per_px',    float, 'SPX',  lambda v: int(v * 1000)),
        'pulse_us':        ('motor_pulse_us',         int,   'PU',   int),
        'm1_invert':       ('motor_m1_invert',        lambda v: v.lower() == 'true', 'M1I', lambda v: 1 if v else 0),
        'm2_invert':       ('motor_m2_invert',        lambda v: v.lower() == 'true', 'M2I', lambda v: 1 if v else 0),
    }
    if key not in _CFG:
        return "UNKNOWN KEY", 400
    attr, cast, cfg_key, cfg_cast = _CFG[key]
    v = cast(value)
    setattr(state, attr, v)
    esp.send_config(cfg_key, cfg_cast(v))
    return "OK"


@bp.route('/motor_settings')
def motor_settings_get():
    return jsonify(
        dead_zone=state.motor_dead_zone,
        max_steps=state.motor_max_steps,
        steps_per_px=state.motor_steps_per_px,
        pulse_us=state.motor_pulse_us,
        m1_invert=state.motor_m1_invert,
        m2_invert=state.motor_m2_invert,
        cmd_timeout_ms=state.motor_cmd_timeout_ms,
    )


@bp.route('/set_motor_config')
def set_motor_config():
    import motor_esp32 as esp
    key   = request.args.get('key', '')
    value = request.args.get('value', '')
    _MAP = {
        'dead_zone':      ('motor_dead_zone',      int,   'DZ',  int),
        'max_steps':      ('motor_max_steps',       int,   'MS',  int),
        'steps_per_px':   ('motor_steps_per_px',   float, 'SP',  lambda v: int(v * 1000)),
        'pulse_us':       ('motor_pulse_us',        int,   'PU',  int),
        'm1_invert':      ('motor_m1_invert',       lambda v: v.lower() == 'true', 'M1I', lambda v: 1 if v else 0),
        'm2_invert':      ('motor_m2_invert',       lambda v: v.lower() == 'true', 'M2I', lambda v: 1 if v else 0),
        'cmd_timeout_ms': ('motor_cmd_timeout_ms',  int,   'TO',  int),
    }
    if key not in _MAP:
        return "UNKNOWN KEY", 400
    attr, cast, cfg_key, cfg_cast = _MAP[key]
    v = cast(value)
    setattr(state, attr, v)
    esp.send_config(cfg_key, cfg_cast(v))
    return "OK"


# ── ESP32 이동 명령 ────────────────────────────────────────
@bp.route('/esp32_move')
def esp32_move():
    import motor_esp32 as esp
    target = request.args.get('target', 'M1').upper()
    if target not in ('M1', 'M2', 'M1,M2'):
        return "INVALID TARGET", 400
    delta_str = request.args.get('delta')
    if delta_str is not None:
        try:
            ok = esp.move_relative_deg(target, float(delta_str))
        except ValueError:
            return "INVALID DELTA", 400
    else:
        try:
            ok = esp.move_deg(target, float(request.args.get('mm', 0)))
        except ValueError:
            return "INVALID MM", 400
    return "OK"


@bp.route('/esp32_sethome')
def esp32_sethome():
    import motor_esp32 as esp
    ok = esp.set_home()
    return ("OK" if ok else ("NOT_CONNECTED", 503))


@bp.route('/esp32_pos_status')
def esp32_pos_status():
    return jsonify(
        connected=state.motor_connected,
        control_mode=state.esp32_control_mode,
        pos_m1_deg=round(state.esp32_pos_m1_deg, 2),
        pos_m2_deg=round(state.esp32_pos_m2_deg, 2),
        speed_m1=round(state.esp32_speed_m1, 1),
        speed_m2=round(state.esp32_speed_m2, 1),
    )


@bp.route('/esp32_set_mode')
def esp32_set_mode():
    import motor_esp32 as esp
    mode = request.args.get('mode', 'track')
    if mode not in ('track', 'pos'):
        return "INVALID MODE", 400
    esp.set_mode(mode)
    return "OK"


@bp.route('/esp32_stop')
def esp32_stop():
    import motor_esp32 as esp
    esp.stop_motors()
    return "OK"

@bp.route('/release_motors')
def release_motors():
    import motor_esp32 as esp
    esp._send("REL\n")
    return "OK"


# ── Arduino 설정/명령 ──────────────────────────────────────
@bp.route('/arduino_motor_settings')
def arduino_motor_settings_get():
    return jsonify(
        steps_per_rev=state.arduino_steps_per_rev,
        m1_max_speed=state.arduino_m1_max_speed,
        m1_accel=state.arduino_m1_accel,
        m2_max_speed=state.arduino_m2_max_speed,
        m2_accel=state.arduino_m2_accel,
    )


@bp.route('/set_arduino_motor_config')
def set_arduino_motor_config():
    key   = request.args.get('key', '')
    value = request.args.get('value', '')
    _MAP = {
        'steps_per_rev': 'arduino_steps_per_rev',
        'm1_max_speed':  'arduino_m1_max_speed',
        'm1_accel':      'arduino_m1_accel',
        'm2_max_speed':  'arduino_m2_max_speed',
        'm2_accel':      'arduino_m2_accel',
    }
    if key not in _MAP:
        return "UNKNOWN KEY", 400
    setattr(state, _MAP[key], int(value))
    return "OK"


@bp.route('/arduino_motor_status')
def arduino_motor_status():
    return jsonify(
        connected=state.motor_connected,
        port=state.motor_port,
        pos_m1=state.arduino_pos_m1,
        pos_m2=state.arduino_pos_m2,
    )


@bp.route('/arduino_run')
def arduino_run():
    import motor_arduino as ard
    motor_id  = int(request.args.get('id',  1))
    degrees   = float(request.args.get('deg', 90))
    max_speed = int(request.args.get('spd', state.arduino_m1_max_speed))
    accel     = int(request.args.get('acc', state.arduino_m1_accel))
    ok = ard.run(motor_id, degrees, max_speed, accel)
    return ("OK" if ok else ("NOT_CONNECTED", 503))


@bp.route('/apply_arduino_cfg')
def apply_arduino_cfg():
    """파라미터 설정을 JSON으로 Arduino에 1회 전송 (Bug fix: Arduino 전용 state 사용)"""
    import motor_arduino as ard
    ok = ard.send_config(
        dead_zone     = state.motor_dead_zone,
        max_steps     = state.motor_max_steps,
        steps_per_px  = state.motor_steps_per_px,
        pulse_us      = state.motor_pulse_us,
        cmd_timeout_ms= state.motor_cmd_timeout_ms,
        m1_invert     = state.motor_m1_invert,
        m2_invert     = state.motor_m2_invert,
    )
    return ("OK" if ok else ("NOT_CONNECTED", 503))


@bp.route('/arduino_estop')
def arduino_estop():
    import motor_arduino as ard
    ok = ard.estop()
    return ("OK" if ok else ("NOT_CONNECTED", 503))


@bp.route('/arduino_home')
def arduino_home():
    import motor_arduino as ard
    motor_id = int(request.args.get('id', 1))
    ok = ard.home(motor_id)
    return ("OK" if ok else ("NOT_CONNECTED", 503))


# ── 펌웨어 업로드 ──────────────────────────────────────────
@bp.route('/upload_firmware', methods=['POST'])
def upload_firmware():
    import motor_esp32 as esp
    state.pause_reconnect = True
    esp.safe_disconnect()
    time.sleep(1)

    port = state.motor_port
    if not port:
        from serial_utils import find_port
        from motor_esp32 import _ESP32_VIDS
        port = find_port(preferred_vids=_ESP32_VIDS)
        if not port:
            state.pause_reconnect = False
            return jsonify(ok=False, log="연결된 ESP32 포트를 찾을 수 없습니다.")

    cmd = ["arduino-cli", "compile", "--upload", "-p", port,
           "--fqbn", "esp32:esp32:d32",
           "esp32_firmware/esp32_firmware.ino"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        success = (res.returncode == 0)
        log_output = res.stdout + "\n" + res.stderr
    except subprocess.TimeoutExpired:
        success, log_output = False, "업로드 시간이 초과되었습니다."
    except Exception as e:
        success, log_output = False, str(e)

    state.pause_reconnect = False
    esp.connect(port)
    return jsonify(ok=success, log=log_output)


@bp.route('/firmware_mode')
def firmware_mode():
    from flask import request, jsonify
    import motor_esp32
    import state
    enable = int(request.args.get('enable', 0))
    if enable == 1:
        motor_esp32.release_motors()
        motor_esp32.safe_disconnect()
        state.motor_connected = False
        print("[routes] Firmware upload mode: COM port released.")
        return jsonify(ok=True, mode="firmware_upload")
    else:
        motor_esp32.start()
        return jsonify(ok=True, mode="normal")

@bp.route('/firmware_status')
def firmware_status():
    expected = state.EXPECTED_FIRMWARE_VERSION
    actual   = state.firmware_version_actual
    match    = (actual == expected) if actual else True
    return jsonify(
        match=match,
        expected=expected,
        actual=actual if actual else expected
    )