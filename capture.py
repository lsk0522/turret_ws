import cv2
import os
import time
from typing import Tuple

import state

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PICTURE_DIR = os.path.join(BASE_DIR, "picture")

if not os.path.exists(PICTURE_DIR):
    try:
        os.makedirs(PICTURE_DIR)
    except Exception as e:
        print(f"[capture] Failed to create picture directory: {e}")

def save_capture():
    if state.current_frame is None:
        print("[capture] ERROR: state.current_frame is None. Camera not active or failed to read.")
        return

    try:
        x, y = state.point[0], state.point[1]
        frame = state.current_frame.copy()
        filename = f"{x}_{y}_{int(time.time())}.jpg"
        filepath = os.path.join(PICTURE_DIR, filename)
        
        success = cv2.imwrite(filepath, frame)
        if success:
            print("캡쳐 성공:", filepath)
        else:
            print("캡쳐 실패: cv2.imwrite 반환값 False (경로 또는 권한 문제 가능성)", filepath)
    except Exception as e:
        print(f"[capture] Exception during save_capture: {e}")
