import atexit
import signal
import sys

from flask import Flask
from routes import setup_routes
import detector
import motor_esp32
import motor_arduino
import state


_cleaned_up = False


def _cleanup_motors():
    """프로그램 종료 시 모터 홀딩 전류 해제 후 안전하게 종료."""
    global _cleaned_up
    if _cleaned_up:
        return
    _cleaned_up = True
    print("\n[main] 종료 시그널 수신 — 모터 해제 중...")
    try:
        if state.device_type == "arduino":
            motor_arduino.estop()
        else:
            motor_esp32.release_motors()
    except Exception:
        pass
    try:
        motor_esp32.safe_disconnect()
    except Exception:
        pass
    try:
        motor_arduino.safe_disconnect()
    except Exception:
        pass
    print("[main] 모터 해제 완료. 종료합니다.")


def _shutdown(signum=None, frame=None):
    _cleanup_motors()
    sys.exit(0)


# 정상/비정상 종료 모두 대응
atexit.register(_cleanup_motors)
signal.signal(signal.SIGINT,  _shutdown)   # Ctrl+C
signal.signal(signal.SIGTERM, _shutdown)   # 프로세스 kill


app = Flask(__name__)

setup_routes(app)

detector.start()
motor_esp32.start()   # ESP32 연결 (포트 자동 감지)
motor_arduino.start() # Arduino 연결 (포트 자동 감지, device_type이 arduino일 때만 활성화)

app.run(
    host='0.0.0.0',
    port=5000,
    debug=False,
    threaded=True
)
