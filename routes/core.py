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
    # 미세조정을 위해 float로 받음 (script.js에서 -1.0 ~ 1.0 전송)
    x = float(request.args.get('x', 0))
    y = float(request.args.get('y', 0))
    import motor_esp32 as esp
    
    if state.esp32_control_mode != "pos":
        esp.set_mode("pos")
        
    if x == 0 and y == 0:
        esp.stop_motors()
    else:
        # 가상 타겟 적분(Virtual Target Integration) 방식 적용!
        # 매 30ms마다 누적된 가상 타겟을 전진시킵니다.
        if not getattr(state, 'motor_moving', False):
            state.motor_moving = True
            # 중요: 조이스틱을 다시 움직일 때 가상 타겟을 '실제 모터 위치(esp32_pos)'로 리셋하지 않습니다!
            # 실제 위치는 통신 딜레이(최대 100ms)로 인해 과거의 위치일 수 있으며, 이로 인해 시작할 때 
            # 모터가 뒤로 튕기거나 멈칫하는 '딜레이'가 발생합니다.
            # 모터는 어차피 이전 가상 타겟 위치에 완벽히 정지해 있으므로, 그대로 이어서 적분하면 딜레이 0초로 즉각 반응합니다.

        # 속도 설정: 1.0 = 최대 속도 (mm/s)
        # 20.0 mm/s 는 약 1560Hz로 매우 적절한 최고 속도입니다.
        MAX_SPEED_DEG_S = 20.0 
        DT = 0.030 # script.js의 전송 주기 (30ms)로 즉각 반응!
        
        if x != 0:
            state.last_queued_target_m1 += (x * MAX_SPEED_DEG_S * DT)
            esp._send(f"MOVE J M1 {state.last_queued_target_m1:.3f}\n")
            
        if y != 0:
            state.last_queued_target_m2 += (y * MAX_SPEED_DEG_S * DT)
            esp._send(f"MOVE J M2 {state.last_queued_target_m2:.3f}\n")
        
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
