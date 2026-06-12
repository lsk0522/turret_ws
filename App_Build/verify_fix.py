import paramiko

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)

def run(cmd):
    _, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

# 문법 검사
out, err = run("cd /home/pi30306/turret_ws && python3 -m py_compile detector.py && echo OK")
print("문법 검사:", out.strip() or err.strip())

# learn_zone 위치 확인
out, _ = run("grep -n 'learn_zone' /home/pi30306/turret_ws/detector.py")
print("\nlearn_zone 위치들:")
print(out)

# start_learning 정의 위치 확인
out, _ = run("grep -n 'def start_learning' /home/pi30306/turret_ws/detector.py")
print("\nstart_learning 정의들:")
print(out)

# ORBTracker.__init__ 부분 확인
out, _ = run("grep -n -A 20 'class ORBTracker' /home/pi30306/turret_ws/detector.py | head -30")
print("\nORBTracker class 시작:")
print(out)

ssh.close()
