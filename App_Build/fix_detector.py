import paramiko

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)
sftp = ssh.open_sftp()

def run(cmd):
    _, stdout, _ = ssh.exec_command(cmd)
    return stdout.read().decode()

src = run("cat /home/pi30306/turret_ws/detector.py")

# ── 수정 1: ORBTracker.__init__ 에 learn_zone 속성 추가 ────────
# __init__ 안에서 self.active = False 바로 다음에 추가
OLD_INIT_END = "        self.active    = False\n        self.learning  = False"
NEW_INIT_END = (
    "        self.active    = False\n"
    "        self.learning  = False\n"
    "        self.learn_zone: tuple[int,int,int,int] = (170, 90, 300, 300)  # (x,y,w,h) — ROI"
)

if "self.learn_zone" not in src:
    src = src.replace(OLD_INIT_END, NEW_INIT_END, 1)
    print("✅ ORBTracker.__init__ 에 learn_zone 추가")
else:
    print("ℹ️  learn_zone 이미 __init__ 에 있음")

# ── 수정 2: process_frame 안에서 LEARN_ZONE 상수 → self.learn_zone 사용 ──
src = src.replace(
    "x, y, w, h = getattr(self, \"learn_zone\", _DEFAULT_LEARN_ZONE)",
    "x, y, w, h = self.learn_zone"
)
# 혹시 상수를 직접 쓰는 경우도 처리
src = src.replace(
    "x, y, w, h = LEARN_ZONE",
    "x, y, w, h = self.learn_zone"
)
print("✅ process_frame ROI 소스 → self.learn_zone")

# ── 수정 3: 모듈 레벨 start_learning 중복 제거 ─────────────────
# 두 번째(마지막) 모듈 레벨 start_learning(n_samples=20) 만 남기고
# 첫 번째 (n_samples 없는) 버전 제거

OLD_FIRST_START = (
    "def start_learning():\n"
    "    _orb.start_learning()\n"
    "    _kalman.reset()\n"
    "    state.ball = None\n"
    "    state.ball_lost = False\n"
    "    state.learning_progress = 0"
)

if OLD_FIRST_START in src:
    src = src.replace(OLD_FIRST_START, "", 1)
    # 빈 줄 연속 정리
    import re
    src = re.sub(r'\n{3,}', '\n\n', src)
    print("✅ 중복 start_learning() 제거 완료")
else:
    print("ℹ️  중복 start_learning() 없음 (이미 수정됨)")

# ── 수정 4: set_learn_zone 모듈 함수에서 _orb.learn_zone 직접 할당 가능 확인 ──
# (이제 __init__ 에 선언됐으므로 Pylance 오류 없음)

with sftp.open('/home/pi30306/turret_ws/detector.py', 'w') as f:
    f.write(src)

sftp.close()
ssh.close()
print("\n🎉 detector.py 오류 수정 완료!")
