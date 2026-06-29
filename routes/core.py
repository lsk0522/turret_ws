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



import threading
_joystick_lock = threading.Lock()

@bp.route('/joystick_dir')
def joystick_dir():
    # 미세조정을 위해 float로 받음 (script.js에서 -1.0 ~ 1.0 전송)
    x = float(request.args.get('x', 0))
    y = float(request.args.get('y', 0))
    seq = int(request.args.get('seq', 0))

    if seq > 0:
        # Lock을 얻기 전에 "가장 최근에 서버에 도착한 요청 번호"를 전역 변수에 기록
        current_latest = getattr(state, 'latest_received_seq', 0)
        if seq > current_latest:
            state.latest_received_seq = seq

    with _joystick_lock:
        if seq > 0:
            # 락을 얻고 나서 확인했을 때, 내 번호보다 더 높은 번호의 요청이 이미 도착해있다면 나는 과거 명령이므로 무시
            if seq < getattr(state, 'latest_received_seq', 0):
                return "STALE"
            
            last_seq = getattr(state, 'joystick_cmd_seq', 0)
            if seq <= last_seq:
                return "STALE"
            state.joystick_cmd_seq = seq

        import motor_esp32 as esp
        
        if state.esp32_control_mode != "pos":
            esp.set_mode("pos")
            
        if abs(x) < 0.001 and abs(y) < 0.001:
            # 조이스틱에서 손을 뗌 → 즉시 정지
            esp.stop_motors()
        else:
            # 순수 조그(Velocity) 제어 방식: 목표 위치를 보내는 대신 "속도 방향" 자체를 전송합니다.
            # ESP32 펌웨어에 새로 추가된 JOG 모드와 Watchdog(150ms)을 활용합니다.
            state.motor_moving = True
            esp._send(f"JOG {x:.3f} {y:.3f}\n")
            
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
                if mode == 'joystick':
                    esp.set_mode("pos")
                    # 트래킹 모드나 다른 동작 후 조이스틱 모드로 돌아올 때,
                    # 가상 타겟이 엉뚱한 곳에 남아있어 모터가 순간이동(스냅)하는 것을 방지합니다.
                    state.last_queued_target_m1 = state.esp32_pos_m1_deg
                    state.last_queued_target_m2 = state.esp32_pos_m2_deg
                else:
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
