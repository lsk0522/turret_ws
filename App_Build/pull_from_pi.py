import paramiko

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)
sftp = ssh.open_sftp()

files = [
    ("/home/pi30306/turret_ws/templates/index.html",
     r"c:\Users\LSK0522\OneDrive - 서울로봇고등학교\바탕 화면\졸업작품\App_Build\turret_ws\templates\index.html"),
    ("/home/pi30306/turret_ws/static/script.js",
     r"c:\Users\LSK0522\OneDrive - 서울로봇고등학교\바탕 화면\졸업작품\App_Build\turret_ws\static\script.js"),
    ("/home/pi30306/turret_ws/static/style.css",
     r"c:\Users\LSK0522\OneDrive - 서울로봇고등학교\바탕 화면\졸업작품\App_Build\turret_ws\static\style.css"),
    ("/home/pi30306/turret_ws/routes.py",
     r"c:\Users\LSK0522\OneDrive - 서울로봇고등학교\바탕 화면\졸업작품\App_Build\turret_ws\routes.py"),
    ("/home/pi30306/turret_ws/detector.py",
     r"c:\Users\LSK0522\OneDrive - 서울로봇고등학교\바탕 화면\졸업작품\App_Build\turret_ws\detector.py"),
    ("/home/pi30306/turret_ws/state.py",
     r"c:\Users\LSK0522\OneDrive - 서울로봇고등학교\바탕 화면\졸업작품\App_Build\turret_ws\state.py"),
]

for remote, local in files:
    sftp.get(remote, local)
    print(f"✅ {remote.split('/')[-1]}")

sftp.close()
ssh.close()
print("done")
