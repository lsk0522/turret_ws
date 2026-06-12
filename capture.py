import cv2
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
