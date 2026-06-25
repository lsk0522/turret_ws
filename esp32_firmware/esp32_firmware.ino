/* =====================================================================================
 * AI Vision Tracker ESP32 Firmware
 * Python motor_esp32.py 완전 호환 버전
 *
 * 핀 배선 (Lolin D32)
 * M1_ENA → GPIO 13    M1_DIR → GPIO 14    M1_PUL → GPIO 16
 * M2_ENA → GPIO 22    M2_DIR → GPIO 21    M2_PUL → GPIO 23
 *
 * 통신 프로토콜 (115200 baud)
 * Pi → ESP32
 *   T:<x>:<y>            화면 좌표 → 실시간 추적
 *   MOVE J M1 50.0       M1 절대 이동 (mm)
 *   MOVE J M2 30.5       M2 절대 이동 (mm)
 *   MOVE J M1,M2 20.0    M1+M2 동시 이동
 *   S                    즉시 정지
 *   REL                  홀딩 전류 즉시 해제 (ENA HIGH)
 *   SETHOME              현재 위치를 원점으로
 *   STATUS / POS         현재 위치 출력
 *   CFG:MSL:<hz>         최대 속도 Hz
 *   CFG:ACC:<rate*10>    가속도 (50 = 5.0 Hz/ms)
 *   CFG:SPD1:<steps*10>  M1 steps/mm x10
 *   CFG:SPD2:<steps*10>  M2 steps/mm x10
 *   CFG:SPX:<steps*1000> steps/pixel x1000
 *   CFG:M1I:<0|1>        M1 방향 반전
 *   CFG:M2I:<0|1>        M2 방향 반전
 *
 * ESP32 → Pi
 *   POS:m1*100:m2*100:spd1:spd2  (30ms 주기)
 *   REL:AUTO                     Watchdog 자동 해제 알림
 *   OK <command>
 *
 * Watchdog: 3초 이상 명령 없으면 ENA HIGH(해제). 다음 명령 오면 자동 재활성화.
 * ===================================================================================== */

#include <Arduino.h>

#define FIRMWARE_VERSION "2.0.0"

// 핀 정의
#define M1_ENA 13
#define M1_DIR 14
#define M1_PUL 16
#define M2_ENA 22
#define M2_DIR 21
#define M2_PUL 23

// 물리 파라미터
float STEPS_PER_DEG_M1  = 44.44f;
float STEPS_PER_DEG_M2  = 44.44f;
float STEPS_PER_PIX    = 3.5f;
float MAX_SPEED_LIMIT  = 3000.0f;
float ACCELERATION_RATE= 8.0f;

// 방향 반전
bool M1_INVERT = false;
bool M2_INVERT = true;    // 수직 모터 기본 반전

// 화면 중앙
const int CENTER_X = 320;
const int CENTER_Y = 240;

// Watchdog (3초)
#define WATCHDOG_MS 3000
unsigned long lastCmdMs  = 0;
bool motorsEnabled       = true;

// 위치/속도
long targetPosM1 = 0, currentPosM1 = 0;
long targetPosM2 = 0, currentPosM2 = 0;
float currentSpeedM1 = 0.0f;
float currentSpeedM2 = 0.0f;
unsigned long lastPulseTimeM1 = 0, lastPulseTimeM2 = 0;
unsigned long lastAccelTimeM1 = 0, lastAccelTimeM2 = 0;
unsigned long lastStatusMs    = 0;
String _serialBuf             = "";

// 함수 선언
void parseCommand(String cmd);
void sendPosStatus();
void stepMotors(unsigned long curUs, unsigned long curMs);
void enableMotors();
void releaseMotors();

// 모터 활성화
void enableMotors() {
  if (!motorsEnabled) {
    digitalWrite(M1_ENA, LOW);
    digitalWrite(M2_ENA, LOW);
    motorsEnabled = true;
  }
}

// 홀딩 전류 해제
void releaseMotors() {
  targetPosM1 = currentPosM1;
  targetPosM2 = currentPosM2;
  currentSpeedM1 = 0.0f;
  currentSpeedM2 = 0.0f;
  digitalWrite(M1_ENA, HIGH);  // HIGH = ENA 비활성 (홀딩 전류 차단)
  digitalWrite(M2_ENA, HIGH);
  motorsEnabled = false;
}

void setup() {
  Serial.begin(115200);
  pinMode(M1_ENA, OUTPUT); pinMode(M1_DIR, OUTPUT); pinMode(M1_PUL, OUTPUT);
  pinMode(M2_ENA, OUTPUT); pinMode(M2_DIR, OUTPUT); pinMode(M2_PUL, OUTPUT);
  digitalWrite(M1_ENA, LOW);
  digitalWrite(M2_ENA, LOW);
  digitalWrite(M1_PUL, HIGH);
  digitalWrite(M2_PUL, HIGH);
  lastStatusMs = millis();
  lastCmdMs    = millis();
  Serial.print("VER:"); Serial.println(FIRMWARE_VERSION);
  Serial.println("OK BOOT AI Vision Tracker ESP32 Ready");
}

void loop() {
  unsigned long curUs = micros();
  unsigned long curMs = millis();

  // Watchdog
  if (motorsEnabled && (curMs - lastCmdMs >= WATCHDOG_MS)) {
    releaseMotors();
    Serial.println("REL:AUTO");
  }

  stepMotors(curUs, curMs);

  if (curMs - lastStatusMs >= 30) {
    lastStatusMs = curMs;
    sendPosStatus();
  }

  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      _serialBuf.trim();
      if (_serialBuf.length() > 0)
        parseCommand(_serialBuf);
      _serialBuf = "";
    } else {
      if (_serialBuf.length() < 128) _serialBuf += c;
      else _serialBuf = "";
    }
  }
}

void stepMotors(unsigned long curUs, unsigned long curMs) {
  if (!motorsEnabled) return;

  // M1
  long remM1 = targetPosM1 - currentPosM1;
  if (remM1 != 0) {
    bool dir1 = (remM1 > 0) ^ M1_INVERT;
    digitalWrite(M1_DIR, dir1 ? HIGH : LOW);
    float wallSpd1 = min(MAX_SPEED_LIMIT, (float)abs(remM1) * 20.0f);
    if (wallSpd1 < 20.0f) wallSpd1 = 20.0f;
    if (curMs - lastAccelTimeM1 >= 1) {
      lastAccelTimeM1 = curMs;
      if (currentSpeedM1 < wallSpd1) currentSpeedM1 += ACCELERATION_RATE;
    }
    if (currentSpeedM1 > wallSpd1) currentSpeedM1 = wallSpd1;
    if (currentSpeedM1 > 5.0f) {
      unsigned long interval = (unsigned long)(1000000.0f / currentSpeedM1);
      if (curUs - lastPulseTimeM1 >= interval) {
        lastPulseTimeM1 = curUs;
        digitalWrite(M1_PUL, LOW); delayMicroseconds(10); digitalWrite(M1_PUL, HIGH);
        currentPosM1 += (remM1 > 0) ? 1 : -1;
      }
    }
  } else { currentSpeedM1 = 0.0f; }

  // M2
  long remM2 = targetPosM2 - currentPosM2;
  if (remM2 != 0) {
    bool dir2 = (remM2 > 0) ^ M2_INVERT;
    digitalWrite(M2_DIR, dir2 ? HIGH : LOW);
    float wallSpd2 = min(MAX_SPEED_LIMIT, (float)abs(remM2) * 20.0f);
    if (wallSpd2 < 20.0f) wallSpd2 = 20.0f;
    if (curMs - lastAccelTimeM2 >= 1) {
      lastAccelTimeM2 = curMs;
      if (currentSpeedM2 < wallSpd2) currentSpeedM2 += ACCELERATION_RATE;
    }
    if (currentSpeedM2 > wallSpd2) currentSpeedM2 = wallSpd2;
    if (currentSpeedM2 > 5.0f) {
      unsigned long interval = (unsigned long)(1000000.0f / currentSpeedM2);
      if (curUs - lastPulseTimeM2 >= interval) {
        lastPulseTimeM2 = curUs;
        digitalWrite(M2_PUL, LOW); delayMicroseconds(10); digitalWrite(M2_PUL, HIGH);
        currentPosM2 += (remM2 > 0) ? 1 : -1;
      }
    }
  } else { currentSpeedM2 = 0.0f; }
}

void sendPosStatus() {
  long pm1 = (STEPS_PER_DEG_M1 > 0.001f) ? (long)((currentPosM1 / STEPS_PER_DEG_M1) * 100.0f) : 0;
  long pm2 = (STEPS_PER_DEG_M2 > 0.001f) ? (long)((currentPosM2 / STEPS_PER_DEG_M2) * 100.0f) : 0;
  Serial.print("POS:"); Serial.print(pm1); Serial.print(":");
  Serial.print(pm2);   Serial.print(":");
  Serial.print((int)currentSpeedM1); Serial.print(":");
  Serial.println((int)currentSpeedM2);
}

void parseCommand(String cmd) {
  if (cmd.length() == 0) return;

  String upper = cmd;
  upper.toUpperCase();

  // 모든 이동 명령 → Watchdog 갱신 + 모터 재활성화
  lastCmdMs = millis();
  if (!motorsEnabled) enableMotors();

  // REL — 즉시 해제
  if (upper == "REL") {
    releaseMotors();
    Serial.println("OK REL");
    return;
  }

  // T:x:y
  if (upper.startsWith("T:")) {
    int c1 = cmd.indexOf(':', 2);
    if (c1 < 0) return;
    int px = cmd.substring(2, c1).toInt();
    int py = cmd.substring(c1 + 1).toInt();
    
    // 1. 임시 목표 스텝 계산 (현재 위치 + 픽셀 오차 기반 상대 이동)
    long tempTargetM1 = currentPosM1 + (long)((px - CENTER_X) * STEPS_PER_PIX);
    long tempTargetM2 = currentPosM2 + (long)((py - CENTER_Y) * STEPS_PER_PIX);

    // 2. M2(수직) 각도 계산 및 제한 (-45 ~ +45도)
    float angleM2 = tempTargetM2 / STEPS_PER_DEG_M2;
    if (angleM2 < -45.0f) angleM2 = -45.0f;
    if (angleM2 > 45.0f)  angleM2 = 45.0f;
    targetPosM2 = (long)(angleM2 * STEPS_PER_DEG_M2);

    // 3. M1(수평) 각도 계산 및 조건부 제한
    float angleM1 = tempTargetM1 / STEPS_PER_DEG_M1;
    
    // 기본 수평 한계: 360도 회전 허용 (±180도)
    float limitM1 = 180.0f;
    
    // 수직(M2)이 25도 이상 꺾였을 때(위든 아래든 상관없이 절대값 적용): 수평을 ±85도 (총 170도)로 제한
    if (abs(angleM2) >= 25.0f) {
        limitM1 = 85.0f;
    }
    
    if (angleM1 < -limitM1) angleM1 = -limitM1;
    if (angleM1 > limitM1)  angleM1 = limitM1;
    targetPosM1 = (long)(angleM1 * STEPS_PER_DEG_M1);
    
    return;
  }

  // S — 정지
  if (upper == "S") {
    targetPosM1 = currentPosM1; targetPosM2 = currentPosM2;
    currentSpeedM1 = 0.0f; currentSpeedM2 = 0.0f;
    Serial.println("OK S");
    return;
  }

  // SETHOME
  if (upper == "SETHOME") {
    currentPosM1 = 0; currentPosM2 = 0;
    targetPosM1  = 0; targetPosM2  = 0;
    Serial.println("OK SETHOME");
    return;
  }

  // STATUS / POS
  if (upper == "STATUS" || upper == "POS") {
    sendPosStatus();
    return;
  }

  // MODE (호환용)
  if (upper == "MODE:POS" || upper == "MODE:TRACK") {
    Serial.print("OK "); Serial.println(upper);
    return;
  }

  // CFG
  if (upper.startsWith("CFG:")) {
    int sep1 = cmd.indexOf(':', 4);
    if (sep1 < 0) return;
    String key = cmd.substring(4, sep1); key.toUpperCase();
    String val = cmd.substring(sep1 + 1);

    if      (key == "SPD1") STEPS_PER_DEG_M1  = val.toFloat() / 10.0f;
    else if (key == "SPD2") STEPS_PER_DEG_M2  = val.toFloat() / 10.0f;
    else if (key == "MSL")  MAX_SPEED_LIMIT   = (float)val.toInt();
    else if (key == "ACC")  ACCELERATION_RATE = val.toFloat() / 10.0f;
    else if (key == "SPX")  STEPS_PER_PIX     = val.toFloat() / 1000.0f;
    else if (key == "M1I")  M1_INVERT         = (val.toInt() != 0);
    else if (key == "M2I")  M2_INVERT         = (val.toInt() != 0);

    Serial.print("OK CFG:"); Serial.print(key);
    Serial.print(":"); Serial.println(val);
    return;
  }

  // MOVE J
  if (upper.startsWith("MOVE J ")) {
    String args  = cmd.substring(7); args.trim();
    String argsU = args; argsU.toUpperCase();
    int spaceIdx = args.lastIndexOf(' ');
    if (spaceIdx < 0) { Serial.println("ERROR: No mm value"); return; }
    float mmVal = args.substring(spaceIdx + 1).toFloat();
    if (argsU.startsWith("M1,M2") || argsU.startsWith("M1, M2")) {
      targetPosM1 = (long)round(mmVal * STEPS_PER_DEG_M1);
      targetPosM2 = (long)round(mmVal * STEPS_PER_DEG_M2);
      Serial.print("OK MOVE J M1,M2 "); Serial.println(mmVal);
    } else if (argsU.startsWith("M1")) {
      targetPosM1 = (long)round(mmVal * STEPS_PER_DEG_M1);
      Serial.print("OK MOVE J M1 "); Serial.println(mmVal);
    } else if (argsU.startsWith("M2")) {
      targetPosM2 = (long)round(mmVal * STEPS_PER_DEG_M2);
      Serial.print("OK MOVE J M2 "); Serial.println(mmVal);
    } else {
      Serial.println("ERROR: Target must be M1, M2, or M1,M2");
    }
    return;
  }

  Serial.print("ERROR: Unknown command: "); Serial.println(cmd);
}
