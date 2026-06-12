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

# index.html 학습 관련 부분
print("=== index.html: learn 관련 부분 ===")
lines = run("cat /home/pi30306/turret_ws/templates/index.html").split('\n')
for i, line in enumerate(lines):
    if 'learn' in line.lower() or 'device' in line.lower() or 'esp32' in line.lower() or 'arduino' in line.lower() or 'motor' in line.lower() or 'connect' in line.lower():
        start = max(0, i-2)
        end = min(len(lines), i+5)
        print(f"--- Line {i+1} ---")
        print('\n'.join(lines[start:end]))
        print()

# script.js 학습 관련 부분  
print("\n=== script.js: learn 관련 함수 ===")
lines_js = run("cat /home/pi30306/turret_ws/static/script.js").split('\n')
in_learn = False
for i, line in enumerate(lines_js):
    if 'learn' in line.lower() or 'startLearn' in line or 'roi' in line.lower() or 'device_status' in line.lower() or 'esp32' in line.lower():
        start = max(0, i-1)
        end = min(len(lines_js), i+8)
        print(f"--- Line {i+1} ---")
        print('\n'.join(lines_js[start:end]))
        print()

ssh.close()
