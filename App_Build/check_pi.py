import paramiko
import os

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)

def run(cmd):
    _, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err

print("=" * 60)
print("📁 turret_ws 파일 목록")
print("=" * 60)
out, _ = run("ls -lh /home/pi30306/turret_ws/")
print(out)

print("\n" + "=" * 60)
print("📁 static 파일 목록")
print("=" * 60)
out, _ = run("ls -lh /home/pi30306/turret_ws/static/")
print(out)

print("\n" + "=" * 60)
print("📁 templates 파일 목록")
print("=" * 60)
out, _ = run("ls -lh /home/pi30306/turret_ws/templates/")
print(out)

print("\n" + "=" * 60)
print("🔌 USB/Serial 포트 목록 (ESP32 / Arduino 연결 확인)")
print("=" * 60)
out, _ = run("ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo '연결된 시리얼 포트 없음'")
print(out)

print("\n" + "=" * 60)
print("🔌 USB 연결 장치 목록")
print("=" * 60)
out, _ = run("lsusb")
print(out)

print("\n" + "=" * 60)
print("📦 설치된 Python 패키지")
print("=" * 60)
out, _ = run("cd /home/pi30306/turret_ws && source turret_venv/bin/activate 2>/dev/null; pip list 2>/dev/null | grep -iE 'flask|cv2|opencv|serial|paramiko|numpy'")
print(out)

print("\n" + "=" * 60)
print("📄 state.py 내용")
print("=" * 60)
out, _ = run("cat /home/pi30306/turret_ws/state.py")
print(out)

print("\n" + "=" * 60)
print("📄 detector.py 존재 여부")
print("=" * 60)
out, _ = run("ls -lh /home/pi30306/turret_ws/detector.py /home/pi30306/turret_ws/tracker.py 2>/dev/null || echo '없음'")
print(out)

print("\n" + "=" * 60)
print("📄 최근 수정된 파일 (상위 10개)")
print("=" * 60)
out, _ = run("find /home/pi30306/turret_ws -name '*.py' -o -name '*.html' -o -name '*.css' -o -name '*.js' | xargs ls -lt 2>/dev/null | head -15")
print(out)

ssh.close()
print("\n✅ 확인 완료!")
