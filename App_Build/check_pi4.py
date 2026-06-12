import paramiko
import os

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)

def run(cmd):
    _, stdout, _ = ssh.exec_command(cmd)
    return stdout.read().decode()

# 전체 파일 읽기
print("=== detector.py ===")
print(run("cat /home/pi30306/turret_ws/detector.py"))

print("\n=== index.html 끝부분 100줄 ===")
print(run("tail -100 /home/pi30306/turret_ws/templates/index.html"))

print("\n=== script.js 첫 100줄 ===")
print(run("head -100 /home/pi30306/turret_ws/static/script.js"))

ssh.close()
