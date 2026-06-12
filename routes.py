from flask import (
    Response,
    request,
    jsonify,
    render_template,
    send_from_directory
)
import os
import base64
import cv2

import state

from capture import save_capture
from camera import gen_frames, gen_debug_frames


def setup_routes(app):

    @app.route('/')
    def index():

        return render_template("index.html")

    @app.route('/video')
    def video():

        return Response(
            gen_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    @app.route('/video_debug')
    def video_debug():
        return Response(
            gen_debug_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    @app.route('/click')
    def click():

        x = int(float(request.args.get('x')))
        y = int(float(request.args.get('y')))

        state.point[0] = x
        state.point[1] = y

        state.last_point = (x, y)

        # Force track mode if we are moving via click/joystick
        if state.esp32_control_mode != "track":
            import motor_esp32 as esp
            esp.set_mode("track")

        return "OK"

    @app.route('/pos')
    def pos():

        return jsonify(
            x=state.point[0],
            y=state.point[1]
        )

    @app.route('/capture')
    def capture():

        save_capture()

        return "OK"

    @app.route('/flip')
    def flip():

        state.flip_enabled = not state.flip_enabled

        return "OK"

    # -------------------------
    # Camera selection & settings
    # -------------------------

    @app.route('/list_cameras')
    def list_cameras():
        """Probe and return list of available camera indices"""
        from camera import list_cameras as _list
        cameras = _list(max_test=6)
        return jsonify(cameras=cameras)

    @app.route('/set_camera')
    def set_camera():
        """Switch to a different camera index"""
        from camera import set_camera_index
        index = int(request.args.get('index', 0))
        ok = set_camera_index(index)
        return jsonify(ok=ok, index=index)

    @app.route('/camera_settings')
    def camera_settings():
        """Return current camera configuration"""
        from camera import _camera_index, FRAME_W, FRAME_H, FRAME_FPS, _is_dummy, RESOLUTION_PRESETS, FPS_PRESETS
        return jsonify(
            index=_camera_index,
            width=FRAME_W,
            height=FRAME_H,
            fps=FRAME_FPS,
            is_dummy=_is_dummy,
            flip=state.flip_enabled,
            res_presets=RESOLUTION_PRESETS,
            fps_presets=FPS_PRESETS
        )

    @app.route('/set_camera_resolution')
    def set_camera_resolution():
        from camera import set_camera_resolution
        width = int(request.args.get('w', 640))
        height = int(request.args.get('h', 480))
        ok = set_camera_resolution(width, height)
        return jsonify(ok=ok, w=width, h=height)

    @app.route('/set_camera_fps')
    def set_camera_fps():
        from camera import set_camera_fps
        fps = int(request.args.get('fps', 30))
        ok = set_camera_fps(fps)
        return jsonify(ok=ok, fps=fps)





    # -------------------------
    # 속도 설정
    # -------------------------

    @app.route('/set_speed')
    def set_speed():
        speed = int(request.args.get("speed"))
        state.speed = speed
        return "OK"

    @app.route('/joystick_dir')
    def joystick_dir():
        """조이스틱 8방향 제어 (무한 이동 후 S 명령으로 정지)"""
        import motor_esp32 as esp
        x = int(request.args.get('x', 0))
        y = int(request.args.get('y', 0))
        
        if x == 0 and y == 0:
            esp.stop_motors()
            return "OK"
            
        esp.stop_motors()
        
        # 방향에 맞춰 큰 값을 큐에 넣어서 계속 회전하게 함
        dist = 10000.0
        if x != 0:
            esp.enqueue_move('M1', x * dist, is_absolute=False)
        if y != 0:
            esp.enqueue_move('M2', y * dist, is_absolute=False)
            
        return "OK"

    # -------------------------
    # 조작 모드 설정
    # -------------------------

    @app.route('/set_mode')
    def set_mode():

        mode = request.args.get("mode")

        state.control_mode = mode

        return "OK"

    # -------------------------
    # 현재 설정 조회
    # -------------------------

    @app.route('/settings')
    def settings():

        return jsonify(
            speed=state.speed,
            control_mode=state.control_mode,
            tracking_mode=state.tracking_mode,
            device_type=state.device_type,
            input_mode=state.input_mode,
        )

    @app.route('/set_input_mode')
    def set_input_mode():
        """Set the input control mode: joystick | pointer | auto"""
        mode = request.args.get('mode', 'joystick')
        if mode in ('joystick', 'pointer', 'auto'):
            state.input_mode = mode
            # Sync control_mode for backend tracking logic
            if mode == 'auto':
                state.control_mode = 'auto'
            else:
                state.control_mode = 'manual'
            
            # Switch motor to track mode for visual targeting
            import motor_esp32 as esp
            esp.set_mode("track")
        return "OK"

    @app.route('/set_device_type')
    def set_device_type():
        dtype = request.args.get('type', 'esp32')
        if dtype in ('esp32', 'arduino'):
            state.device_type = dtype
        return "OK"


    # -------------------------
    # ESP32 수동 재연결
    # -------------------------

    @app.route('/reconnect_esp32')
    def reconnect_esp32():
        """지정한 포트(또는 자동 감지)로 ESP32 재연결"""
        import motor_esp32 as esp
        port = request.args.get('port', None)   # 예: ?port=COM6
        try:
            # 기존 연결 해제
            if esp._ser and esp._ser.is_open:
                esp._ser.close()
            esp._ser = None
            state.motor_connected = False
            # 재연결 시도
            esp.connect(port)
            if state.motor_connected:
                return jsonify(ok=True, port=state.motor_port)
            else:
                return jsonify(ok=False, port=""), 503
        except Exception as e:
            return jsonify(ok=False, error=str(e)), 500

    @app.route('/available_ports')
    def available_ports():
        """현재 시스템에 연결된 COM 포트 목록 반환"""
        try:
            import serial.tools.list_ports
            ports = [
                {"device": p.device, "description": p.description}
                for p in serial.tools.list_ports.comports()
            ]
        except Exception:
            ports = []
        return jsonify(ports=ports, connected=state.motor_connected, current_port=state.motor_port)



    @app.route('/captures')
    def list_captures():
        folder = "picture"
        if not os.path.exists(folder):
            return jsonify([])
        try:
            files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            files.sort(key=lambda x: os.path.getmtime(os.path.join(folder, x)), reverse=True)
            return jsonify(files)
        except Exception as e:
            return jsonify([])

    @app.route('/picture/<path:filename>')
    def get_picture(filename):
        return send_from_directory('picture', filename)

    # -------------------------
    # 추적 대상 검출 상태 조회
    # -------------------------

    @app.route('/ball')
    def ball():
        if state.ball is None:
            return jsonify(detected=False)
        return jsonify(detected=True, lost=state.ball_lost, **state.ball)

    @app.route('/tracking_status')
    def tracking_status():
        """Return AI tracking locked/searching status for header indicator"""
        locked = (
            state.ball is not None and
            not state.ball_lost and
            state.tracking_mode == "custom"
        )
        return jsonify(
            locked=locked,
            detected=(state.ball is not None),
            tracking_mode=state.tracking_mode,
            control_mode=state.control_mode,
        )

    # -------------------------
    # ORB 학습 시작 / 진행률 / 초기화
    # -------------------------

    @app.route('/start_learning')
    def start_learning():
        import detector as det
        det.start_learning()
        state.tracking_mode = "custom"
        return "OK"

    @app.route('/learning_progress')
    def learning_progress():
        import detector as det
        prog = det.get_learning_progress()
        # 학습 완료 스냅샷: 학습 영역 기준 썸네일
        thumb = None
        if prog == 100 and state.current_frame is not None:
            x, y, w, h = det.get_learn_zone()
            img_h, img_w = state.current_frame.shape[:2]
            # 안전장치: 이미지 범위 밖으로 삐져나가지 않도록 제한
            x1 = max(0, min(img_w - 1, x))
            y1 = max(0, min(img_h - 1, y))
            x2 = max(0, min(img_w, x + w))
            y2 = max(0, min(img_h, y + h))
            
            if x2 > x1 and y2 > y1:
                roi = state.current_frame[y1:y2, x1:x2]
                
                # 썸네일을 파일로 영구 저장
                os.makedirs("learning_data", exist_ok=True)
                cv2.imwrite("learning_data/target_thumbnail.jpg", roi)
                
                _, buf = cv2.imencode('.jpg', roi, [cv2.IMWRITE_JPEG_QUALITY, 82])
                thumb = "data:image/jpeg;base64," + base64.b64encode(buf).decode()
        return jsonify(progress=prog, done=(prog == 100), thumbnail=thumb, failed=state.learning_failed)

    @app.route('/target_thumbnail')
    def target_thumbnail():
        """영구 저장된 학습 대상 썸네일 서빙"""
        return send_from_directory('learning_data', 'target_thumbnail.jpg')

    @app.route('/clear_target')
    def clear_target():
        import detector as det
        det.reset_tracker()
        state.tracking_mode = "none"
        state.ball = None
        state.learning_progress = 0
        
        # 저장된 썸네일 파일 삭제
        thumb_path = os.path.join("learning_data", "target_thumbnail.jpg")
        if os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass
        return "OK"

    # ─────────────────────────────────────────
    # Arduino Uno 스텝모터 파라미터 조회 / 변경
    # ─────────────────────────────────────────

    @app.route('/arduino_motor_settings')
    def arduino_motor_settings_get():
        return jsonify(
            steps_per_rev=state.arduino_steps_per_rev,
            m1_max_speed=state.arduino_m1_max_speed,
            m1_accel=state.arduino_m1_accel,
            m2_max_speed=state.arduino_m2_max_speed,
            m2_accel=state.arduino_m2_accel,
        )

    @app.route('/set_arduino_motor_config')
    def set_arduino_motor_config():
        key   = request.args.get('key', '')
        value = request.args.get('value', '')
        if   key == 'steps_per_rev': state.arduino_steps_per_rev = int(value)
        elif key == 'm1_max_speed':  state.arduino_m1_max_speed  = int(value)
        elif key == 'm1_accel':      state.arduino_m1_accel      = int(value)
        elif key == 'm2_max_speed':  state.arduino_m2_max_speed  = int(value)
        elif key == 'm2_accel':      state.arduino_m2_accel      = int(value)
        else: return "UNKNOWN KEY", 400
        return "OK"

    # ─────────────────────────────────────────
    # Arduino Uno 실시간 모터 위치 피드백
    # ─────────────────────────────────────────

    @app.route('/arduino_motor_status')
    def arduino_motor_status():
        return jsonify(
            connected=state.motor_connected,
            port=state.motor_port,
            pos_m1=state.arduino_pos_m1,
            pos_m2=state.arduino_pos_m2,
        )

    # ─────────────────────────────────────────
    # Arduino Uno 모터 명령 (단발 JSON 전송)
    # ─────────────────────────────────────────

    @app.route('/arduino_run')
    def arduino_run():
        import motor_arduino as ard
        motor_id  = int(request.args.get('id',  1))
        degrees   = float(request.args.get('deg', 90))
        max_speed = int(request.args.get('spd',  state.arduino_m1_max_speed))
        accel     = int(request.args.get('acc',  state.arduino_m1_accel))
        ok = ard.run(motor_id, degrees, max_speed, accel)
        return ("OK" if ok else ("NOT_CONNECTED", 503))

    @app.route('/apply_arduino_cfg')
    def apply_arduino_cfg():
        """파라미터 설정을 JSON으로 Arduino 시리얼 포트에 1회 전송"""
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

    @app.route('/arduino_estop')
    def arduino_estop():
        """비상 정지 — 두 모터 즉시 STOP"""
        import motor_arduino as ard
        ok = ard.estop()
        return ("OK" if ok else ("NOT_CONNECTED", 503))

    @app.route('/arduino_home')
    def arduino_home():
        import motor_arduino as ard
        motor_id = int(request.args.get('id', 1))
        ok = ard.home(motor_id)
        return ("OK" if ok else ("NOT_CONNECTED", 503))

    # -------------------------
    # 모터 실시간 상태 조회
    # -------------------------

    @app.route('/motor_status')
    def motor_status():
        return jsonify(
            connected=state.motor_connected,
            port=state.motor_port,
            target_x=state.motor_target_x,
            target_y=state.motor_target_y,
            error_x=state.motor_error_x,
            error_y=state.motor_error_y,
            steps_m1=state.motor_steps_m1,
            steps_m2=state.motor_steps_m2,
            moving=state.motor_moving,
            timeout=state.motor_timeout,
            stopped=state.motor_stopped,
        )

    # -------------------------
    # 모터 설정값 조회
    # -------------------------

    @app.route('/motor_settings')
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

    # -------------------------
    # 모터 설정값 변경 (Pi 상태 + ESP32 CFG 동기화)
    # -------------------------

    @app.route('/set_motor_config')
    def set_motor_config():
        import motor as mot
        key   = request.args.get('key', '')
        value = request.args.get('value', '')

        if key == 'dead_zone':
            v = int(value)
            state.motor_dead_zone = v
            mot.send_config('DZ', v)
        elif key == 'max_steps':
            v = int(value)
            state.motor_max_steps = v
            mot.send_config('MS', v)
        elif key == 'steps_per_px':
            v = float(value)
            state.motor_steps_per_px = v
            mot.send_config('SP', int(v * 1000))
        elif key == 'pulse_us':
            v = int(value)
            state.motor_pulse_us = v
            mot.send_config('PU', v)
        elif key == 'm1_invert':
            v = value.lower() == 'true'
            state.motor_m1_invert = v
            mot.send_config('M1I', 1 if v else 0)
        elif key == 'm2_invert':
            v = value.lower() == 'true'
            state.motor_m2_invert = v
            mot.send_config('M2I', 1 if v else 0)
        elif key == 'cmd_timeout_ms':
            v = int(value)
            state.motor_cmd_timeout_ms = v
            mot.send_config('TO', v)
        else:
            return "UNKNOWN KEY", 400

        return "OK"

    # ─────────────────────────────────────────
    # ROI 학습 영역 설정 (드래그 입력)
    # ─────────────────────────────────────────

    @app.route('/set_learn_zone')
    def set_learn_zone():
        import detector as det
        x = int(float(request.args.get('x', 170)))
        y = int(float(request.args.get('y', 90)))
        w = int(float(request.args.get('w', 300)))
        h = int(float(request.args.get('h', 300)))
        det.set_learn_zone(x, y, w, h)
        return jsonify(x=x, y=y, w=w, h=h)

    @app.route('/get_learn_zone')
    def get_learn_zone():
        import detector as det
        x, y, w, h = det.get_learn_zone()
        return jsonify(x=x, y=y, w=w, h=h)

    # ─────────────────────────────────────────
    # 추가 학습 (지문인식 스타일 반복)
    # ─────────────────────────────────────────

    @app.route('/add_learning')
    def add_learning():
        """기존 학습 데이터에 n_samples 추가"""
        import detector as det
        n = int(request.args.get('n', 20))
        det.start_learning(n_samples=n)
        return "OK"

    # ─────────────────────────────────────────
    # 연결 상태 통합 엔드포인트
    # ─────────────────────────────────────────

    @app.route('/device_status')
    def device_status():
        """ESP32 / Arduino 연결 여부 + 현재 파라미터 한 번에 반환"""
        import serial.tools.list_ports as lp
        ports = [p.device for p in lp.comports()]
        return jsonify(
            connected=state.motor_connected,
            port=state.motor_port,
            device_type=state.device_type,
            available_ports=ports,
            params=dict(
                dead_zone=state.motor_dead_zone,
                max_steps=state.motor_max_steps,
                steps_per_px=state.motor_steps_per_px,
                pulse_us=state.motor_pulse_us,
                m1_invert=state.motor_m1_invert,
                m2_invert=state.motor_m2_invert,
                cmd_timeout_ms=state.motor_cmd_timeout_ms,
            )
        )

    # ─────────────────────────────────────────
    # ESP32 mm 위치 제어 — 파라미터 조회
    # ─────────────────────────────────────────

    @app.route('/esp32_mm_settings')
    def esp32_mm_settings():
        """ESP32 mm 위치 제어 파라미터 전체 조회"""
        return jsonify(
            control_mode=state.esp32_control_mode,
            steps_per_mm_m1=state.esp32_steps_per_mm_m1,
            steps_per_mm_m2=state.esp32_steps_per_mm_m2,
            max_speed_hz=state.esp32_max_speed_hz,
            accel_rate=state.esp32_accel_rate,
            # 추적 모드 파라미터도 함께 반환
            dead_zone=state.motor_dead_zone,
            max_steps=state.motor_max_steps,
            steps_per_px=state.motor_steps_per_px,
            pulse_us=state.motor_pulse_us,
            m1_invert=state.motor_m1_invert,
            m2_invert=state.motor_m2_invert,
            cmd_timeout_ms=state.motor_cmd_timeout_ms,
        )

    # ─────────────────────────────────────────
    # ESP32 mm 위치 제어 — 파라미터 변경
    # ─────────────────────────────────────────

    @app.route('/set_esp32_mm_config')
    def set_esp32_mm_config():
        """
        ESP32 mm 위치 제어 파라미터 변경 및 ESP32 동기화
        ?key=steps_per_mm_m1&value=78.0
        """
        import motor_esp32 as esp
        key   = request.args.get('key', '')
        value = request.args.get('value', '')

        if key == 'steps_per_mm_m1':
            v = float(value)
            state.esp32_steps_per_mm_m1 = v
            # ESP32 CFG:SPM1:<val×10> 형태로 전송
            esp.send_mm_config('SPM1', int(v * 10))
        elif key == 'steps_per_mm_m2':
            v = float(value)
            state.esp32_steps_per_mm_m2 = v
            esp.send_mm_config('SPM2', int(v * 10))
        elif key == 'max_speed_hz':
            v = float(value)
            state.esp32_max_speed_hz = v
            esp.send_mm_config('MSL', int(v))
        elif key == 'accel_rate':
            v = float(value)
            state.esp32_accel_rate = v
            # CFG:ACC:<val×10> 형태
            esp.send_mm_config('ACC', int(v * 10))
        elif key == 'pulse_us':
            v = int(value)
            state.motor_pulse_us = v
            esp.send_mm_config('PU', v)
        elif key == 'm1_invert':
            v = value.lower() == 'true'
            state.motor_m1_invert = v
            esp.send_mm_config('M1I', 1 if v else 0)
        elif key == 'm2_invert':
            v = value.lower() == 'true'
            state.motor_m2_invert = v
            esp.send_mm_config('M2I', 1 if v else 0)
        else:
            return "UNKNOWN KEY", 400

        return "OK"

    # ─────────────────────────────────────────
    # ESP32 mm 이동 명령
    # ─────────────────────────────────────────

    @app.route('/esp32_move')
    def esp32_move():
        """
        절대 또는 상대 위치 이동 명령
        절대: ?target=M1&mm=50.0  또는  ?target=M1,M2&mm=30.0
        상대: ?target=M1&delta=10.0
        """
        import motor_esp32 as esp
        target = request.args.get('target', 'M1').upper()
        if target not in ('M1', 'M2', 'M1,M2'):
            return "INVALID TARGET", 400

        delta_str = request.args.get('delta')
        if delta_str is not None:
            try:
                delta = float(delta_str)
            except ValueError:
                return "INVALID DELTA", 400
            ok = esp.move_relative_mm(target, delta)
        else:
            try:
                mm = float(request.args.get('mm', 0))
            except ValueError:
                return "INVALID MM", 400
            ok = esp.move_mm(target, mm)

        return ("OK" if ok else ("NOT_CONNECTED", 503))

    # ─────────────────────────────────────────
    # ESP32 원점 설정
    # ─────────────────────────────────────────

    @app.route('/esp32_sethome')
    def esp32_sethome():
        """현재 위치를 원점(0mm)으로 설정"""
        import motor_esp32 as esp
        ok = esp.set_home()
        return ("OK" if ok else ("NOT_CONNECTED", 503))

    # ─────────────────────────────────────────
    # ESP32 실시간 mm 위치 피드백
    # ─────────────────────────────────────────

    @app.route('/esp32_pos_status')
    def esp32_pos_status():
        """M1/M2 현재 위치(mm) 및 속도(Hz) 실시간 조회"""
        return jsonify(
            connected=state.motor_connected,
            control_mode=state.esp32_control_mode,
            pos_m1_mm=round(state.esp32_pos_m1_mm, 2),
            pos_m2_mm=round(state.esp32_pos_m2_mm, 2),
            speed_m1=round(state.esp32_speed_m1, 1),
            speed_m2=round(state.esp32_speed_m2, 1),
        )

    # ─────────────────────────────────────────
    # ESP32 모드 전환 (추적 ↔ 위치 제어)
    # ─────────────────────────────────────────

    @app.route('/esp32_set_mode')
    def esp32_set_mode():
        """
        ESP32 제어 모드 전환
        ?mode=track  또는  ?mode=pos
        """
        import motor_esp32 as esp
        mode = request.args.get('mode', 'track')
        if mode not in ('track', 'pos'):
            return "INVALID MODE", 400
        esp.set_mode(mode)
        return "OK"

    # ─────────────────────────────────────────
    # ESP32 즉시 정지
    # ─────────────────────────────────────────

    @app.route('/esp32_stop')
    def esp32_stop():
        """모든 모터 즉시 정지"""
        import motor_esp32 as esp
        esp.stop_motors()
        return "OK"


