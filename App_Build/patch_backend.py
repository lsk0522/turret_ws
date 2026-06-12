import paramiko
import os

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)

sftp = ssh.open_sftp()

def run(cmd):
    _, stdout, _ = ssh.exec_command(cmd)
    return stdout.read().decode().strip()

# ============================================================
# 1. detector.py 패치: LEARN_ZONE을 동적으로 변경 가능하게,
#    학습 샘플 수(n_samples) 추가
# ============================================================

detector_patch = r'''
import state

# LEARN_ZONE 을 runtime 에 변경할 수 있도록 함수 제공
def set_learn_zone(x, y, w, h):
    """ROI 박스를 동적으로 설정 (UI 드래그 입력)"""
    _orb.learn_zone = (int(x), int(y), int(w), int(h))

def get_learn_zone():
    return getattr(_orb, 'learn_zone', (170, 90, 300, 300))

def start_learning(n_samples=20):
    """지문인식 스타일: 호출할 때마다 n_samples 만큼 추가 학습"""
    _orb.start_learning(n_samples=n_samples)
    _kalman.reset()
    state.ball = None
    state.ball_lost = False
    state.learning_progress = 0
'''

# ============================================================
# 2. routes.py 에 새 엔드포인트 3개 추가
# ============================================================

new_routes = r'''
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
'''

# ── routes.py 읽기 → 끝에 새 라우트 삽입 ────────────────
routes_src = run("cat /home/pi30306/turret_ws/routes.py")

# 이미 추가됐는지 확인
if '/set_learn_zone' in routes_src:
    print("routes.py: set_learn_zone 이미 있음 → 스킵")
else:
    # 마지막 닫는 중괄호(setup_routes 함수 끝) 바로 앞에 삽입
    # 마지막 줄이 비어 있을 수 있으므로 안전하게 append
    new_routes_content = routes_src.rstrip() + "\n" + new_routes + "\n"
    with sftp.open('/home/pi30306/turret_ws/routes.py', 'w') as f:
        f.write(new_routes_content)
    print("✅ routes.py 업데이트 완료")

# ── detector.py: set_learn_zone / get_learn_zone / start_learning 패치 ──
detector_src = run("cat /home/pi30306/turret_ws/detector.py")

if 'def set_learn_zone' in detector_src:
    print("detector.py: set_learn_zone 이미 있음 → 스킵")
else:
    # ORBTracker.start_learning 에 n_samples 파라미터 추가
    detector_src = detector_src.replace(
        'def start_learning(self):',
        'def start_learning(self, n_samples=20):'
    ).replace(
        'self._buf      = []\n        self.progress  = 0\n        self.N_SAMPLES',
        'self._buf      = []\n        self.progress  = 0\n        self.N_SAMPLES = n_samples\n        _N_SAMPLES'
    )
    # N_SAMPLES 하드코딩 → 인스턴스 속성 사용
    # 간단하게: 클래스 레벨 N_SAMPLES=20 → self.N_SAMPLES
    detector_src = detector_src.replace(
        'N_SAMPLES = 20',
        'N_SAMPLES = n_samples'
    )

    # learn_zone 동적 접근 (process_frame 에서 LEARN_ZONE 상수 대신 self.learn_zone)
    detector_src = detector_src.replace(
        'LEARN_ZONE = (170, 90, 300, 300)',
        '_DEFAULT_LEARN_ZONE = (170, 90, 300, 300)'
    )
    detector_src = detector_src.replace(
        'x, y, w, h = LEARN_ZONE',
        'x, y, w, h = getattr(self, "learn_zone", _DEFAULT_LEARN_ZONE)'
    )

    # 모듈 레벨 헬퍼 추가 (파일 끝에)
    detector_src = detector_src.rstrip() + "\n\n" + \
        "def set_learn_zone(x, y, w, h):\n" \
        "    _orb.learn_zone = (int(x), int(y), int(w), int(h))\n\n" \
        "def get_learn_zone():\n" \
        "    return getattr(_orb, 'learn_zone', _DEFAULT_LEARN_ZONE)\n\n" \
        "def start_learning(n_samples=20):\n" \
        "    _orb.start_learning(n_samples=n_samples)\n" \
        "    _kalman.reset()\n" \
        "    state.ball = None\n" \
        "    state.ball_lost = False\n" \
        "    state.learning_progress = 0\n"

    with sftp.open('/home/pi30306/turret_ws/detector.py', 'w') as f:
        f.write(detector_src)
    print("✅ detector.py 업데이트 완료")

sftp.close()
ssh.close()
print("\n✅ 백엔드 패치 완료!")
