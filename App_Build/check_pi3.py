import paramiko

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)

def run(cmd):
    _, stdout, _ = ssh.exec_command(cmd)
    return stdout.read().decode()

print("=== routes.py 전체 ===")
print(run("cat /home/pi30306/turret_ws/routes.py"))

print("\n=== detector.py 전체 ===")
print(run("cat /home/pi30306/turret_ws/detector.py"))

ssh.close()
