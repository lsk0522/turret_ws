import paramiko

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)

def run(cmd):
    _, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode().strip()

print("=" * 60)
print("📄 motor.py")
print("=" * 60)
print(run("cat /home/pi30306/turret_ws/motor.py"))

print("\n" + "=" * 60)
print("📄 motor_esp32.py")
print("=" * 60)
print(run("cat /home/pi30306/turret_ws/motor_esp32.py"))

print("\n" + "=" * 60)
print("📄 motor_arduino.py")
print("=" * 60)
print(run("cat /home/pi30306/turret_ws/motor_arduino.py"))

print("\n" + "=" * 60)
print("📄 detector.py (첫 60줄)")
print("=" * 60)
print(run("head -60 /home/pi30306/turret_ws/detector.py"))

print("\n" + "=" * 60)
print("📄 routes.py (첫 80줄)")
print("=" * 60)
print(run("head -80 /home/pi30306/turret_ws/routes.py"))

print("\n" + "=" * 60)
print("📁 esp32_firmware 폴더")
print("=" * 60)
print(run("ls -lh /home/pi30306/turret_ws/esp32_firmware/"))

ssh.close()
print("\n✅ 확인 완료!")
