import time

# ==========================================
# 물체 추적기 (위치 예측 포함)
# ==========================================

class Tracker:

    def __init__(self):
        self.last_pos = None
        self.last_time = None
        self.velocity = (0, 0)
        self.locked = False
        self.lost_count = 0
        self.max_lost = 15  # 이 프레임 수만큼 감지 실패 시 추적 해제
        self.smooth_factor = 0.6  # 위치 보간 계수 (높을수록 반응 빠름)

    def update(self, detection):
        """
        감지 결과를 받아서 추적 상태를 갱신하고,
        예측된 타겟 좌표를 반환합니다.
        """

        now = time.time()

        if detection:

            cx = detection["cx"]
            cy = detection["cy"]

            # 속도 벡터 계산
            if self.last_pos and self.last_time:
                dt = now - self.last_time
                if dt > 0:
                    vx = (cx - self.last_pos[0]) / dt
                    vy = (cy - self.last_pos[1]) / dt
                    # 속도 스무딩
                    self.velocity = (
                        self.velocity[0] * 0.3 + vx * 0.7,
                        self.velocity[1] * 0.3 + vy * 0.7
                    )

            self.last_pos = (cx, cy)
            self.last_time = now
            self.locked = True
            self.lost_count = 0

            return (cx, cy)

        else:
            # 감지 실패 → 예측 모드
            self.lost_count += 1

            if self.lost_count > self.max_lost:
                self.locked = False
                self.velocity = (0, 0)
                return None

            # 마지막 속도 벡터로 위치 예측
            if self.last_pos and self.last_time:
                dt = now - self.last_time
                px = self.last_pos[0] + self.velocity[0] * dt * 0.5
                py = self.last_pos[1] + self.velocity[1] * dt * 0.5

                px = max(0, min(639, px))
                py = max(0, min(479, py))

                return (int(px), int(py))

            return None

    def reset(self):
        """추적 상태 초기화"""
        self.last_pos = None
        self.last_time = None
        self.velocity = (0, 0)
        self.locked = False
        self.lost_count = 0
