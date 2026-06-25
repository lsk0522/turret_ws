import cv2
import os
import threading
import numpy as np
import time

import state

# 학습 영역: 640x480 프레임 중앙 300x300
_DEFAULT_LEARN_ZONE = (170, 90, 300, 300)   # (x, y, w, h)

# ── 헬퍼: 피부색 마스크 (YCrCb — 조명 변화에 강함) ──────
def _skin_mask(img):
    """피부색 픽셀 = 255, 그 외 = 0. 손을 제거하기 위해 사용."""
    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    mask = cv2.inRange(ycrcb, np.array((0, 133, 77), dtype=np.uint8), np.array((255, 173, 127), dtype=np.uint8))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    return cv2.dilate(mask, kernel, iterations=2)   # 여유 있게 확장

# ── 헬퍼: 프레임 차분 모션 마스크 ────────────────────────
def _motion_mask(frame, prev_frame):
    diff = cv2.absdiff(
        cv2.cvtColor(frame,      cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY),
    )
    _, mask = cv2.threshold(diff, 15, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    return cv2.dilate(mask, kernel, iterations=2)

# ── 칼만 필터 ────────────────────────────────────────────
class KalmanTracker:
    def __init__(self):
        self.kf = cv2.KalmanFilter(4, 2)
        self.kf.measurementMatrix = np.array([
            [1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
        self.kf.transitionMatrix = np.array([
            [1, 0, 1, 0], [0, 1, 0, 1],
            [0, 0, 1, 0], [0, 0, 0, 1]], np.float32)
        self.kf.processNoiseCov     = np.eye(4, dtype=np.float32) * 5.0
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 1.0
        self.kf.errorCovPost        = np.eye(4, dtype=np.float32) * 10.0
        self.initialized = False
        self.lost = 0
        self.MAX_LOST = 20

    def update(self, cx, cy):
        m = np.array([[np.float32(cx)], [np.float32(cy)]])
        if not self.initialized:
            self.kf.statePost = np.array(
                [[np.float32(cx)], [np.float32(cy)], [0.0], [0.0]], np.float32)
            self.initialized = True
        self.kf.correct(m)
        self.lost = 0
        p = self.kf.predict()
        return int(p[0][0]), int(p[1][0])

    def predict_next(self):
        if not self.initialized:
            return None
        self.lost += 1
        if self.lost > self.MAX_LOST:
            self.initialized = False
            return None
        p = self.kf.predict()
        return int(p[0][0]), int(p[1][0])

    def reset(self):
        self.initialized = False
        self.lost = 0

# ── CSRT 트래커 (최신 AI 트래커) ──────────────────────────
class CSRTTracker:
    def __init__(self):
        self.tracker = None
        self.active = False
        self.learning = False
        self.learn_zone: tuple[int,int,int,int] = (170, 90, 300, 300)  # (x,y,w,h)
        self.template = None
        self._start: float = 0.0
        self.load_saved_data()

    @property
    def progress(self):
        # 학습 모달을 즉시 완료시키기 위해 100 반환
        return 100

    def load_saved_data(self):
        import os
        folder = "learning_data"
        zone_path = os.path.join(folder, "learn_zone.txt")
        if os.path.exists(zone_path):
            try:
                with open(zone_path, "r") as f:
                    coords = [int(v) for v in f.read().strip().split(",")]
                    if len(coords) == 4:
                        self.learn_zone = (coords[0], coords[1], coords[2], coords[3])
            except Exception as e:
                pass

    def start_learning(self, n_samples=20):
        # 15초 학습 과정을 생략하고 즉시 트래커 초기화
        import state
        frame = state.current_frame
        if frame is None:
            state.learning_failed = True
            return

        x, y, w, h = self.learn_zone
        img_h, img_w = frame.shape[0], frame.shape[1]
        x1 = max(0, min(img_w - 1, x))
        y1 = max(0, min(img_h - 1, y))
        x2 = max(0, min(img_w, x + w))
        y2 = max(0, min(img_h, y + h))
        w = x2 - x1
        h = y2 - y1

        if w <= 0 or h <= 0:
            state.learning_failed = True
            return

        # ── 배경 및 손 제거를 통한 BBox 자동 정밀 보정 ──
        roi = frame[y1:y2, x1:x2]
        skin = _skin_mask(roi)
        no_skin = cv2.bitwise_not(skin)
        
        # Canny Edge로 객체의 윤곽 파악 (배경 무시)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 150)
        
        # 손이 아니면서 엣지가 있는 부분
        obj_mask = cv2.bitwise_and(edges, no_skin)
        
        # 객체 덩어리 생성
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        obj_mask = cv2.morphologyEx(obj_mask, cv2.MORPH_CLOSE, kernel)
        obj_mask = cv2.dilate(obj_mask, kernel, iterations=2)
        
        contours, _ = cv2.findContours(obj_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            rx, ry, rw, rh = cv2.boundingRect(c)
            # 노이즈가 아닌 유의미한 객체 크기라면 bbox 정밀 갱신
            if rw > 15 and rh > 15:
                pad_x = 5
                pad_y = 5
                new_x1 = max(x1, x1 + rx - pad_x)
                new_y1 = max(y1, y1 + ry - pad_y)
                new_x2 = min(x2, x1 + rx + rw + pad_x*2)
                new_y2 = min(y2, y1 + ry + rh + pad_y*2)
                
                # 만약 정밀 갱신된 박스가 유효하면 적용
                if new_x2 > new_x1 and new_y2 > new_y1:
                    x1, y1 = new_x1, new_y1
                    w = new_x2 - new_x1
                    h = new_y2 - new_y1

        try:
            self.active = False # 진행 중인 track() 메서드 충돌 방지
            
            # 전역 템플릿 탐색 복구를 위한 원본 템플릿 저장
            self.template = frame[y1:y1+h, x1:x1+w].copy()
            
            self.tracker = getattr(cv2, 'TrackerCSRT_create')()  # type: ignore
            self.tracker.init(frame, (x1, y1, w, h))
            self.active = True
            self.learning = False
            state.learning_failed = False
            state.tracking_mode = "custom"
            self.learn_zone = (x1, y1, w, h) # UI 썸네일을 위해 존 갱신
            self._save_thumbnail()
            
            # learn_zone 저장
            import os
            os.makedirs("learning_data", exist_ok=True)
            with open("learning_data/learn_zone.txt", "w") as f:
                f.write(f"{self.learn_zone[0]},{self.learn_zone[1]},{self.learn_zone[2]},{self.learn_zone[3]}")
                
        except Exception as e:
            print(f"[CSRTTracker] Error init: {e}")
            state.learning_failed = True
            self.active = False

    def process_frame(self, frame, prev_frame=None):
        pass

    def _finish(self):
        pass

    def _save_thumbnail(self):
        frame = state.current_frame
        if frame is None:
            return
        x, y, w, h = self.learn_zone
        img_h, img_w = frame.shape[0], frame.shape[1]
        x1 = max(0, min(img_w - 1, x))
        y1 = max(0, min(img_h - 1, y))
        x2 = max(0, min(img_w, x + w))
        y2 = max(0, min(img_h, y + h))
        if x2 > x1 and y2 > y1:
            roi = frame[y1:y2, x1:x2]
            import os
            os.makedirs("learning_data", exist_ok=True)
            try:
                cv2.imwrite("learning_data/target_thumbnail.jpg", roi, [cv2.IMWRITE_JPEG_QUALITY, 82])
            except Exception:
                pass

    def track(self, frame, motion=None):
        if not self.active or self.tracker is None:
            return None

        ok, bbox = self.tracker.update(frame)
        
        # ── Competitive Tracking (경쟁적 템플릿 매칭 복구 알고리즘) ──
        # 트래커가 평소처럼 추적 중일 때, 전역 탐색에서 "월등히 더 좋은" 일치 항목을 찾으면 거기로 점프합니다.
        # 이 방식은 가장자리 여부와 무관하게 작동하며, 정상 추적 중일 때는 점프하지 않아 매우 안정적입니다.
        if self.template is not None and self.template.shape[0] > 0 and self.template.shape[1] > 0:
            res = cv2.matchTemplate(frame, self.template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val > 0.65: # 전역 탐색에서 상당히 비슷한 물체 발견
                new_tx, new_ty = max_loc
                new_cx = new_tx + self.template.shape[1] // 2
                new_cy = new_ty + self.template.shape[0] // 2
                
                jump = False
                if ok:
                    tx, ty, tw, th = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                    cx = tx + tw // 2
                    cy = ty + th // 2
                    dist = ((cx - new_cx)**2 + (cy - new_cy)**2)**0.5
                    
                    if dist > 50: # 현재 추적 중인 곳과 거리가 꽤 멀다면
                        # 현재 추적 중인 곳의 점수 계산
                        pad = 10
                        rx1, ry1 = max(0, tx - pad), max(0, ty - pad)
                        rx2, ry2 = min(frame.shape[1], tx + tw + pad), min(frame.shape[0], ty + th + pad)
                        roi = frame[ry1:ry2, rx1:rx2]
                        
                        current_score = 0
                        if roi.shape[0] >= self.template.shape[0] and roi.shape[1] >= self.template.shape[1]:
                            res_roi = cv2.matchTemplate(roi, self.template, cv2.TM_CCOEFF_NORMED)
                            _, current_score, _, _ = cv2.minMaxLoc(res_roi)
                        
                        # 전역에서 찾은 점수가 현재 추적 중인 점수보다 월등히(0.15 이상) 높다면,
                        # 이는 트래커가 엉뚱한 배경을 추적 중이고 진짜 물체가 딴 곳에 나타났다는 뜻!
                        if max_val > current_score + 0.15:
                            jump = True
                            print(f"[CSRT] Competitive jump! cur_score={current_score:.2f}, new_score={max_val:.2f}, dist={dist:.0f}")
                else:
                    jump = True # 트래커가 아예 끊겼을 경우 즉시 점프
                    
                if jump:
                    tw, th = self.template.shape[1], self.template.shape[0]
                    new_bbox = (new_tx, new_ty, tw, th)
                    self.tracker = getattr(cv2, 'TrackerCSRT_create')()  # type: ignore
                    self.tracker.init(frame, new_bbox)
                    bbox = new_bbox
                    ok = True

        if not ok:
            return None

        x, y, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        cx = x + w // 2
        cy = y + h // 2
        
        # 바운딩 박스 화면 이탈 방지
        frame_h, frame_w = frame.shape[:2]
        x = max(0, min(frame_w - 1, x))
        y = max(0, min(frame_h - 1, y))
        
        return {
            "cx": cx, "cy": cy,
            "x": x, "y": y, "w": w, "h": h,
            "matches": 100, "predicted": False
        }

    def reset(self):
        self.active = False
        self.learning = False
        self.tracker = None

# ── Hough Circle 폴백 (흰 공 등 원형 물체) ────────────────
class CircleDetector:
    """ORB 실패 시 폴백. 형태만 보므로 흰 공 ↔ 흰 배경도 감지 가능."""

    def detect(self, frame, motion=None):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 모션 영역만 사용 (배경 원형 노이즈 방지)
        search = gray
        if motion is not None and cv2.countNonZero(motion) > 200:
            search = cv2.bitwise_and(gray, gray, mask=motion)

        blurred = cv2.GaussianBlur(search, (9, 9), 2)

        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1, minDist=40,
            param1=60, param2=18,
            minRadius=12, maxRadius=130,
        )
        if circles is None:
            return None

        circles = np.round(circles[0]).astype(int)

        # 피부색 중심 원 제외 (손가락 끝 등)
        skin = _skin_mask(frame)
        best = None
        best_r = 0
        for cx, cy, r in circles:
            if 0 <= cy < frame.shape[0] and 0 <= cx < frame.shape[1]:
                if skin[cy, cx]:      # 중심이 피부색 → 손 가능성, 스킵
                    continue
                if r > best_r:
                    best_r = r
                    best = (cx, cy, r)

        if best is None:
            return None

        cx, cy, r = best
        return {
            "cx": int(cx), "cy": int(cy),
            "x": int(cx - r), "y": int(cy - r),
            "w": int(2 * r), "h": int(2 * r),
            "predicted": False,
            "detector": "hough",
        }

# ── 모듈 인스턴스 ────────────────────────────────────────
_csrt   = CSRTTracker()
_circle = CircleDetector()
_kalman = KalmanTracker()
_thread = None

def get_learning_progress():
    return _csrt.progress

def reset_tracker():
    _csrt.reset()
    _kalman.reset()
    state.ball = None
    state.ball_lost = False
    state.learning_progress = 0

# ── 메인 루프 ────────────────────────────────────────────
def _run():
    last_id    = None
    prev_frame = None
    frame      = None

    while True:
        try:
            frame = state.current_frame
            if frame is None:
                time.sleep(0.01)
                continue

            # ── 학습 중 (CSRT에서는 즉시 완료됨) ─────────────────────────────────────
            if _csrt.learning:
                pass

            frame_id = id(frame)
            if frame_id == last_id:
                time.sleep(0.005)
                continue
            last_id = frame_id

            # ── 추적 ────────────────────────────────────────
            ball = None
            motion = None

            # 수동 모드일 때는 무거운 모션 마스크 및 트래킹을 생략 (단, 학습 중이 아닐 때)
            if state.control_mode == 'auto' or _csrt.learning:
                motion = _motion_mask(frame, prev_frame) if prev_frame is not None else None
                prev_frame = frame.copy()

                # 1) CSRT AI 트래커
                if _csrt.active:
                    ball = _csrt.track(frame, motion)

                # 2) ORB 실패 → Hough Circle (흰 공 등 원형 물체 대응)
                if ball is None and motion is not None:
                    ball = _circle.detect(frame, motion)
            else:
                # 수동 모드 최적화: prev_frame만 최소한으로 유지
                if prev_frame is None:
                    prev_frame = frame.copy()

            # ── 칼만 갱신 ────────────────────────────────────
            if ball:
                px, py = _kalman.update(ball["cx"], ball["cy"])
                ball["predicted_cx"] = px
                ball["predicted_cy"] = py
                state.ball      = ball
                state.ball_lost = False
            elif _csrt.active:
                pred = _kalman.predict_next()
                state.ball_lost = True
                state.ball = (
                    {"cx": pred[0], "cy": pred[1], "predicted": True}
                    if pred else None
                )
            else:
                state.ball      = None
                state.ball_lost = False
                
        except Exception as e:
            print(f"[Detector] Exception in _run loop: {e}")
            time.sleep(0.1)

        # ── 자동 모드: 조준점 갱신 ───────────────────────
        if state.control_mode == "auto" and state.ball and frame is not None:
            tx = state.ball.get("predicted_cx", state.ball["cx"])
            ty = state.ball.get("predicted_cy", state.ball["cy"])
            frame_h = frame.shape[0]
            frame_w = frame.shape[1]
            center_x = frame_w / 2
            center_y = frame_h / 2
            # P-Controller: 현재 모터 좌표(state.point)에서 프레임 중앙 기준 오차만큼 부드럽게 이동
            err_x = tx - center_x
            err_y = ty - center_y
            
            # P-gain 설정 (0.1 ~ 0.5): 높을수록 빨리, 낮을수록 부드럽게
            p_gain_x = 0.15
            p_gain_y = 0.10
            
            new_x = state.point[0] + (err_x * p_gain_x)
            new_y = state.point[1] + (err_y * p_gain_y)
            
            state.point[0] = max(0, min(frame_w - 1, int(new_x)))
            state.point[1] = max(0, min(frame_h - 1, int(new_y)))

def start():
    global _thread
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()

def set_learn_zone(x, y, w, h):
    _csrt.learn_zone = (int(x), int(y), int(w), int(h))

def get_learn_zone():
    return getattr(_csrt, 'learn_zone', _DEFAULT_LEARN_ZONE)

def start_learning(n_samples=20):
    _csrt.start_learning()
    _kalman.reset()
    state.ball = None
    state.ball_lost = False
    state.learning_progress = 0
