import paramiko
import os

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"
PI_PATH = "/home/pi30306/turret_ws"

LOCAL_BASE = os.path.join(os.path.dirname(__file__), "turret_ws")

files = [
    ("routes.py",              f"{PI_PATH}/routes.py"),
    ("templates/index.html",   f"{PI_PATH}/templates/index.html"),
    ("static/style.css",       f"{PI_PATH}/static/style.css"),
    ("static/script.js",       f"{PI_PATH}/static/script.js"),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("라즈베리 파이에 연결 중...")
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)
print("연결 성공!")

sftp = ssh.open_sftp()

for local_rel, remote in files:
    local_full = os.path.join(LOCAL_BASE, local_rel)
    print(f"  전송 중: {local_rel} -> {remote}")
    sftp.put(local_full, remote)
    print(f"  ✅ 완료: {local_rel}")

sftp.close()
ssh.close()
print("\n🎉 모든 파일 전송 완료!")
