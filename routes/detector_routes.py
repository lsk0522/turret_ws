"""검출·학습·갤러리 라우트."""
import os
import base64
import cv2
from flask import Blueprint, request, jsonify, send_from_directory
import state

bp = Blueprint('detector', __name__)


# ── 갤러리 ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# routes is a subdirectory, so we go up one level
PROJECT_DIR = os.path.dirname(BASE_DIR)
PICTURE_DIR = os.path.join(PROJECT_DIR, "picture")

@bp.route('/captures')
def list_captures():
    folder = PICTURE_DIR
    if not os.path.exists(folder):
        return jsonify([])
    try:
        files = [f for f in os.listdir(folder)
                 if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(folder, x)), reverse=True)
        return jsonify(files)
    except Exception:
        return jsonify([])


@bp.route('/picture/<path:filename>')
def serve_picture(filename):
    import os
    from flask import send_from_directory
    pic_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'picture')
    return send_from_directory(pic_dir, filename)


@bp.route('/delete/<path:filename>')
def delete_picture(filename):
    import os
    pic_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'picture')
    file_path = os.path.join(pic_dir, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "error", "message": "File not found"}), 404


# ── 추적 상태 ─────────────────────────────────────────────
@bp.route('/ball')
def ball():
    if state.ball is None:
        return jsonify(detected=False)
    return jsonify(detected=True, lost=state.ball_lost, **state.ball)


@bp.route('/tracking_status')
def tracking_status():
    locked = (state.ball is not None and not state.ball_lost
              and state.tracking_mode == "custom")
    return jsonify(
        locked=locked,
        detected=(state.ball is not None),
        tracking_mode=state.tracking_mode,
        control_mode=state.control_mode,
    )


# ── ORB 학습 ─────────────────────────────────────────────
@bp.route('/start_learning')
def start_learning():
    import detector as det
    det.start_learning()
    state.tracking_mode = "custom"
    return "OK"


@bp.route('/learning_progress')
def learning_progress():
    import detector as det
    prog = det.get_learning_progress()
    # 썸네일은 학습 완료 시 detector._finish()에서 파일로 저장됨.
    # 여기서는 저장된 파일의 base64만 1회 읽어서 반환 (재인코딩 없음).
    thumb = None
    if prog == 100:
        thumb_path = os.path.join("learning_data", "target_thumbnail.jpg")
        if os.path.exists(thumb_path):
            try:
                with open(thumb_path, 'rb') as f:
                    thumb = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
            except Exception:
                pass
    return jsonify(progress=prog, done=(prog == 100),
                   thumbnail=thumb, failed=state.learning_failed)


@bp.route('/target_thumbnail')
def target_thumbnail():
    return send_from_directory('learning_data', 'target_thumbnail.jpg')


@bp.route('/clear_target')
def clear_target():
    import detector as det
    det.reset_tracker()
    state.tracking_mode = "none"
    thumb_path = os.path.join("learning_data", "target_thumbnail.jpg")
    if os.path.exists(thumb_path):
        try:
            os.remove(thumb_path)
        except Exception:
            pass
    return "OK"


# ── 학습 영역 ─────────────────────────────────────────────
@bp.route('/set_learn_zone')
def set_learn_zone():
    import detector as det
    x = int(float(request.args.get('x', 170)))
    y = int(float(request.args.get('y', 90)))
    w = int(float(request.args.get('w', 300)))
    h = int(float(request.args.get('h', 300)))
    det.set_learn_zone(x, y, w, h)
    return jsonify(x=x, y=y, w=w, h=h)


@bp.route('/get_learn_zone')
def get_learn_zone():
    import detector as det
    x, y, w, h = det.get_learn_zone()
    return jsonify(x=x, y=y, w=w, h=h)


@bp.route('/add_learning')
def add_learning():
    import detector as det
    n = int(request.args.get('n', 20))
    det.start_learning(n_samples=n)
    return "OK"
