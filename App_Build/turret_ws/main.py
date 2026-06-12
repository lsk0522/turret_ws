from flask import Flask
from routes import setup_routes
import detector
import motor

app = Flask(__name__)

setup_routes(app)

detector.start()
motor.start()      # ESP32 연결 (포트 자동 감지)

app.run(
    host='0.0.0.0',
    port=5000,
    debug=False
)