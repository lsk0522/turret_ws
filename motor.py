"""
모터 모듈 디스패처

state.device_type 에 따라 ESP32 / Arduino Uno 모듈을 자동 전환.
각 모듈은 device_type 을 감시하며 자신이 아닌 경우 포트를 해제하므로
두 모듈이 동시에 실행돼도 물리적 포트 충돌 없이 동작한다.
"""

import state
import motor_esp32
import motor_arduino


def start(port=None):
    motor_esp32.start(port)
    motor_arduino.start(port)


def stop_motors():
    if state.device_type == "arduino":
        motor_arduino.estop()
    else:
        motor_esp32.stop_motors()


def send_config(key: str, value):
    """ESP32 전용 CFG 명령"""
    if state.device_type == "esp32":
        motor_esp32.send_config(key, value)
