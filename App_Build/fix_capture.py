import paramiko

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)
sftp = ssh.open_sftp()

new_src = """import cv2
import os
import time
from typing import Tuple

import state

if not os.path.exists("picture"):
    os.makedirs("picture")

def save_capture():

    if state.current_frame is None:
        return

    if state.last_point is None:
        return

    point: Tuple[int, int] = state.last_point  # type: ignore[assignment]
    x, y = point

    frame = state.current_frame.copy()

    filename = f"picture/{x}_{y}_{int(time.time())}.jpg"

    cv2.imwrite(filename, frame)

    print("캡쳐:", filename)
"""

with sftp.open('/home/pi30306/turret_ws/capture.py', 'w') as f:
    f.write(new_src)

sftp.close()
ssh.close()
print("done")
