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

src = run("cat /home/pi30306/turret_ws/capture.py")
print(src)

# 18번줄 확인
lines = src.splitlines()
print(f"\n=== 18번줄: {lines[17] if len(lines) >= 18 else 'N/A'} ===")
ssh.close()
