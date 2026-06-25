"""Camera module — supports physical camera and fallback dummy mode.
   Provides camera index selection and resolution/fps configuration.
"""

import cv2
import time
import threading
import numpy as np
import state
import sys

# ── Camera configuration state ─────────────────────────────────────
_camera_index  = 0
_cap           = None
_cap_lock      = threading.Lock()

# ── Mutable resolution / fps ────────────────────────────────────────
FRAME_W   = 640
FRAME_H   = 480
FRAME_FPS = 30

# ── Preset resolution options ───────────────────────────────────────
RESOLUTION_PRESETS = [
    (320,  240),
    (640,  480),
    (800,  600),
    (1280, 720),
    (1920, 1080),
]

FPS_PRESETS = [15, 24, 30, 60]

# ── Dummy fallback mode ────────────────────────────────────────────
_is_dummy = False


def _open_camera(index):
    """Open camera at given index with current FRAME_W/H/FPS settings."""
    global _is_dummy, FRAME_W, FRAME_H, FRAME_FPS
    if sys.platform.startswith('win'):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)

    if not cap.isOpened():
        _is_dummy = True
        print(f"[camera] index {index} open failed — dummy mode")
        return cap

    cap.set(cv2.CAP_PROP_FOURCC, getattr(cv2, 'VideoWriter_fourcc')(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    cap.set(cv2.CAP_PROP_FPS,          FRAME_FPS)

    # Read back actual values (driver may cap them)
    actual_w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    if actual_fps < 1:
        actual_fps = FRAME_FPS

    FRAME_W   = actual_w
    FRAME_H   = actual_h
    FRAME_FPS = actual_fps

    _is_dummy = False
    print(f"[camera] opened index {index}  {FRAME_W}×{FRAME_H} @ {FRAME_FPS}fps")
    return cap


def _get_fallback_frame():
    """Generate animated dummy frame when no physical camera is available."""
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    cv2.putText(frame, "NO CAMERA SIGNAL", (max(0, FRAME_W // 2 - 160), FRAME_H // 2 - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (60, 60, 60), 2)
    cv2.putText(frame, f"camera index: {_camera_index}  {FRAME_W}x{FRAME_H}",
                (max(0, FRAME_W // 2 - 160), FRAME_H // 2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 80, 80), 1)
    # Animated dots
    t = int(time.time() * 2) % 4
    for i in range(4):
        cx = FRAME_W // 2 - 30 + i * 20
        clr = (0, 200, 80) if i == t else (40, 40, 40)
        cv2.circle(frame, (cx, FRAME_H // 2 + 55), 6, clr, -1)
    return frame


# ── Open initial camera ────────────────────────────────────────────
_cap = _open_camera(_camera_index)

# ── Background Capture Thread ──────────────────────────────────────
_thread_running = True
def _capture_loop():
    global _cap
    while _thread_running:
        frame = None
        with _cap_lock:
            if _cap and _cap.isOpened():
                # Read as fast as possible to drain the buffer
                ok, raw = _cap.read()
                if ok and raw is not None:
                    frame = raw
        
        if frame is not None:
            if state.flip_enabled:
                frame = cv2.flip(frame, 1)
            state.current_frame = frame.copy()
        else:
            time.sleep(0.01)

_capture_thread = threading.Thread(target=_capture_loop, daemon=True)
_capture_thread.start()


def set_camera_index(index: int):
    """Switch to a different camera index at runtime."""
    global _cap, _camera_index
    with _cap_lock:
        if _cap and _cap.isOpened():
            _cap.release()
        _camera_index = index

        _cap = _open_camera(index)
    return not _is_dummy


def set_camera_resolution(width: int, height: int):
    """Change camera resolution and reopen."""
    global _cap, FRAME_W, FRAME_H
    with _cap_lock:
        FRAME_W = width
        FRAME_H = height
        if _cap and _cap.isOpened():
            _cap.release()
        _cap = _open_camera(_camera_index)
    return not _is_dummy


def set_camera_fps(fps: int):
    """Change camera FPS and reopen."""
    global _cap, FRAME_FPS
    with _cap_lock:
        FRAME_FPS = fps
        if _cap and _cap.isOpened():
            _cap.release()
        _cap = _open_camera(_camera_index)
    return not _is_dummy




def list_cameras(max_test=6):
    """Probe camera indices 0..max_test-1 and return available list."""
    available = []
    for i in range(max_test):
        if sys.platform.startswith('win'):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available


def gen_frames():
    """Yield MJPEG frames for the /video stream (Optimized)."""
    last_id = None
    last_buffer = None
    while True:
        frame = state.current_frame

        if frame is None:
            time.sleep(0.033)
            if last_buffer is None:
                frame = _get_fallback_frame()
                _, last_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
        else:
            frame_id = id(frame)
            if frame_id == last_id and last_buffer is not None:
                time.sleep(0.01)
            else:
                last_id = frame_id
                ret, last_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if not ret:
                    continue

        if last_buffer is not None:
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                last_buffer.tobytes() +
                b'\r\n'
            )

def gen_debug_frames():
    """Yield MJPEG frames with detection overlay for /video_debug (Optimized)."""
    last_id = None
    last_ball_id = None
    last_buffer = None
    while True:
        frame = state.current_frame
        if frame is None:
            time.sleep(0.03)
            continue

        ball = state.ball
        frame_id = id(frame)
        ball_id = id(ball) if ball else None

        if frame_id == last_id and ball_id == last_ball_id and last_buffer is not None:
            time.sleep(0.01)
        else:
            last_id = frame_id
            last_ball_id = ball_id
            vis  = frame.copy()

            if ball:
                lost  = state.ball_lost
                det   = ball.get("detector", "orb")
                color = (0, 165, 255) if lost else (
                    (255, 200, 0) if det == "hough" else (0, 255, 0)
                )

                if not ball.get("predicted", False) and "x" in ball:
                    cv2.rectangle(vis,
                        (ball["x"], ball["y"]),
                        (ball["x"] + ball["w"], ball["y"] + ball["h"]),
                        color, 2)
                    if det == "hough":
                        r = ball["w"] // 2
                        cv2.circle(vis, (ball["cx"], ball["cy"]), r, color, 2)

                pcx = ball.get("predicted_cx", ball["cx"])
                pcy = ball.get("predicted_cy", ball["cy"])
                cv2.drawMarker(vis, (pcx, pcy), color, cv2.MARKER_CROSS, 22, 2)
                label = "PREDICTING" if lost else (
                    f"Hough  r={ball['w']//2}px" if det == "hough"
                    else f"ORB  matches={ball.get('matches','?')}"
                )
                cv2.putText(vis, label, (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2)
            else:
                cv2.putText(vis, "No object", (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.62, (80, 80, 80), 2)

            _, last_buffer = cv2.imencode('.jpg', vis, [cv2.IMWRITE_JPEG_QUALITY, 80])

        if last_buffer is not None:
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                last_buffer.tobytes() +
                b'\r\n'
            )
