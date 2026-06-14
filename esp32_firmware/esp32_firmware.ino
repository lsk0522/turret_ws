/* =====================================================================================
 * Turret ESP32 Firmware — 단순 루프 기반 mm 위치 제어
 * Python motor_esp32.py 완전 호환 버전
 *
 * 📌 핀 배선 (Lolin D32)
 * M1_ENA → GPIO 13    M1_DIR → GPIO 14    M1_PUL → GPIO 16
 * M2_ENA → GPIO 22    M2_DIR → GPIO 21    M2_PUL → GPIO 23
 *
 * 통신 프로토콜 (115200 baud)
 * ── Pi → ESP32 ──────────────────────────────────────────────────
 * "MOVE J M1 50.0\n"       M1을 50.0mm로 절대 이동
 * "MOVE J M2 30.5\n"       M2를 30.5mm로 절대 이동
 * "MOVE J M1,M2 20.0\n"    M1+M2 동시 이동
 * "S\n"                    즉시 정지
 * "SETHOME\n"              현재 위치를 원점으로 설정
 * "STATUS\n" / "POS\n"     현재 위치 즉시 출력
 * "MODE:POS\n"             (무시 — 항상 위치 제어 모드)
 * "MODE:TRACK\n"           (무시)
 * "CFG:MSL:<hz>\n"         최대 속도 Hz 변경
 * "CFG:ACC:<rate*10>\n"    가속도 변경 (예: 50 = 5.0 Hz/ms)
 * "CFG:SPM1:<steps*10>\n"  M1 steps/mm × 10 
 * "CFG:SPM2:<steps*10>\n"  M2 steps/mm × 10
 *
 * ── ESP32 → Pi ──────────────────────────────────────────────────
 * "POS:m1_mm*100:m2_mm*100:spd1:spd2\n"  (30ms 주기 자동 출력)
 * "OK <command>\n"
 * =====================================================================================
 */

// ── 헤더 선언 (대문자 A 필수) ──────────────────────────────────────
#include <Arduino.h>

// ── 핀 정의 ──────────────────────────────────────────────────────
#define M1_ENA 13
#define M1_DIR 14
#define M1_PUL 16

#define M2_ENA 22
#define M2_DIR 21
#define M2_PUL 23

// ── 물리 파라미터 (CFG 명령으로 실시간 변경 가능) ────────────────
float STEPS_PER_MM_M1 = 78.0; // M1 steps/mm
float STEPS_PER_MM_M2 = 78.0; // M2 steps/mm

float MAX_SPEED_LIMIT = 1000.0; // 최대 Hz (탈조 방지용 낮은 값)
float ACCELERATION_RATE = 5.0;  // Hz/ms (탈조 방지용 낮은 가속도)

// ── 위치 추적 변수 ────────────────────────────────────────────────
long targetPosM1 = 0, currentPosM1 = 0;
long targetPosM2 = 0, currentPosM2 = 0;

float currentSpeedM1 = 0.0;
float currentSpeedM2 = 0.0;

unsigned long lastPulseTimeM1 = 0;
unsigned long lastPulseTimeM2 = 0;
unsigned long lastAccelTimeM1 = 0;
unsigned long lastAccelTimeM2 = 0;

unsigned long lastStatusMs = 0;
String _serialBuf = ""; // 논블로킹 수신 버퍼

// ── 함수 선언 ─────────────────────────────────────────────────────
void parseCommand(String cmd);
void sendPosStatus();

// ── Setup ─────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200); // Serial0 -> Serial로 수정

  pinMode(M1_ENA, OUTPUT);
  pinMode(M1_DIR, OUTPUT);
  pinMode(M1_PUL, OUTPUT);
  pinMode(M2_ENA, OUTPUT);
  pinMode(M2_DIR, OUTPUT);
  pinMode(M2_PUL, OUTPUT);

  digitalWrite(M1_ENA, LOW); // 드라이버 활성화
  digitalWrite(M2_ENA, LOW);
  digitalWrite(M1_PUL, HIGH); // 비활성 상태 (PUL- 방식)
  digitalWrite(M2_PUL, HIGH);

  lastStatusMs = millis();

  Serial.println("OK BOOT — Turret ESP32 Simple Firmware Ready");
}

// ── Loop ──────────────────────────────────────────────────────────
void loop() {
  unsigned long curUs = micros();
  unsigned long curMs = millis();

  // ── M1 가감속 위치 제어 ──────────────────────────────────────
  long remM1 = targetPosM1 - currentPosM1;
  if (remM1 != 0) {
    digitalWrite(M1_DIR, remM1 > 0 ? HIGH : LOW);

    // 감속벽: 목표 근처에서도 충분한 속도 유지 + 최소 80Hz 보장
    float wallSpd1 = min(MAX_SPEED_LIMIT, abs(remM1) * 20.0f);
    if (wallSpd1 < 80.0f)
      wallSpd1 = 80.0f;

    // 1ms마다 가속
    if (curMs - lastAccelTimeM1 >= 1) {
      lastAccelTimeM1 = curMs;
      if (currentSpeedM1 < wallSpd1)
        currentSpeedM1 += ACCELERATION_RATE;
    }
    if (currentSpeedM1 > wallSpd1)
      currentSpeedM1 = wallSpd1;

    // 펄스 발생 (최소 10Hz 이상일 때)
    if (currentSpeedM1 > 10.0f) {
      unsigned long interval = (unsigned long)(1000000.0f / currentSpeedM1);
      if (curUs - lastPulseTimeM1 >= interval) {
        lastPulseTimeM1 = curUs;
        digitalWrite(M1_PUL, LOW);
        delayMicroseconds(5);
        digitalWrite(M1_PUL, HIGH);
        if (remM1 > 0)
          currentPosM1++;
        else
          currentPosM1--;
      }
    }
  } else {
    currentSpeedM1 = 0.0f;
  }

  // ── M2 가감속 위치 제어 ──────────────────────────────────────
  long remM2 = targetPosM2 - currentPosM2;
  if (remM2 != 0) {
    digitalWrite(M2_DIR, remM2 > 0 ? HIGH : LOW);

    float wallSpd2 = min(MAX_SPEED_LIMIT, abs(remM2) * 20.0f);
    if (wallSpd2 < 80.0f)
      wallSpd2 = 80.0f;

    if (curMs - lastAccelTimeM2 >= 1) {
      lastAccelTimeM2 = curMs;
      if (currentSpeedM2 < wallSpd2)
        currentSpeedM2 += ACCELERATION_RATE;
    }
    if (currentSpeedM2 > wallSpd2)
      currentSpeedM2 = wallSpd2;

    if (currentSpeedM2 > 10.0f) {
      unsigned long interval = (unsigned long)(1000000.0f / currentSpeedM2);
      if (curUs - lastPulseTimeM2 >= interval) {
        lastPulseTimeM2 = curUs;
        digitalWrite(M2_PUL, LOW);
        delayMicroseconds(5);
        digitalWrite(M2_PUL, HIGH);
        if (remM2 > 0)
          currentPosM2++;
        else
          currentPosM2--;
      }
    }
  } else {
    currentSpeedM2 = 0.0f;
  }

  // ── 30ms마다 POS 자동 피드백 ────────────────────────────────
  if (curMs - lastStatusMs >= 30) {
    lastStatusMs = curMs;
    sendPosStatus();
  }

  // ── 비블로킹 시리얼 명령 수신 ───────────────────────────
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      _serialBuf.trim();
      if (_serialBuf.length() > 0)
        parseCommand(_serialBuf);
      _serialBuf = "";
    } else {
      if (_serialBuf.length() < 128)
        _serialBuf += c;
      else
        _serialBuf = ""; 
    }
  }
}

// ── POS 피드백 출력 (Python motor_esp32.py 호환 형식) ────────────
void sendPosStatus() {
  long pm1_cm = (STEPS_PER_MM_M1 > 0.001f)
                    ? (long)((currentPosM1 / STEPS_PER_MM_M1) * 100.0f)
                    : 0;
  long pm2_cm = (STEPS_PER_MM_M2 > 0.001f)
                    ? (long)((currentPosM2 / STEPS_PER_MM_M2) * 100.0f)
                    : 0;
  Serial.print("POS:");
  Serial.print(pm1_cm);
  Serial.print(":");
  Serial.print(pm2_cm);
  Serial.print(":");
  Serial.print((int)currentSpeedM1);
  Serial.print(":");
  Serial.println((int)currentSpeedM2);
}

// ── 명령 파서 ─────────────────────────────────────────────────────
void parseCommand(String cmd) {
  if (cmd.length() == 0)
    return;

  String upper = cmd;
  upper.toUpperCase();

  // 즉시 정지
  if (upper == "S") {
    targetPosM1 = currentPosM1;
    targetPosM2 = currentPosM2;
    currentSpeedM1 = 0.0f;
    currentSpeedM2 = 0.0f;
    Serial.println("OK S");
    return;
  }

  // 원점 설정
  if (upper == "SETHOME") {
    currentPosM1 = 0;
    currentPosM2 = 0;
    targetPosM1 = 0;
    targetPosM2 = 0;
    Serial.println("OK SETHOME");
    return;
  }

  // 위치 즉시 요청
  if (upper == "STATUS" || upper == "POS") {
    sendPosStatus();
    return;
  }

  // MODE 명령
  if (upper == "MODE:POS" || upper == "MODE:TRACK") {
    Serial.print("OK ");
    Serial.println(upper);
    return;
  }

  // CFG 파라미터 실시간 변경
  if (upper.startsWith("CFG:")) {
    int sep1 = cmd.indexOf(':', 4);
    if (sep1 < 0)
      return;
    String key = cmd.substring(4, sep1);
    key.toUpperCase();
    String val = cmd.substring(sep1 + 1);

    if (key == "SPM1")
      STEPS_PER_MM_M1 = val.toFloat() / 10.0f;
    else if (key == "SPM2")
      STEPS_PER_MM_M2 = val.toFloat() / 10.0f;
    else if (key == "MSL")
      MAX_SPEED_LIMIT = (float)val.toInt();
    else if (key == "ACC")
      ACCELERATION_RATE = val.toFloat() / 10.0f;

    Serial.print("OK CFG:");
    Serial.print(key);
    Serial.print(":");
    Serial.println(val);
    return;
  }

  // MOVE J 명령
  if (upper.startsWith("MOVE J ")) {
    String args = cmd.substring(7);
    args.trim();
    String argsU = args;
    argsU.toUpperCase();

    int spaceIdx = args.lastIndexOf(' ');
    if (spaceIdx < 0) {
      Serial.println("ERROR: No mm value");
      return;
    }
    float mmVal = args.substring(spaceIdx + 1).toFloat();

    if (argsU.startsWith("M1,M2") || argsU.startsWith("M1, M2")) {
      targetPosM1 = (long)round(mmVal * STEPS_PER_MM_M1);
      targetPosM2 = (long)round(mmVal * STEPS_PER_MM_M2);
      Serial.print("OK MOVE J M1,M2 ");
      Serial.println(mmVal);
    } else if (argsU.startsWith("M1")) {
      targetPosM1 = (long)round(mmVal * STEPS_PER_MM_M1);
      Serial.print("OK MOVE J M1 ");
      Serial.println(mmVal);
    } else if (argsU.startsWith("M2")) {
      targetPosM2 = (long)round(mmVal * STEPS_PER_MM_M2);
      Serial.print("OK MOVE J M2 ");
      Serial.println(mmVal);
    } else {
      Serial.println("ERROR: Target must be M1, M2, or M1,M2");
    }
    return;
  }

  Serial.print("ERROR: Unknown command: ");
  Serial.println(cmd);
}
