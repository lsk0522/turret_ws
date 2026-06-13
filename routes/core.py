"""
핵심 라우트 — index, video, click, pos, capture, flip, settings, set_speed,
             joystick_dir, set_input_mode, set_device_type, reconnect, available_ports
"""
from flask import Blueprint, Response, request, jsonify, render_template
import state

bp = Blueprint('core', __name__)


@bp.route('/')
def index():
    return render_template("index.html")


@bp.route('/video')
def video():
    from camera import gen_frames
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@bp.route('/click')
def click():
    try:
        x = int(float(request.args.get('x', 320)))
        y = int(float(request.args.get('y', 240)))
    except (TypeError, ValueError):
        return "INVALID", 400
    state.point = [x, y]
    state.last_point = (x, y)
    if state.esp32_control_mode != "track":
        import motor_esp32 as esp
        esp.set_mode("track")
    return "OK"


@bp.route('/pos')
def pos():
    return jsonify(x=state.point[0], y=state.point[1])


@bp.route('/capture')
def capture():
    from capture import save_capture
    save_capture()
    return "OK"


@bp.route('/flip')
def flip():
    state.flip_enabled = not state.flip_enabled
    return "OK"


@bp.route('/settings')
def settings():
    return jsonify(
        speed=state.speed,
        control_mode=state.control_mode,
        tracking_mode=state.tracking_mode,
        device_type=state.device_type,
        input_mode=state.input_mode,
    )


@bp.route('/set_speed')
def set_speed():
    try:
        speed = int(request.args.get("speed", state.speed))
    except (TypeError, ValueError):
        return "INVALID", 400
    state.speed = speed
    _sync_speed_to_esp32(speed)
    return "OK"


def _sync_speed_to_esp32(speed: int):
    """speed 1~20 값을 ESP32 MSL로 즉시 동기화."""
    hz = speed * 150   # 1=150Hz(매우 느림) ~ 20=3000Hz(빠름)
    state.esp32_max_speed_hz = hz
    if state.device_type == "esp32" and state.motor_connected:
        import motor_esp32 as esp
        esp.send_config("MSL", hz)


@bp.route('/joystick_dir')
def joystick_dir():
    import motor_esp32 as esp
    try:
        x = int(request.args.get('x', 0))
        y = int(request.args.get('y', 0))
    except (TypeError, ValueError):
        return "INVALID", 400
    if x == 0 and y == 0:
        esp.stop_motors()
        return "OK"
    # dist = 10000mm: 사실상 무한 이동 — 조이스틱을 놓을 때 stop_motors()로 멈춤
    # 실제 속도는 ESP32의 MAX_SPEED_LIMIT(MSL)이 제어 → 감도 슬라이더에 연동
    dist = 10000.0
    if x != 0:
        esp.enqueue_move('M1', x * dist, is_absolute=False)
    if y != 0:
        esp.enqueue_move('M2', y * dist, is_absolute=False)
    return "OK"


@bp.route('/set_input_mode')
def set_input_mode():
    mode = request.args.get('mode', 'joystick')
    if mode in ('joystick', 'pointer', 'auto'):
        state.input_mode = mode
        if mode == 'auto':
            state.control_mode = 'auto'
        else:
            state.control_mode = 'manual'
            import motor_esp32 as esp
            if state.motor_connected:
                esp.set_mode("track")
    return "OK"


@bp.route('/set_device_type')
def set_device_type():
    dtype = request.args.get('type', 'esp32')
    if dtype in ('esp32', 'arduino'):
        state.device_type = dtype
    return "OK"


@bp.route('/reconnect_esp32')
def reconnect_esp32():
    import motor_esp32 as esp
    port = request.args.get('port', None)
    try:
        esp.safe_disconnect()
        esp.connect(port)
        if state.motor_connected:
            return jsonify(ok=True, port=state.motor_port)
        return jsonify(ok=False, port=""), 503
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


@bp.route('/available_ports')
def available_ports():
    try:
        import serial.tools.list_ports
        ports = [{"device": p.device, "description": p.description}
                 for p in serial.tools.list_ports.comports()]
    except Exception:
        ports = []
    return jsonify(ports=ports, connected=state.motor_connected,
                   current_port=state.motor_port)
