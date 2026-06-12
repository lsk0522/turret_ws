import paramiko, time

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)

def run(cmd):
    _, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode(), stderr.read().decode()

# 기존 서버 종료
run("pkill -f 'python.*main.py' 2>/dev/null; sleep 1")
time.sleep(1)

# 서버 재시작 (백그라운드)
run("cd /home/pi30306/turret_ws && nohup python3 main.py > /tmp/turret.log 2>&1 &")
time.sleep(2)

# 실행 확인
out, _ = run("pgrep -a python3 | grep main.py")
print("서버 프로세스:", out.strip())

out2, _ = run("tail -5 /tmp/turret.log")
print("로그:", out2)

ssh.close()
print("done")
