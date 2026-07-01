/* =====================================================================================
 * AI Vision Tracker ESP32 Firmware  v2.0.7
 * Python motor_esp32.py 완전 호환 버전
 *
 * [v2.0.1 변경사항]
 * BUG FIX 1: Watchdog이 main.py 시작 직후 즉시 발동하는 문제
 *   - 원인: FreeRTOS Task 기동 지연으로 lastCmdMs 기점이 틀어짐
 *   - 수정: motorTask 진입 직후 lastCmdMs 재갱신, WATCHDOG_MS 3000→5000
 *
 * BUG FIX 2: 부팅 시 ENA GPIO 플로팅(HIGH) → 드라이버 비활성화
 *   - 원인: pinMode() 선언 전 GPIO가 HIGH 상태로 잠깐 유지됨
 *   - 수정: setup() 최상단에서 digitalWrite(ENA, LOW) 선행 호출
 *
 * BUG FIX 3: REL 이후 Watchdog 중복 발동
 *   - 원인: Watchdog 조건에 userReleased 미확인
 *   - 수정: !userReleased 조건 추가
 *
 * [v2.0.2 변경사항]
 * BUG FIX 4: POS 명령 수신 시 serialMutex 재진입으로 motorTask 정지
 *   - 원인: serialTask가 serialMutex를 잡고 parseCommand() 호출,
 *           parseCommand("POS") 내부 sendPosStatus()가 같은 mutex를 다시 요청
 *   - 수정: serialTask에서 parseCommand() 자체는 잠그지 않음
 *
 * [v2.0.3 변경사항]
 * BUG FIX 5: REL 이후 모터 활성화 상태 복구 명령 추가
 *   - ENA / ENABLE 명령으로 드라이버 활성화(ENA LOW)를 명시적으로 수행
 *   - enableMotors()가 내부 상태와 무관하게 ENA 핀을 항상 LOW로 재출력
 *
 * [v2.0.4 변경사항]
 * BUG FIX 6: 이동 중 Watchdog 자동 해제로 모터 전원이 꺼지는 문제
 *   - 남은 이동량이 없을 때만 REL:AUTO 실행
 *   - 이동 중에는 명령 공백이 길어져도 ENA LOW 유지
 *
 * [v2.0.5 변경사항]
 * TUNING 1: 조이스틱 수동 조작 부드러움 개선
 *   - 기본 가속도를 낮추고, 남은 거리 대비 목표 속도 기울기를 완화
 *
 * [v2.0.6 변경사항]
 * TUNING 2: 과이동과 끊김 감소
 *   - 기본 가속도와 목표 속도 기울기를 추가 완화
 *
 * [v2.0.7 변경사항]
 * FIX: S 명령을 점진 감속에서 즉시 정지로 변경
 *   - S 수신 시 targetPos=currentPos, speed=0 즉시 설정
 *   - 조이스틱에서 손을 떼면 모터가 그 자리에서 즉시 멈춤
 *
 * 핀 배선 (Lolin D32)
 * M1_ENA → GPIO 13    M1_DIR → GPIO 14    M1_PUL → GPIO 16
 * M2_ENA → GPIO 22    M2_DIR → GPIO 21    M2_PUL → GPIO 23
 *
 * 통신 프로토콜 (115200 baud)
 * [Pi → ESP32]
 *   T:<x>:<y>            화면 좌표 → 실시간 추적
 *   MOVE J M1 50.0       M1 절대 이동 (degree)
 *   MOVE J M2 30.5       M2 절대 이동
 *   MOVE J M1,M2 20.0    M1+M2 동시 이동
 *   MOVE J XY 10.0 20.0  M1, M2 개별 각도 지정
 *   S                    즉시 정지
 *   REL                  홀딩 전류 즉시 해제 (ENA HIGH)
 *   ENA / ENABLE         홀딩 전류 재활성화 (ENA LOW)
 *   SETHOME              현재 위치를 원점으로
 *   STATUS / POS         현재 위치 출력
 *   CFG:MSL:<hz>         최대 속도 Hz
 *   CFG:ACC:<rate*10>    가속도 (50 = 5.0 Hz/ms)
 *   CFG:SPD1:<steps*10>  M1 steps/deg x10
 *   CFG:SPD2:<steps*10>  M2 steps/deg x10
 *   CFG:SPX:<steps*1000> steps/pixel x1000
 *   CFG:M1I:<0|1>        M1 방향 반전
 *   CFG:M2I:<0|1>        M2 방향 반전
 *
 * [ESP32 → Pi]
 *   POS:m1*100:m2*100:spd1:spd2  (30ms 주기)
 *   REL:AUTO                     Watchdog 자동 해제 알림
 *   OK <command>
 *
 * Watchdog: 5초 이상 명령 없으면 ENA HIGH(해제). 다음 명령 오면 자동 재활성화.
 * ===================================================================================== */

#include <Arduino.h>
#include <stdint.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#define FIRMWARE_VERSION "2.0.7"

// 핀 정의
#define M1_ENA 13
#define M1_DIR 14
#define M1_PUL 16
#define M2_ENA 22
#define M2_DIR 21
#define M2_PUL 23

// 물리 파라미터
float STEPS_PER_DEG_M1   = 44.44f;
float STEPS_PER_DEG_M2   = 44.44f;
float STEPS_PER_PIX      = 3.5f;
float MAX_SPEED_LIMIT    = 3000.0f;
float ACCELERATION_RATE  = 3.0f;

// 방향 반전
bool M1_INVERT = false;
bool M2_INVERT = true;

// 화면 중앙
const int CENTER_X = 320;
const int CENTER_Y = 240;

// [FIX 1] Watchdog 3000 → 5000ms
#define WATCHDOG_MS 5000

unsigned long lastCmdMs  = 0;
bool motorsEnabled       = true;
bool userReleased        = false;

// 위치/속도
long targetPosM1 = 0, currentPosM1 = 0;
long targetPosM2 = 0, currentPosM2 = 0;
float currentSpeedM1 = 0.0f;
float currentSpeedM2 = 0.0f;
unsigned long lastPulseTimeM1 = 0, lastPulseTimeM2 = 0;
unsigned long lastAccelTimeM1 = 0, lastAccelTimeM2 = 0;
unsigned long lastStatusMs    = 0;

bool isJogging = false;
float jogVx = 0.0f;
float jogVy = 0.0f;
unsigned long lastJogMs = 0;
// 함수 선언
void parseCommand(String cmd);
void sendPosStatus();
void stepMotors(unsigned long curUs, unsigned long curMs);
void enableMotors();
void releaseMotors();
void setTargetAngles(float angleM1, float angleM2);

void enableMotors() {
  digitalWrite(M1_ENA, LOW);
  digitalWrite(M2_ENA, LOW);
  motorsEnabled = true;
  userReleased = false;
}

void releaseMotors() {
  targetPosM1 = currentPosM1;
  targetPosM2 = currentPosM2;
  currentSpeedM1 = 0.0f;
  currentSpeedM2 = 0.0f;
  digitalWrite(M1_ENA, HIGH);
  digitalWrite(M2_ENA, HIGH);
  motorsEnabled = false;
}

SemaphoreHandle_t serialMutex;
TaskHandle_t serialTaskHandle = NULL;
TaskHandle_t motorTaskHandle  = NULL;

void serialTask(void *pvParameters) {
  String buf = "";
  while (1) {
    while (Serial.available() > 0) {
      char c = (char)Serial.read();
      if (c == '\n') {
        buf.trim();
        if (buf.length() > 0) {
          parseCommand(buf);
        }
        buf = "";
      } else {
        if (buf.length() < 128) buf += c;
        else buf = "";
      }
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

void motorTask(void *pvParameters) {
  // [FIX 1] Task 실제 기동 시점으로 Watchdog 기점 재설정
  lastCmdMs = millis();

  unsigned long lastWdtMs = millis();
  while (1) {
    unsigned long curUs = micros();
    unsigned long curMs = millis();

    long remM1 = targetPosM1 - currentPosM1;
    long remM2 = targetPosM2 - currentPosM2;
    bool isIdle = (remM1 == 0 && remM2 == 0);

    if (isJogging) {
      if (curMs - lastJogMs > 150) {
        isJogging = false;
        targetPosM1 = currentPosM1;
        targetPosM2 = currentPosM2;
        currentSpeedM1 = 0;
        currentSpeedM2 = 0;
      } else {
        if (abs(jogVx) > 0.01) targetPosM1 = currentPosM1 + (jogVx > 0 ? 1000 : -1000);
        else targetPosM1 = currentPosM1;
        if (abs(jogVy) > 0.01) targetPosM2 = currentPosM2 + (jogVy > 0 ? 1000 : -1000);
        else targetPosM2 = currentPosM2;
      }
    }

    // [FIX 3, 6] 사용자 해제가 아니고, 완전히 정지 상태일 때만 자동 해제
    if (motorsEnabled && !userReleased && isIdle && (curMs - lastCmdMs >= WATCHDOG_MS)) {
      releaseMotors();
      xSemaphoreTake(serialMutex, portMAX_DELAY);
      Serial.println("REL:AUTO");
      xSemaphoreGive(serialMutex);
    }

    stepMotors(curUs, curMs);

    if (curMs - lastStatusMs >= 30) {
      lastStatusMs = curMs;
      sendPosStatus();
    }

    remM1 = targetPosM1 - currentPosM1;
    remM2 = targetPosM2 - currentPosM2;
    if (remM1 == 0 && remM2 == 0) {
      vTaskDelay(pdMS_TO_TICKS(1));
    } else if (curMs - lastWdtMs >= 100) {
      lastWdtMs = curMs;
      vTaskDelay(pdMS_TO_TICKS(1));
    } else {
      vTaskDelay(0);
    }
  }
}

void setup() {
  // [FIX 2] pinMode 이전에 ENA를 LOW로 선행 출력 → GPIO 플로팅 방지
  digitalWrite(M1_ENA, LOW);
  digitalWrite(M2_ENA, LOW);

  Serial.begin(115200);
  serialMutex = xSemaphoreCreateMutex();

  pinMode(M1_ENA, OUTPUT); pinMode(M1_DIR, OUTPUT); pinMode(M1_PUL, OUTPUT);
  pinMode(M2_ENA, OUTPUT); pinMode(M2_DIR, OUTPUT); pinMode(M2_PUL, OUTPUT);

  // pinMode 이후 ENA LOW 재확인
  digitalWrite(M1_ENA, LOW);
  digitalWrite(M2_ENA, LOW);
  digitalWrite(M1_PUL, HIGH);
  digitalWrite(M2_PUL, HIGH);

  lastStatusMs = millis();
  lastCmdMs    = millis();

  Serial.print("VER:"); Serial.println(FIRMWARE_VERSION);
  Serial.println("OK BOOT AI Vision Tracker ESP32 Ready");

  xTaskCreatePinnedToCore(serialTask, "serialTask", 4096, NULL, 1, &serialTaskHandle, 0);
  xTaskCreatePinnedToCore(motorTask,  "motorTask",  4096, NULL, 1, &motorTaskHandle,  1);
}

void loop() {
  vTaskDelay(pdMS_TO_TICKS(1000));
}

void stepMotors(unsigned long curUs, unsigned long curMs) {
  if (!motorsEnabled) return;

  // M1
  long remM1 = targetPosM1 - currentPosM1;
  if (remM1 != 0) {
    bool dir1 = (remM1 > 0) ^ M1_INVERT;
    digitalWrite(M1_DIR, dir1 ? HIGH : LOW);
    float jogLimitM1 = isJogging ? (abs(jogVx) * MAX_SPEED_LIMIT) : MAX_SPEED_LIMIT;
    if (jogLimitM1 < 8.0f) jogLimitM1 = 8.0f;
    float wallSpd1 = min(jogLimitM1, (float)abs(remM1) * 8.0f);
    if (wallSpd1 < 8.0f) wallSpd1 = 8.0f;

    if (curMs - lastAccelTimeM1 >= 1) {
      lastAccelTimeM1 = curMs;
      if (currentSpeedM1 < wallSpd1) {
        currentSpeedM1 += ACCELERATION_RATE;
        if (currentSpeedM1 > wallSpd1) currentSpeedM1 = wallSpd1;
      } else if (currentSpeedM1 > wallSpd1) {
        currentSpeedM1 -= ACCELERATION_RATE;
        if (currentSpeedM1 < wallSpd1) currentSpeedM1 = wallSpd1;
      }
    }

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
    float jogLimitM2 = isJogging ? (abs(jogVy) * MAX_SPEED_LIMIT) : MAX_SPEED_LIMIT;
    if (jogLimitM2 < 8.0f) jogLimitM2 = 8.0f;
    float wallSpd2 = min(jogLimitM2, (float)abs(remM2) * 8.0f);
    if (wallSpd2 < 8.0f) wallSpd2 = 8.0f;

    if (curMs - lastAccelTimeM2 >= 1) {
      lastAccelTimeM2 = curMs;
      if (currentSpeedM2 < wallSpd2) {
        currentSpeedM2 += ACCELERATION_RATE;
        if (currentSpeedM2 > wallSpd2) currentSpeedM2 = wallSpd2;
      } else if (currentSpeedM2 > wallSpd2) {
        currentSpeedM2 -= ACCELERATION_RATE;
        if (currentSpeedM2 < wallSpd2) currentSpeedM2 = wallSpd2;
      }
    }

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

  xSemaphoreTake(serialMutex, portMAX_DELAY);
  Serial.print("POS:"); Serial.print(pm1); Serial.print(":");
  Serial.print(pm2);    Serial.print(":");
  Serial.print((int)currentSpeedM1); Serial.print(":");
  Serial.println((int)currentSpeedM2);
  xSemaphoreGive(serialMutex);
}

void setTargetAngles(float angleM1, float angleM2) {
  if (angleM2 < -45.0f) angleM2 = -45.0f;
  if (angleM2 > 45.0f)  angleM2 = 45.0f;

  float limitM1 = 180.0f;
  if (angleM2 >= -45.0f && angleM2 <= -25.0f) {
    limitM1 = 85.0f;
  }

  if (angleM1 < -limitM1) angleM1 = -limitM1;
  if (angleM1 > limitM1)  angleM1 = limitM1;

  targetPosM1 = round(angleM1 * STEPS_PER_DEG_M1);
  targetPosM2 = round(angleM2 * STEPS_PER_DEG_M2);
}

void parseCommand(String cmd) {
  if (cmd.length() == 0) return;

  String upper = cmd;
  upper.toUpperCase();

  // S — 즉시 정지 (targetPos=currentPos, speed=0) 및 HALT 기능
  if (upper == "S") {
    targetPosM1 = currentPosM1;
    targetPosM2 = currentPosM2;
    currentSpeedM1 = 0.0f;
    currentSpeedM2 = 0.0f;
    lastCmdMs = millis();
    Serial.println("OK S");
    return;
  }

  // REL
  if (upper == "REL") {
    userReleased = true;
    releaseMotors();
    lastCmdMs = millis();
    Serial.println("OK REL");
    return;
  }

  // ENA / ENABLE
  if (upper == "ENA" || upper == "ENABLE") {
    targetPosM1 = currentPosM1;
    targetPosM2 = currentPosM2;
    currentSpeedM1 = 0.0f;
    currentSpeedM2 = 0.0f;
    enableMotors();
    lastCmdMs = millis();
    Serial.println("OK ENA");
    return;
  }

  // T:x:y
  if (upper.startsWith("T:")) {
    lastCmdMs = millis();
    userReleased = false;
    if (!motorsEnabled) enableMotors();

    int c1 = cmd.indexOf(':', 2);
    if (c1 < 0) return;
    int px = cmd.substring(2, c1).toInt();
    int py = cmd.substring(c1 + 1).toInt();

    float angleM1 = (currentPosM1 + (long)((px - CENTER_X) * STEPS_PER_PIX)) / STEPS_PER_DEG_M1;
    float angleM2 = (currentPosM2 + (long)((py - CENTER_Y) * STEPS_PER_PIX)) / STEPS_PER_DEG_M2;

    setTargetAngles(angleM1, angleM2);
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
    lastCmdMs = millis();
    if (!userReleased && !motorsEnabled) enableMotors();
    sendPosStatus();
    return;
  }

  // MODE (호환용)
  if (upper == "MODE:POS" || upper == "MODE:TRACK") {
    lastCmdMs = millis();
    Serial.print("OK "); Serial.println(upper);
    return;
  }

  // CFG
  if (upper.startsWith("CFG:")) {
    lastCmdMs = millis();
    if (!userReleased && !motorsEnabled) enableMotors();
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

  // JOG
  if (upper.startsWith("JOG ")) {
    lastCmdMs = millis();
    lastJogMs = millis();
    userReleased = false;
    if (!motorsEnabled) enableMotors();
    
    String args = cmd.substring(4); args.trim();
    int space = args.indexOf(' ');
    if (space > 0) {
      jogVx = args.substring(0, space).toFloat();
      jogVy = args.substring(space + 1).toFloat();
      if (abs(jogVx) < 0.01 && abs(jogVy) < 0.01) {
        isJogging = false;
        targetPosM1 = currentPosM1;
        targetPosM2 = currentPosM2;
        currentSpeedM1 = 0;
        currentSpeedM2 = 0;
      } else {
        isJogging = true;
      }
    }
    Serial.println("OK JOG");
    return;
  }

  // MOVE J
  if (upper.startsWith("MOVE J ")) {
    lastCmdMs = millis();
    userReleased = false;
    if (!motorsEnabled) enableMotors();

    String args  = cmd.substring(7); args.trim();
    String argsU = args; argsU.toUpperCase();
    int spaceIdx = args.lastIndexOf(' ');
    if (spaceIdx < 0) { Serial.println("ERROR: No value"); return; }
    float val = args.substring(spaceIdx + 1).toFloat();

    float targetAngleM1 = targetPosM1 / STEPS_PER_DEG_M1;
    float targetAngleM2 = targetPosM2 / STEPS_PER_DEG_M2;

    if (argsU.startsWith("XY ")) {
      String vals = args.substring(3); vals.trim();
      int space2 = vals.indexOf(' ');
      if (space2 > 0) {
        float v1 = vals.substring(0, space2).toFloat();
        float v2 = vals.substring(space2 + 1).toFloat();
        setTargetAngles(v1, v2);
        Serial.print("OK MOVE J XY "); Serial.print(v1); Serial.print(" "); Serial.println(v2);
      }
    } else if (argsU.startsWith("M1,M2") || argsU.startsWith("M1, M2")) {
      setTargetAngles(val, val);
      Serial.print("OK MOVE J M1,M2 "); Serial.println(val);
    } else if (argsU.startsWith("M1")) {
      setTargetAngles(val, targetAngleM2);
      Serial.print("OK MOVE J M1 "); Serial.println(val);
    } else if (argsU.startsWith("M2")) {
      setTargetAngles(targetAngleM1, val);
      Serial.print("OK MOVE J M2 "); Serial.println(val);
    } else {
      Serial.println("ERROR: Target must be M1, M2, or M1,M2");
    }
    return;
  }

  Serial.print("ERROR: Unknown command: "); Serial.println(cmd);
}
