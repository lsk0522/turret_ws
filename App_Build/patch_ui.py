import paramiko

PI_HOST = "172.30.14.31"
PI_USER = "pi30306"
PI_PASS = "12345678"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)
sftp = ssh.open_sftp()

def run(cmd):
    _, stdout, _ = ssh.exec_command(cmd)
    return stdout.read().decode()

# ── 현재 index.html 읽기 ────────────────────────────────
html = run("cat /home/pi30306/turret_ws/templates/index.html")

# ── 1. 학습 완료 후 "더 학습할까요?" 모달 HTML 추가 ────
MORE_LEARNING_MODAL = '''
    <!-- ====== 추가 학습 확인 모달 (지문인식 스타일) ====== -->
    <div id="more-learn-modal" class="ios-modal-backdrop" style="display:none;">
        <div class="ios-modal-panel" style="max-width:340px; text-align:center; padding: 0 0 24px 0;">
            <div class="ios-modal-header" style="justify-content:center; border-bottom: 1px solid rgba(255,255,255,0.08);">
                <span>학습 완료</span>
            </div>
            <div style="padding: 20px 24px 8px;">
                <!-- 썸네일 -->
                <div id="more-learn-thumb-wrap" style="width:120px;height:90px;border-radius:12px;overflow:hidden;margin:0 auto 16px;background:rgba(255,255,255,0.06);display:flex;align-items:center;justify-content:center;">
                    <img id="more-learn-thumb" src="" alt="학습된 타겟" style="width:100%;height:100%;object-fit:cover;display:none;">
                    <svg id="more-learn-thumb-icon" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.3)" stroke-width="1.5" style="width:32px;height:32px;">
                        <circle cx="12" cy="12" r="10"></circle><path d="M12 8v4l3 3"></path>
                    </svg>
                </div>
                <div id="more-learn-count" style="font-size:13px;color:rgba(255,255,255,0.5);margin-bottom:8px;">1회 학습 완료</div>
                <div style="font-size:15px;font-weight:600;color:#fff;margin-bottom:6px;">더 학습할까요?</div>
                <div style="font-size:13px;color:rgba(255,255,255,0.5);line-height:1.5;">
                    학습을 반복할수록 인식률이 높아집니다.<br>지문인식처럼 다양한 각도에서 추가하세요.
                </div>
                <!-- 학습 횟수 프로그레스 바 (지문인식 스타일) -->
                <div id="more-learn-dots" style="display:flex;gap:8px;justify-content:center;margin-top:16px;">
                    <!-- JS로 동적 생성 -->
                </div>
            </div>
            <div style="display:flex;flex-direction:column;gap:10px;padding: 0 24px;">
                <button id="btn-more-learn" style="background:rgba(0,122,255,0.85);border:none;border-radius:12px;color:#fff;font-size:16px;font-weight:600;padding:14px;cursor:pointer;transition:opacity 0.2s;">
                    📸 더 학습하기
                </button>
                <button id="btn-finish-learn" style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);border-radius:12px;color:#fff;font-size:16px;font-weight:500;padding:14px;cursor:pointer;transition:opacity 0.2s;">
                    ✓ 완료
                </button>
            </div>
        </div>
    </div>

    <!-- ====== ROI 드래그 선택 오버레이 ====== -->
    <div id="roi-select-overlay" style="display:none;position:absolute;top:0;left:0;width:100%;height:100%;z-index:50;cursor:crosshair;touch-action:none;">
        <!-- 반투명 배경 (선택 영역 밖) -->
        <canvas id="roi-select-canvas" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;"></canvas>
        <!-- 안내 배너 -->
        <div id="roi-instruction-banner" style="position:absolute;top:72px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.7);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.15);border-radius:20px;padding:10px 20px;color:#fff;font-size:13px;font-weight:500;white-space:nowrap;pointer-events:none;">
            📦 학습할 물체에 네모칸을 그려주세요
        </div>
        <!-- 선택 확인 버튼 (박스 그린 후 표시) -->
        <div id="roi-confirm-btns" style="display:none;position:absolute;bottom:110px;left:50%;transform:translateX(-50%);display:flex;gap:12px;pointer-events:auto;">
            <button id="btn-roi-cancel" style="background:rgba(255,59,48,0.85);border:none;border-radius:14px;color:#fff;font-size:14px;font-weight:600;padding:12px 20px;cursor:pointer;">취소</button>
            <button id="btn-roi-confirm" style="background:rgba(0,122,255,0.9);border:none;border-radius:14px;color:#fff;font-size:14px;font-weight:600;padding:12px 20px;cursor:pointer;">📸 이 영역 학습</button>
        </div>
    </div>
'''

# learn-overlay 바로 앞에 삽입
if 'more-learn-modal' in html:
    print("더 학습 모달: 이미 있음 → 스킵")
else:
    html = html.replace(
        '<!-- 학습 모드 오버레이',
        MORE_LEARNING_MODAL + '\n    <!-- 학습 모드 오버레이'
    )
    print("✅ 더 학습 모달 + ROI 오버레이 삽입")

with sftp.open('/home/pi30306/turret_ws/templates/index.html', 'w') as f:
    f.write(html)
print("✅ index.html 저장 완료")

# ── 2. script.js 패치: 학습 완료 후 더 학습 모달 + ROI 드래그 ──
js = run("cat /home/pi30306/turret_ws/static/script.js")

# (A) ROI 드래그 코드 & 더학습 모달 코드가 없으면 추가
ROI_AND_MORE_LEARN_JS = r"""

/* ==========================================
   ROI 드래그 선택 (학습 영역 지정)
   ========================================== */
const roiOverlay       = document.getElementById("roi-select-overlay");
const roiCanvas        = document.getElementById("roi-select-canvas");
const roiInstrBanner   = document.getElementById("roi-instruction-banner");
const roiConfirmBtns   = document.getElementById("roi-confirm-btns");
const btnRoiCancel     = document.getElementById("btn-roi-cancel");
const btnRoiConfirm    = document.getElementById("btn-roi-confirm");

let _roiDragging = false;
let _roiStartX = 0, _roiStartY = 0;
let _roiRect   = null;   // {x,y,w,h} in 640x480 coords

function _getVideoCoords(clientX, clientY) {
    const vid = document.getElementById("video");
    const rect = vid.getBoundingClientRect();
    const scaleX = 640 / rect.width;
    const scaleY = 480 / rect.height;
    return {
        x: Math.round((clientX - rect.left) * scaleX),
        y: Math.round((clientY - rect.top)  * scaleY)
    };
}

function _drawROICanvas(x1, y1, x2, y2) {
    const c = roiCanvas;
    const ctx = c.getContext("2d");
    c.width  = c.offsetWidth;
    c.height = c.offsetHeight;

    const vid = document.getElementById("video");
    const vr  = vid.getBoundingClientRect();
    const scaleX = vr.width  / 640;
    const scaleY = vr.height / 480;

    const sx = Math.min(x1, x2) * scaleX;
    const sy = Math.min(y1, y2) * scaleY;
    const sw = Math.abs(x2 - x1) * scaleX;
    const sh = Math.abs(y2 - y1) * scaleY;

    ctx.clearRect(0, 0, c.width, c.height);

    // 어두운 배경
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(0, 0, c.width, c.height);

    // 선택 영역은 밝게
    ctx.clearRect(sx, sy, sw, sh);

    // 테두리
    ctx.strokeStyle = "#007aff";
    ctx.lineWidth   = 2.5;
    ctx.shadowColor = "rgba(0,122,255,0.8)";
    ctx.shadowBlur  = 8;
    ctx.strokeRect(sx, sy, sw, sh);

    // 코너 핸들
    const cLen = 14;
    ctx.strokeStyle = "#fff";
    ctx.lineWidth   = 3;
    ctx.shadowBlur  = 0;
    [[sx,sy],[sx+sw,sy],[sx,sy+sh],[sx+sw,sy+sh]].forEach(([cx,cy]) => {
        const dx = cx < sx + sw/2 ? 1 : -1;
        const dy = cy < sy + sh/2 ? 1 : -1;
        ctx.beginPath();
        ctx.moveTo(cx, cy); ctx.lineTo(cx + dx*cLen, cy);
        ctx.moveTo(cx, cy); ctx.lineTo(cx, cy + dy*cLen);
        ctx.stroke();
    });

    // 중앙 치수 표시
    const wPx = Math.abs(x2 - x1), hPx = Math.abs(y2 - y1);
    if (wPx > 30 && hPx > 30) {
        ctx.fillStyle = "rgba(0,0,0,0.6)";
        const label = `${wPx} × ${hPx}`;
        ctx.font = "bold 12px Inter, sans-serif";
        const tw = ctx.measureText(label).width;
        const lx = sx + sw/2 - tw/2 - 6;
        const ly = sy + sh/2 - 10;
        ctx.fillRect(lx, ly, tw + 12, 20);
        ctx.fillStyle = "#fff";
        ctx.fillText(label, lx + 6, ly + 14);
    }
}

function openROISelect() {
    roiOverlay.style.display = "block";
    roiConfirmBtns.style.display = "none";
    const c = roiCanvas;
    const ctx = c.getContext("2d");
    c.width  = c.offsetWidth;
    c.height = c.offsetHeight;
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.font = "15px Inter, sans-serif";
    ctx.fillStyle = "rgba(255,255,255,0.6)";
    ctx.textAlign = "center";
    ctx.fillText("화면에 드래그하여 영역을 선택하세요", c.width/2, c.height/2);
}

function closeROISelect() {
    roiOverlay.style.display = "none";
    _roiRect = null;
}

// 마우스 드래그
roiOverlay.addEventListener("mousedown", e => {
    const p = _getVideoCoords(e.clientX, e.clientY);
    _roiDragging = true;
    _roiStartX = p.x; _roiStartY = p.y;
    roiConfirmBtns.style.display = "none";
});
roiOverlay.addEventListener("mousemove", e => {
    if (!_roiDragging) return;
    const p = _getVideoCoords(e.clientX, e.clientY);
    _drawROICanvas(_roiStartX, _roiStartY, p.x, p.y);
});
roiOverlay.addEventListener("mouseup", e => {
    if (!_roiDragging) return;
    _roiDragging = false;
    const p = _getVideoCoords(e.clientX, e.clientY);
    const x = Math.min(_roiStartX, p.x);
    const y = Math.min(_roiStartY, p.y);
    const w = Math.abs(p.x - _roiStartX);
    const h = Math.abs(p.y - _roiStartY);
    if (w > 20 && h > 20) {
        _roiRect = {x, y, w, h};
        roiConfirmBtns.style.display = "flex";
    }
});

// 터치 지원
roiOverlay.addEventListener("touchstart", e => {
    e.preventDefault();
    const t = e.touches[0];
    const p = _getVideoCoords(t.clientX, t.clientY);
    _roiDragging = true;
    _roiStartX = p.x; _roiStartY = p.y;
    roiConfirmBtns.style.display = "none";
}, {passive: false});
roiOverlay.addEventListener("touchmove", e => {
    e.preventDefault();
    if (!_roiDragging) return;
    const t = e.touches[0];
    const p = _getVideoCoords(t.clientX, t.clientY);
    _drawROICanvas(_roiStartX, _roiStartY, p.x, p.y);
}, {passive: false});
roiOverlay.addEventListener("touchend", e => {
    if (!_roiDragging) return;
    _roiDragging = false;
    const t = e.changedTouches[0];
    const p = _getVideoCoords(t.clientX, t.clientY);
    const x = Math.min(_roiStartX, p.x);
    const y = Math.min(_roiStartY, p.y);
    const w = Math.abs(p.x - _roiStartX);
    const h = Math.abs(p.y - _roiStartY);
    if (w > 20 && h > 20) {
        _roiRect = {x, y, w, h};
        roiConfirmBtns.style.display = "flex";
    }
});

btnRoiCancel.addEventListener("click", closeROISelect);

btnRoiConfirm.addEventListener("click", async () => {
    if (!_roiRect) return;
    const {x, y, w, h} = _roiRect;
    // 서버에 ROI 전송
    await fetch(`/set_learn_zone?x=${x}&y=${y}&w=${w}&h=${h}`);
    closeROISelect();
    // 학습 시작
    startLearningSession();
});

/* ==========================================
   지문인식 스타일 반복 학습
   ========================================== */
const moreLearnModal   = document.getElementById("more-learn-modal");
const moreLearnThumb   = document.getElementById("more-learn-thumb");
const moreLearnThumbIcon = document.getElementById("more-learn-thumb-icon");
const moreLearnCount   = document.getElementById("more-learn-count");
const moreLearnDots    = document.getElementById("more-learn-dots");
const btnMoreLearn     = document.getElementById("btn-more-learn");
const btnFinishLearn   = document.getElementById("btn-finish-learn");

let _learnSessionCount = 0;
const MAX_LEARN_DOTS = 5;

function _renderLearnDots(count) {
    if (!moreLearnDots) return;
    moreLearnDots.innerHTML = "";
    for (let i = 0; i < MAX_LEARN_DOTS; i++) {
        const dot = document.createElement("div");
        dot.style.cssText = `
            width: 10px; height: 10px; border-radius: 50%;
            background: ${i < count ? "#30d158" : "rgba(255,255,255,0.2)"};
            transition: background 0.4s ease;
            ${i < count ? "box-shadow: 0 0 6px rgba(48,209,88,0.6);" : ""}
        `;
        moreLearnDots.appendChild(dot);
    }
}

function showMoreLearnModal(thumbnail) {
    _learnSessionCount++;
    if (moreLearnModal) {
        if (thumbnail) {
            moreLearnThumb.src = thumbnail;
            moreLearnThumb.style.display = "block";
            moreLearnThumbIcon.style.display = "none";
        }
        moreLearnCount.textContent = `${_learnSessionCount}회 학습 완료`;
        _renderLearnDots(_learnSessionCount);
        moreLearnModal.style.display = "flex";
    }
}

function hideMoreLearnModal() {
    if (moreLearnModal) moreLearnModal.style.display = "none";
}

btnMoreLearn && btnMoreLearn.addEventListener("click", () => {
    hideMoreLearnModal();
    // 추가 학습 시작 (ROI는 유지, 서버에서 기존 zone 재사용)
    fetch("/add_learning?n=20");
    startLearningFromServer();
});

btnFinishLearn && btnFinishLearn.addEventListener("click", () => {
    hideMoreLearnModal();
    _learnSessionCount = 0;
});

/* ==========================================
   학습 시작 함수 (ROI 선택 → 학습 → 완료 → 더학습 모달)
   ========================================== */

// 기존 "학습 시작" 버튼에 ROI 선택 모드를 연결
const btnStartLearnOld = document.getElementById("btn-start-learn");
if (btnStartLearnOld) {
    // 기존 이벤트 제거 후 ROI 선택으로 변경
    const newBtn = btnStartLearnOld.cloneNode(true);
    btnStartLearnOld.parentNode.replaceChild(newBtn, btnStartLearnOld);
    newBtn.addEventListener("click", () => {
        _learnSessionCount = 0;
        openROISelect();
    });
}

function startLearningSession() {
    // 실제 학습 시작 (서버 호출)
    fetch("/start_learning").catch(() => {});
    startLearningFromServer();
}

function startLearningFromServer() {
    // 기존 learnOverlay 표시 로직 재활용 (있으면)
    const learnOverlay = document.getElementById("learn-overlay");
    if (learnOverlay) learnOverlay.style.display = "flex";
    const learnFill = document.getElementById("learn-progress-fill");
    const learnPct  = document.getElementById("learn-pct");
    const learnBannerTxt = document.getElementById("learn-banner-txt");

    if (learnBannerTxt) learnBannerTxt.textContent = "📸 학습 중... 물체를 다양한 각도에서 보여주세요";
    if (learnFill) learnFill.style.width = "0%";
    if (learnPct)  learnPct.textContent  = "0%";

    const poll = setInterval(async () => {
        try {
            const res  = await fetch("/learning_progress");
            const data = await res.json();
            if (learnFill) learnFill.style.width = data.progress + "%";
            if (learnPct)  learnPct.textContent  = data.progress + "%";

            if (data.done) {
                clearInterval(poll);
                if (learnOverlay) learnOverlay.style.display = "none";
                // 지문인식 스타일: 더 학습 모달 표시
                showMoreLearnModal(data.thumbnail);
            }
        } catch(e) { clearInterval(poll); }
    }, 200);
}

/* ==========================================
   연결 상태 실시간 표시 (ESP32 / Arduino)
   ========================================== */

const deviceStatusDot   = document.getElementById("device-status-dot");
const deviceStatusLabel = document.getElementById("device-status-label");
const deviceParamApplied = document.getElementById("device-param-status");

async function pollDeviceStatus() {
    try {
        const res = await fetch("/device_status");
        const d   = await res.json();

        // 헤더 연결 상태 점 표시
        if (deviceStatusDot) {
            deviceStatusDot.style.background = d.connected ? "#30d158" : "#ff453a";
            deviceStatusDot.style.boxShadow  = d.connected
                ? "0 0 6px rgba(48,209,88,0.7)"
                : "0 0 6px rgba(255,69,58,0.5)";
        }
        if (deviceStatusLabel) {
            deviceStatusLabel.textContent = d.connected
                ? `${d.device_type.toUpperCase()} 연결됨`
                : "연결 안됨";
            deviceStatusLabel.style.color = d.connected ? "#30d158" : "#ff453a";
        }

        // 파라미터 적용 가능 여부
        const applyBtn = document.getElementById("cfg-btn-apply");
        if (applyBtn) {
            applyBtn.disabled = !d.connected;
            applyBtn.style.opacity = d.connected ? "1" : "0.4";
            applyBtn.title = d.connected ? "" : "장치가 연결되어야 적용 가능합니다";
        }

    } catch(e) {}
}

// 3초마다 연결 상태 갱신
setInterval(pollDeviceStatus, 3000);
pollDeviceStatus();
"""

if 'openROISelect' in js:
    print("script.js: ROI 코드 이미 있음 → 스킵")
else:
    js = js.rstrip() + "\n" + ROI_AND_MORE_LEARN_JS + "\n"
    with sftp.open('/home/pi30306/turret_ws/static/script.js', 'w') as f:
        f.write(js)
    print("✅ script.js 업데이트 완료")

# ── 3. style.css: ROI 오버레이 + 더학습 모달 스타일 ────
css = run("cat /home/pi30306/turret_ws/static/style.css")

ROI_CSS = """

/* ─── ROI 선택 오버레이 ──────────────────────────────── */
#roi-select-overlay {
    display: none;
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 50;
    cursor: crosshair;
    touch-action: none;
}

#roi-select-canvas {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    pointer-events: none;
}

#roi-instruction-banner {
    position: absolute;
    top: 72px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,0.72);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 20px;
    padding: 10px 20px;
    color: #fff;
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
    pointer-events: none;
    animation: fadeSlideDown 0.3s ease;
}

#roi-confirm-btns {
    position: absolute;
    bottom: 110px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    gap: 12px;
    pointer-events: auto;
    animation: fadeSlideUp 0.25s ease;
}

#btn-roi-cancel, #btn-roi-confirm {
    border: none;
    border-radius: 14px;
    color: #fff;
    font-size: 14px;
    font-weight: 600;
    padding: 12px 22px;
    cursor: pointer;
    backdrop-filter: blur(10px);
    transition: transform 0.15s ease, opacity 0.15s ease;
}

#btn-roi-cancel  { background: rgba(255,59,48,0.85); }
#btn-roi-confirm { background: rgba(0,122,255,0.9); }
#btn-roi-cancel:active,
#btn-roi-confirm:active { transform: scale(0.95); opacity: 0.85; }

/* ─── 더 학습 모달 ────────────────────────────────────── */
#more-learn-modal {
    display: none;
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: 200;
    background: rgba(0,0,0,0.5);
    backdrop-filter: blur(15px);
    -webkit-backdrop-filter: blur(15px);
    align-items: center;
    justify-content: center;
    animation: fadeIn 0.3s ease;
}

#more-learn-modal .ios-modal-panel {
    max-width: 340px;
    animation: slideUp 0.35s cubic-bezier(0.34,1.56,0.64,1);
}

#btn-more-learn:hover  { opacity: 0.88; }
#btn-finish-learn:hover { opacity: 0.88; }
#btn-more-learn:active,
#btn-finish-learn:active { transform: scale(0.97); }

/* ─── 연결 상태 dot ──────────────────────────────────── */
#device-status-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #ff453a;
    transition: background 0.5s ease, box-shadow 0.5s ease;
    margin-right: 6px;
    flex-shrink: 0;
}

#device-status-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    transition: color 0.5s ease;
}

@keyframes fadeSlideDown {
    from { opacity:0; transform:translateX(-50%) translateY(-10px); }
    to   { opacity:1; transform:translateX(-50%) translateY(0); }
}

@keyframes fadeSlideUp {
    from { opacity:0; transform:translateX(-50%) translateY(10px); }
    to   { opacity:1; transform:translateX(-50%) translateY(0); }
}
"""

if 'roi-select-overlay' in css:
    print("style.css: ROI 스타일 이미 있음 → 스킵")
else:
    css = css.rstrip() + "\n" + ROI_CSS + "\n"
    with sftp.open('/home/pi30306/turret_ws/static/style.css', 'w') as f:
        f.write(css)
    print("✅ style.css 업데이트 완료")

# ── 4. index.html: device-status-dot + device-status-label 헤더에 추가 ──
html2 = run("cat /home/pi30306/turret_ws/templates/index.html")

if 'device-status-dot' in html2:
    print("index.html: device-status-dot 이미 있음 → 스킵")
else:
    # 기존 live-indicator 옆에 device 상태 dot 추가
    html2 = html2.replace(
        '</div>  <!-- header-left / header-right 끝 -->',
        '    <span id="device-status-dot"></span>\n            <span id="device-status-label">확인 중</span>\n        </div>'
    )
    # 더 안전하게: motor-link-label 근처에 삽입
    # header-right 끝부분 바로 앞에 추가
    html2 = html2.replace(
        '<button id="btn-settings"',
        '<span id="device-status-dot" title="모터 연결 상태"></span>\n        <span id="device-status-label" style="font-size:11px;font-weight:600;color:#ff453a;margin-right:8px;">확인 중</span>\n        <button id="btn-settings"'
    )
    with sftp.open('/home/pi30306/turret_ws/templates/index.html', 'w') as f:
        f.write(html2)
    print("✅ index.html device-status-dot 추가 완료")

sftp.close()
ssh.close()
print("\n🎉 모든 UI 패치 완료!")
