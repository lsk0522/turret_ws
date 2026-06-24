/* ==========================================
   Apple Premium Script for AI Vision Tracker
   ========================================== */

window.addEventListener("load", () => {
    setTimeout(() => {
        window.scrollTo(0, 1);
    }, 100);
    // 첫 로드 시 갤러리 리스트 불러오기
    updateGallery();
});

const img    = document.getElementById("video");
const canvas = document.getElementById("overlay");
const ctx    = canvas.getContext("2d");
const wrap   = document.getElementById("wrap");

canvas.width  = 640;
canvas.height = 480;

let BASE_R;
let STICK_R;

function resize(){
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let w;
    let h;

    /* 원래 4:3 비율 유지 */
    if (vw / vh > 4 / 3) {
        h = vh;
        w = vh * 4 / 3;
    } else {
        w = vw;
        h = vw * 3 / 4;
    }

    wrap.style.width  = w + "px";
    wrap.style.height = h + "px";

    const s = Math.min(w, h);

    // 조이스틱 및 컨트롤 버튼 크기 동적 조절
    BASE_R  = Math.round(s * 0.12);
    STICK_R = Math.round(s * 0.05);

    const base  = document.getElementById("joystick-base");
    const stick = document.getElementById("joystick-stick");

    base.style.width  = BASE_R * 2 + "px";
    base.style.height = BASE_R * 2 + "px";

    stick.style.width  = STICK_R * 2 + "px";
    stick.style.height = STICK_R * 2 + "px";

    stick.style.left = BASE_R + "px";
    stick.style.top  = BASE_R + "px";
}

resize();
window.addEventListener("resize", resize);

let px  = 320;   // 렌더링 위치 (lerp 적용)
let py  = 240;
let tPx = 320;   // 목표 위치 (서버 / 조이스틱이 설정)
let tPy = 240;
let maxSpeed = 5;

/* manual | auto */
let controlMode = "manual";

let joyVx = 0;
let joyVy = 0;
let joystickTouchId = null;

/* 학습 모드 상태 — drawCrosshair에서 참조하므로 loop() 전에 선언 */
let learningMode    = false;
let learningProgress = 0;
let currentLearnZone = { x: 170, y: 90, w: 300, h: 300 };

/* ==========================================
   Apple 시네마틱 크로스헤어 — 코너 브래킷 + 중심 도트
   ========================================== */
function drawCrosshair(){
    ctx.clearRect(0, 0, 640, 480);

    // 수동: Apple Red, 자동: Apple Green
    const color = (controlMode === "auto") ? "#30D158" : "#FF3B30";

    ctx.save();

    // 학습 모드 중이거나 ROI 영역을 선택하고 있을 때는 조준점(도트·링·브래킷) 전부 숨김
    const roiOverlayEl = document.getElementById("roi-select-overlay");
    const isROIOpen = roiOverlayEl && (roiOverlayEl.style.display === "block");
    if (!learningMode && !isROIOpen) {

        // ── 중심 도트 ──────────────────────────
        ctx.shadowBlur  = 10;
        ctx.shadowColor = color;
        ctx.fillStyle   = color;
        ctx.beginPath();
        ctx.arc(px, py, 2, 0, Math.PI * 2);
        ctx.fill();

        // ── 바깥 링 (얇고 반투명) ───────────────
        ctx.strokeStyle = (controlMode === "auto")
            ? "rgba(48, 209, 88, 0.28)"
            : "rgba(255, 59, 48, 0.28)";
        ctx.lineWidth   = 1;
        ctx.shadowBlur  = 0;
        ctx.beginPath();
        ctx.arc(px, py, 22, 0, Math.PI * 2);
        ctx.stroke();

        // ── 코너 브래킷 (L자 4개) ──────────────
        const gap = 28;
        const len = 10;
        const corners = [
            { ox: px - gap, oy: py - gap, dx:  len, dy:    0, ex:   0, ey:  len },
            { ox: px + gap, oy: py - gap, dx: -len, dy:    0, ex:   0, ey:  len },
            { ox: px - gap, oy: py + gap, dx:  len, dy:    0, ex:   0, ey: -len },
            { ox: px + gap, oy: py + gap, dx: -len, dy:    0, ex:   0, ey: -len },
        ];

        ctx.strokeStyle = color;
        ctx.lineWidth   = 1.8;
        ctx.lineCap     = "round";
        ctx.shadowBlur  = 8;
        ctx.shadowColor = color;

        corners.forEach(({ ox, oy, dx, dy, ex, ey }) => {
            ctx.beginPath();
            ctx.moveTo(ox + dx, oy + dy);
            ctx.lineTo(ox, oy);
            ctx.lineTo(ox + ex, oy + ey);
            ctx.stroke();
        });

    } // end if (!learningMode)

    // 학습 모드: 고정 학습 존 애니메이션
    if (learningMode) {
        ctx.save();
        const zx = currentLearnZone.x;
        const zy = currentLearnZone.y;
        const zw = currentLearnZone.w;
        const zh = currentLearnZone.h;

        // 반투명 외부 어둠
        ctx.fillStyle = "rgba(0,0,0,0.35)";
        ctx.fillRect(0, 0, 640, zy);
        ctx.fillRect(0, zy + zh, 640, 480 - zy - zh);
        ctx.fillRect(0, zy, zx, zh);
        ctx.fillRect(zx + zw, zy, 640 - zx - zw, zh);

        // 애니메이션 점선 테두리
        const dash = (Date.now() / 25) % 20;
        ctx.setLineDash([10, 5]);
        ctx.lineDashOffset = -dash;
        ctx.strokeStyle = "#30d158";
        ctx.lineWidth = 2;
        ctx.shadowBlur = 12;
        ctx.shadowColor = "#30d158";
        ctx.strokeRect(zx, zy, zw, zh);

        // 코너 L자 핸들
        ctx.setLineDash([]);
        ctx.lineWidth = 3.5;
        const hl = 16;
        [
            [zx,      zy,       hl,  0,  0,  hl],
            [zx + zw, zy,      -hl,  0,  0,  hl],
            [zx,      zy + zh,  hl,  0,  0, -hl],
            [zx + zw, zy + zh, -hl,  0,  0, -hl],
        ].forEach(([ox, oy, dx1, dy1, dx2, dy2]) => {
            ctx.beginPath();
            ctx.moveTo(ox + dx1, oy); ctx.lineTo(ox, oy); ctx.lineTo(ox, oy + dy2);
            ctx.stroke();
        });

        // 진행률 텍스트 (박스 상단에 그려서 하단 게이지바와의 중복/겹침 차단)
        ctx.setLineDash([]);
        ctx.shadowBlur = 0;
        ctx.font = "bold 13px -apple-system, sans-serif";
        ctx.fillStyle = "#30d158";
        ctx.textAlign = "center";
        let textY = zy - 10;
        if (textY < 15) {
            textY = zy + 20; // 상단 한계 경계선일 경우 박스 안쪽에 표기
        }
        ctx.fillText(`${learningProgress}%`, zx + zw / 2, textY);

        ctx.restore();
    }

    // 자동 모드: 야구공 검출 박스 + 예측 위치 표시
    if (controlMode === "auto" && ballState && ballState.detected) {
        const lost = ballState.lost;
        const boxColor = lost ? "rgba(255,159,10,0.7)" : "#30d158";

        ctx.save();
        ctx.strokeStyle = boxColor;
        ctx.shadowBlur = 6;
        ctx.shadowColor = boxColor;
        ctx.lineWidth = 2;

        if (!lost && ballState.x !== undefined) {
            // 실제 검출 박스
            ctx.strokeRect(ballState.x, ballState.y, ballState.w, ballState.h);
        }

        // 칼만 예측 위치 (작은 십자선)
        const pcx = ballState.predicted_cx ?? ballState.cx;
        const pcy = ballState.predicted_cy ?? ballState.cy;
        if (pcx !== undefined) {
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(pcx - 10, pcy); ctx.lineTo(pcx + 10, pcy);
            ctx.moveTo(pcx, pcy - 10); ctx.lineTo(pcx, pcy + 10);
            ctx.stroke();
        }

        ctx.restore();
    }

    ctx.restore();
}

/* ==========================================
   야구공 검출 상태 (자동 모드)
   ========================================== */
let ballState = null;

setInterval(async () => {
    if (controlMode !== "auto") {
        ballState = null;
        return;
    }
    try {
        const res = await fetch("/ball");
        ballState = await res.json();
        if (ballState && ballState.detected && ballState.cx !== undefined) {
            // 자동 모드: 실제 추적 대상의 위치를 조준점 타겟(tPx, tPy)으로 설정하여,
            // 십자선이 모터 각도가 아닌 실제 물체를 부드럽게 따라가게 함
            tPx = ballState.cx;
            tPy = ballState.cy;
        }
    } catch(e) {}
}, 80);

let lastSync = 0;

let _isFetchingClick = false;
let _pendingClickX = null;
let _pendingClickY = null;

function sendClick(x, y) {
    if (_isFetchingClick) {
        _pendingClickX = Math.round(x);
        _pendingClickY = Math.round(y);
        return;
    }
    _isFetchingClick = true;
    _pendingClickX = null;
    _pendingClickY = null;
    
    fetch(`/click?x=${Math.round(x)}&y=${Math.round(y)}`)
        .catch(()=>{})
        .finally(() => {
            _isFetchingClick = false;
            if (_pendingClickX !== null) {
                setTimeout(() => sendClick(_pendingClickX, _pendingClickY), 5);
            }
        });
}

function syncServer(){
    const now = Date.now();
    if(now - lastSync < 50) return;
    lastSync = now;
    sendClick(tPx, tPy);
}


async function syncPos(){
    // 자동 모드일 때는 모터 위치(/pos)로 크로스헤어를 옮기지 않음
    if (controlMode === "auto") return;
    
    // 조이스틱을 사용 중이거나 최근에 사용했다면 서버 위치로 덮어쓰지 않음 (튀는 현상 방지)
    if (joystickTouchId !== null || (Date.now() - lastSync < 300)) return;
    
    try {
        const res  = await fetch("/pos");
        const data = await res.json();
        
        // 비동기 네트워크 응답을 기다리는 동안 사용자가 조이스틱을 조작하기 시작했을 수 있으므로 재확인
        if (controlMode === "auto" || joystickTouchId !== null || (Date.now() - lastSync < 300)) return;
        
        tPx = data.x;   // 목표값만 갱신 — 렌더링은 loop()에서 lerp
        tPy = data.y;
    } catch(e) {}
}

// 자동 모드: 80ms마다 위치 동기화 (추적 반응성)
// 수동 모드: 동기화 안 함 — 클라이언트가 직접 위치 관리
setInterval(() => {
    // 자동 모드: syncPos(/pos)는 사용하지 않음 (모터 각도 추종 금지)
    if (controlMode !== "auto") {
        syncPos();
    }
}, 80);

/* ==========================================
   조이스틱 드래그 제어 로직 (마우스 & 터치)
   ========================================== */
const base  = document.getElementById("joystick-base");
const stick = document.getElementById("joystick-stick");

function getBaseCenter(){
    const rect = base.getBoundingClientRect();
    return {
        x: rect.left + BASE_R,
        y: rect.top  + BASE_R
    };
}

let joyDirX = 0;
let joyDirY = 0;

let _joyLastSend = 0;

function checkJoystickDir() {
    // Deprecated: Joystick directly mapped to /click in loop() for zero-delay velocity control
}

function updateStick(tx, ty){
    const center = getBaseCenter();
    let dx = tx - center.x;
    let dy = ty - center.y;

    const dist = Math.sqrt(dx*dx + dy*dy);
    const maxDist = BASE_R * 0.75;

    if(dist > maxDist){
        dx = dx / dist * maxDist;
        dy = dy / dist * maxDist;
    }

    stick.style.left = BASE_R + dx + "px";
    stick.style.top  = BASE_R + dy + "px";

    joyVx = dx / maxDist;
    joyVy = dy / maxDist;
    
    // checkJoystickDir(); // removed to prevent overlap with syncServer
    checkJoystickDir(); // Re-enabled for proper velocity control
}

function resetStick(){
    // Spring-back animation: restore transition then snap to center with physics
    stick.style.transition = 'left 0.45s cubic-bezier(0.34,1.56,0.64,1.0), top 0.45s cubic-bezier(0.34,1.56,0.64,1.0), background 0.15s';
    stick.style.left = BASE_R + "px";
    stick.style.top  = BASE_R + "px";
    setTimeout(() => { stick.style.transition = ''; }, 460);

    joyVx = 0;
    joyVy = 0;
    joystickTouchId = null;

    if (inputMode === "joystick") {
        tPx = 320;
        tPy = 240;
        sendClick(320, 240);
    }
    lastSync = Date.now();
}

/* 터치 제어 */
base.addEventListener("touchstart", (e)=>{
    e.preventDefault();
    const t = e.changedTouches[0];
    joystickTouchId = t.identifier;
    updateStick(t.clientX, t.clientY);
},{passive:false});

base.addEventListener("touchmove", (e)=>{
    e.preventDefault();
    for(const t of e.changedTouches){
        if(t.identifier === joystickTouchId){
            updateStick(t.clientX, t.clientY);
        }
    }
},{passive:false});

base.addEventListener("touchend", () => {
    resetStick();
});

/* 마우스 제어 */
base.addEventListener("mousedown", (e)=>{
    e.preventDefault();
    updateStick(e.clientX, e.clientY);

    function move(ev){
        updateStick(ev.clientX, ev.clientY);
    }

    function up(){
        resetStick();
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
    }

    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
});

/* ==========================================
   Toast 알림 시스템 (alert() 대체)
   ========================================== */
function showToast(msg, type = 'info', duration = 3000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast-show'));
    setTimeout(() => {
        toast.classList.remove('toast-show');
        toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    }, duration);
}

/* ==========================================
   액션 이벤트 핸들링 (캡처, 플립)
   ========================================== */
const flashOverlay = document.getElementById("flash-overlay");

function triggerFlash() {
    flashOverlay.classList.remove("flash-active");
    void flashOverlay.offsetWidth;
    flashOverlay.classList.add("flash-active");
}

document.getElementById("btn-capture").addEventListener("click", () => {
    // Flash fires only on SUCCESS (not false-positive on error)
    fetch("/capture")
        .then(() => {
            triggerFlash();
            setTimeout(updateGallery, 350);
        })
        .catch(() => showToast('촬영 실패: 카메라 연결을 확인하세요', 'error'));
});

document.getElementById("btn-flip").addEventListener("click", () => {
    fetch("/flip").catch(() => showToast('플립 실패', 'error'));
});

/* ==========================================
   메인 드로잉 및 조준점 갱신 루프 (delta-time lerp)
   ========================================== */
let _lastFrameTime = 0;

function loop(timestamp){
    const dt = _lastFrameTime === 0 ? 1 : Math.min((timestamp - _lastFrameTime) / (1000 / 60), 3);
    _lastFrameTime = timestamp;

    if (controlMode === "manual") {
        // 수동 조이스틱 모드: 십자선은 항상 중앙(320, 240)에 렌더링
        px = 320;
        py = 240;
        
        if (inputMode === "joystick") {
            // 조이스틱의 위치값을 직접 가상 타겟(tPx, tPy)의 오프셋으로 변환 (속도 제어)
            if (Math.abs(joyVx) > 0.05 || Math.abs(joyVy) > 0.05) {
                tPx = 320 + joyVx * maxSpeed * 6; // maxSpeed에 비례한 오프셋
                tPy = 240 + joyVy * maxSpeed * 6;
                
                const now = Date.now();
                if (now - lastSync > 60) {
                    sendClick(tPx, tPy);
                    lastSync = now;
                }
            } else if (tPx !== 320 || tPy !== 240) {
                // 조이스틱을 놨을 때 즉각 중앙 타겟 전송하여 모터 즉시 정지
                tPx = 320;
                tPy = 240;
                sendClick(320, 240);
                lastSync = Date.now();
            }
        }
    } else {
        // 자동 모드: 서버 갱신(80ms)을 lerp로 보간 → 끊김 없음
        px += (tPx - px) * 0.20;
        py += (tPy - py) * 0.20;
    }
    drawCrosshair();
    requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

/* ==========================================
   애플 스타일 설정창 제어
   ========================================== */
const settingsBtn = document.getElementById("settings-btn");
const settingsModal = document.getElementById("settings-modal");
const closeSettings = document.getElementById("close-settings");

/* ==========================================
   모달 열기/닫기 (Apple spring 애니메이션)
   ========================================== */
function _closeModalAnimate(modal) {
    const panel = modal.querySelector('.ios-modal-panel, .more-learn-panel, .gallery-panel, .motor-status-panel, .motor-cfg-panel, .camera-settings-panel');
    modal.classList.add('modal-closing');
    if (panel) {
        panel.style.animation = 'panelOut 0.22s cubic-bezier(0.55,0,1,0.45) forwards';
    }
    setTimeout(() => {
        modal.style.display = 'none';
        modal.classList.remove('modal-closing');
        if (panel) panel.style.animation = '';
    }, 220);
}

function openSettings(){
    settingsModal.style.display = "flex";
}

function closeSettingsModal(){
    _closeModalAnimate(settingsModal);
}

settingsBtn.addEventListener("click", openSettings);
closeSettings.addEventListener("click", closeSettingsModal);

settingsModal.addEventListener("click", function(e){
    if(e.target === settingsModal){
        closeSettingsModal();
    }
});

// ESC 키: 학습 모드 → ROI 선택 → 모달 닫기 → 설정 열기 순으로 처리
document.addEventListener("keydown", function(e){
    if (e.key !== "Escape") return;
    if (learningMode) {
        exitLearningMode();
        moreLearnModal.style.display = "none";
        _sessionCount = 0;
        fetch("/clear_target");
    } else if (roiOverlay.style.display === "block") {
        closeROISelect();
        openSettings();
    } else if (moreLearnModal.style.display === "flex") {
        moreLearnModal.style.display = "none";
        _sessionCount = 0;
        openSettings();
    } else if (settingsModal.style.display === "flex") {
        closeSettingsModal();
    } else if (galleryModal.style.display === "flex") {
        closeGalleryModal();
    } else if (motorStatusModal.style.display === "flex") {
        closeMotorStatusModal();
    } else if (motorCfgModal.style.display === "flex") {
        closeMotorCfgModal();
    } else if (typeof firmwareModal !== "undefined" && firmwareModal && firmwareModal.style.display === "flex") {
        firmwareModal.style.display = "none";
    } else if (typeof cameraCfgModal !== "undefined" && cameraCfgModal && cameraCfgModal.style.display === "flex") {
        closeCameraCfgModal();
    } else {
        openSettings();
    }
});

/* 속도 슬라이더 — debounce to avoid 60 HTTP requests/sec */
const speedSlider = document.getElementById("speed-slider");
const speedValue = document.getElementById("speed-value");

let _speedDebounce = null;
speedSlider.addEventListener("input", function(){
    maxSpeed = parseFloat(speedSlider.value);
    speedValue.textContent = speedSlider.value;
    clearTimeout(_speedDebounce);
    _speedDebounce = setTimeout(() => {
        fetch(`/set_speed?speed=${speedSlider.value}`).catch(() => {});
    }, 150);
});

/* ── Input Mode: "pointer" | "joystick" | "auto" ──────────────── */
let inputMode = "joystick";

const controlSegmentBtns = document.querySelectorAll("#control-mode-segment .segment-btn");
const segmentSlider      = document.querySelector("#control-mode-segment .segment-slider");
const hiddenSelect       = document.getElementById("control-mode");

// Header indicator elements
const liveIndicator     = document.getElementById("live-indicator");
const trackingIndicator = document.getElementById("tracking-indicator");
const trackingDot       = document.getElementById("tracking-dot");
const trackingLabel     = document.getElementById("tracking-label");

// Click handler for 3-way segment buttons
controlSegmentBtns.forEach((btn, idx) => {
    btn.addEventListener("click", () => {
        const val = btn.dataset.value;
        setInputModeUI(val);
        fetch(`/set_input_mode?mode=${val}`);
    });
});

function setInputModeUI(mode) {
    inputMode = mode;
    if (hiddenSelect) hiddenSelect.value = mode;

    // Update active button and slider position
    const btns = [...controlSegmentBtns];
    btns.forEach(b => b.classList.toggle("active", b.dataset.value === mode));
    const idx = btns.findIndex(b => b.dataset.value === mode);
    segmentSlider.style.transform = `translateX(${idx * 100}%)`;

    // Sync legacy controlMode for crosshair color etc.
    controlMode = (mode === "auto") ? "auto" : "manual";

    // Update header indicators
    if (liveIndicator)     liveIndicator.style.display    = (mode === "joystick") ? "flex" : "none";
    if (trackingIndicator) trackingIndicator.style.display = (mode === "auto")    ? "flex" : "none";

    // Toggle joystick visibility
    const joystickBase = document.getElementById("joystick-base");
    if (joystickBase) {
        joystickBase.style.opacity      = (mode === "joystick") ? "1" : "0";
        joystickBase.style.pointerEvents = (mode === "joystick") ? "" : "none";
    }

    // Reset joystick when leaving joystick mode
    if (mode !== "joystick") {
        joyVx = 0; joyVy = 0;
    }

    // Start or stop AI tracking poll
    if (mode === "auto") {
        startTrackingPoll();
    } else {
        stopTrackingPoll();
        // Reset tracking indicator on non-auto modes
        updateTrackingUI(false);
    }
}

/* ── AI Tracking Status Polling ──────────────────────────────── */
let trackingPollTimer = null;

function startTrackingPoll() {
    if (trackingPollTimer) return;
    trackingPollTimer = setInterval(pollTrackingStatus, 200);
}

function stopTrackingPoll() {
    if (trackingPollTimer) {
        clearInterval(trackingPollTimer);
        trackingPollTimer = null;
    }
}

async function pollTrackingStatus() {
    if (inputMode !== "auto") return;
    try {
        const res  = await fetch("/tracking_status");
        const data = await res.json();
        updateTrackingUI(data.locked);
    } catch(e) {}
}

function updateTrackingUI(locked) {
    if (!trackingDot || !trackingLabel) return;
    if (locked) {
        trackingDot.className   = "tracking-dot tracking-locked";
        trackingLabel.textContent = "LOCKED";
        trackingLabel.style.color = "#30d158";
    } else {
        trackingDot.className   = "tracking-dot tracking-searching";
        trackingLabel.textContent = "SEARCHING";
        trackingLabel.style.color = "#ff9f0a";
    }
}

/* ── Mode 1: Pointer Control (canvas click/touch) ─────────────── */



/* ── 물건 선택 버튼 ──────────────────────────────────── */
let hasTarget = false;

const btnSelectTarget  = document.getElementById("btn-select-target");
const targetPreviewRow = document.getElementById("target-preview-row");
const targetThumb      = document.getElementById("target-thumb");
const btnAddLearning   = document.getElementById("btn-add-learning");
const btnClearTarget   = document.getElementById("btn-clear-target");

btnSelectTarget.addEventListener("click", () => {
    closeSettingsModal();
    openROISelect();
});

if (btnAddLearning) {
    btnAddLearning.addEventListener("click", async () => {
        closeSettingsModal();
        try {
            await fetch("/add_learning?n=20");
            _startLearningSession();
        } catch (e) {
            console.error("추가 학습 실패", e);
        }
    });
}

if (btnClearTarget) {
    btnClearTarget.addEventListener("click", async () => {
        try {
            await fetch("/clear_target");
            hasTarget = false;
            targetPreviewRow.style.display = "none";
            btnSelectTarget.textContent = "물건 새로 학습하기";
            _sessionCount = 0;
            // Fix: use setInputModeUI (correct function name, was setControlModeUI)
            controlMode = 'manual';
            setInputModeUI('joystick');
            await fetch("/set_mode?mode=manual");
        } catch (e) {
            console.error("타겟 초기화 실패", e);
            showToast('타겟 초기화 실패', 'error');
        }
    });
}

function setTargetUI(thumbSrc) {
    hasTarget = true;
    if (thumbSrc) targetThumb.src = thumbSrc;
    targetPreviewRow.style.display = "flex";
    btnSelectTarget.textContent = "다시 학습";
}

/* ══════════════════════════════════════════
   ROI 드래그 선택
   ══════════════════════════════════════════ */
const roiOverlay    = document.getElementById("roi-select-overlay");
const roiCanvas     = document.getElementById("roi-canvas");
const roiConfirmBtns = document.getElementById("roi-confirm-btns");
const btnRoiCancel  = document.getElementById("btn-roi-cancel");
const btnRoiConfirm = document.getElementById("btn-roi-confirm");

let _roiDrag = false, _roiSx = 0, _roiSy = 0, _roiRect = null;

function _vidCoords(cx, cy) {
    const r = document.getElementById("video").getBoundingClientRect();
    return { x: Math.round((cx - r.left) * 640 / r.width),
             y: Math.round((cy - r.top)  * 480 / r.height) };
}

function _drawROI(x1, y1, x2, y2) {
    const c = roiCanvas;
    c.width = c.offsetWidth; c.height = c.offsetHeight;
    const ctx = c.getContext("2d");
    const vr = document.getElementById("video").getBoundingClientRect();
    const sx = Math.min(x1,x2) * vr.width/640,  sy = Math.min(y1,y2) * vr.height/480;
    const sw = Math.abs(x2-x1) * vr.width/640,  sh = Math.abs(y2-y1) * vr.height/480;
    ctx.clearRect(0,0,c.width,c.height);
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(0,0,c.width,c.height);
    ctx.clearRect(sx,sy,sw,sh);
    ctx.strokeStyle = "#007aff"; ctx.lineWidth = 2.5;
    ctx.shadowColor = "rgba(0,122,255,0.8)"; ctx.shadowBlur = 8;
    ctx.strokeRect(sx,sy,sw,sh);
    // 코너 핸들
    const L=14; ctx.strokeStyle="#fff"; ctx.lineWidth=3; ctx.shadowBlur=0;
    [[sx,sy],[sx+sw,sy],[sx,sy+sh],[sx+sw,sy+sh]].forEach(([cx,cy]) => {
        const dx = cx<sx+sw/2?1:-1, dy = cy<sy+sh/2?1:-1;
        ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+dx*L,cy);
        ctx.moveTo(cx,cy); ctx.lineTo(cx,cy+dy*L); ctx.stroke();
    });
    const wP=Math.abs(x2-x1), hP=Math.abs(y2-y1);
    if(wP>30 && hP>30) {
        const label=`${wP} × ${hP}`;
        ctx.font="bold 12px Inter,sans-serif";
        const tw=ctx.measureText(label).width;
        ctx.fillStyle="rgba(0,0,0,0.6)";
        ctx.fillRect(sx+sw/2-tw/2-6, sy+sh/2-10, tw+12, 20);
        ctx.fillStyle="#fff"; ctx.textAlign="center";
        ctx.fillText(label, sx+sw/2, sy+sh/2+4);
    }
}

function openROISelect() {
    roiOverlay.style.display = "block";
    roiConfirmBtns.style.display = "none";
    _roiRect = null;
    const c = roiCanvas;
    c.width = c.offsetWidth; c.height = c.offsetHeight;
    const ctx = c.getContext("2d");
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(0,0,c.width,c.height);
}
function closeROISelect() { roiOverlay.style.display = "none"; _roiRect = null; }

function _roiPointerDown(cx, cy, target) {
    if (target && target.closest("#roi-confirm-btns")) return;
    const p = _vidCoords(cx,cy);
    _roiDrag=true; _roiSx=p.x; _roiSy=p.y;
    roiConfirmBtns.style.display="none";
}
function _roiPointerMove(cx, cy) {
    if(!_roiDrag) return;
    const p = _vidCoords(cx,cy);
    _drawROI(_roiSx,_roiSy,p.x,p.y);
}
function _roiPointerUp(cx, cy) {
    if(!_roiDrag) return; _roiDrag=false;
    const p = _vidCoords(cx,cy);
    const x=Math.min(_roiSx,p.x), y=Math.min(_roiSy,p.y);
    const w=Math.abs(p.x-_roiSx), h=Math.abs(p.y-_roiSy);
    if(w>20 && h>20) { _roiRect={x,y,w,h}; roiConfirmBtns.style.display="flex"; }
}

roiOverlay.addEventListener("mousedown", e => _roiPointerDown(e.clientX, e.clientY, e.target));
roiOverlay.addEventListener("mousemove", e => _roiPointerMove(e.clientX, e.clientY));
roiOverlay.addEventListener("mouseup",   e => _roiPointerUp(e.clientX, e.clientY));
roiOverlay.addEventListener("touchstart", e => { e.preventDefault(); const t=e.touches[0]; _roiPointerDown(t.clientX,t.clientY,e.target); }, {passive:false});
roiOverlay.addEventListener("touchmove",  e => { e.preventDefault(); const t=e.touches[0]; _roiPointerMove(t.clientX,t.clientY); }, {passive:false});
roiOverlay.addEventListener("touchend",   e => { const t=e.changedTouches[0]; _roiPointerUp(t.clientX,t.clientY); });

btnRoiCancel.addEventListener("click", closeROISelect);
btnRoiConfirm.addEventListener("click", async () => {
    if(!_roiRect) return;
    const {x,y,w,h} = _roiRect;
    await fetch(`/set_learn_zone?x=${x}&y=${y}&w=${w}&h=${h}`).catch(()=>{});
    currentLearnZone = { x, y, w, h };
    closeROISelect();
    _startLearningSession();
});

/* ══════════════════════════════════════════
   지문인식 스타일 반복 학습 모달
   ══════════════════════════════════════════ */
const moreLearnModal    = document.getElementById("more-learn-modal");
const moreLearnThumb    = document.getElementById("more-learn-thumb");
const moreLearnThumbIcon = document.getElementById("more-learn-thumb-icon");
const moreLearnCount    = document.getElementById("more-learn-count");
const moreLearnDots     = document.getElementById("more-learn-dots");
const btnMoreLearn      = document.getElementById("btn-more-learn");
const btnFinishLearn    = document.getElementById("btn-finish-learn");

let _sessionCount = 0;

function _renderDots(n) {
    if(!moreLearnDots) return;
    moreLearnDots.innerHTML = "";
    for(let i=0;i<5;i++) {
        const d = document.createElement("div");
        d.className = "ml-dot" + (i<n ? " ml-dot-on" : "");
        moreLearnDots.appendChild(d);
    }
}

function _showMoreLearnModal(thumbnail) {
    _sessionCount++;
    if(thumbnail) { moreLearnThumb.src=thumbnail; moreLearnThumb.style.display="block"; moreLearnThumbIcon.style.display="none"; }
    else          { moreLearnThumb.style.display="none"; moreLearnThumbIcon.style.display="block"; }
    moreLearnCount.textContent = `${_sessionCount}회 학습 완료`;
    _renderDots(_sessionCount);

    // 지문인식 스타일 다각도 모션 가이드
    const descEl = document.querySelector(".more-learn-desc");
    if (descEl) {
        if (_sessionCount === 1) {
            descEl.innerHTML = "1단계 스캔 완료!<br>이번에는 물체를 <b>옆으로 살짝 돌려 측면</b>을 학습해 보세요.";
        } else if (_sessionCount === 2) {
            descEl.innerHTML = "2단계 스캔 완료!<br>이번에는 물체를 <b>조금 더 멀리서(크기 변화)</b> 학습해 보세요.";
        } else if (_sessionCount === 3) {
            descEl.innerHTML = "3단계 스캔 완료!<br>이번에는 물체를 <b>위/아래로 비스듬히 기울여서</b> 학습해 보세요.";
        } else if (_sessionCount === 4) {
            descEl.innerHTML = "4단계 스캔 완료!<br>마지막으로 <b>뒷면 또는 불규칙한 각도</b>를 한번 더 학습하세요.";
        } else {
            descEl.innerHTML = "5단계 스캔 완료! 다각도 학습이 모두 끝났습니다.<br>완료 버튼을 누르면 고정밀 자동 추적이 가능합니다.";
        }
    }
    moreLearnModal.style.display = "flex";
}

btnMoreLearn && btnMoreLearn.addEventListener("click", () => {
    moreLearnModal.style.display = "none";
    fetch("/add_learning?n=20").catch(()=>{});
    _startLearnPoll();
});
btnFinishLearn && btnFinishLearn.addEventListener("click", () => {
    moreLearnModal.style.display = "none";
    _sessionCount = 0;
});

/* ══════════════════════════════════════════
   학습 모드 오버레이
   ══════════════════════════════════════════ */
const learnOverlay   = document.getElementById("learn-overlay");
const btnCancelLearn = document.getElementById("btn-cancel-learn");
const learnFill      = document.getElementById("learn-progress-fill");
const learnPct       = document.getElementById("learn-progress-pct");
const learnBannerTxt = document.getElementById("learn-banner-text");

let _learnPollTimer = null;

function _startLearningSession() {
    fetch("/start_learning").catch(()=>{});
    _startLearnPoll();
}

function _startLearnPoll() {
    learningMode = true;
    learningProgress = 0;
    learnFill.style.width = "0%";
    learnPct.textContent  = "0%";
    learnBannerTxt.textContent = "AI 트래커 대상을 지정했습니다!";
    learnBannerTxt.style.color = ""; // 색상 초기화
    learnOverlay.classList.add("active");
    document.getElementById("joystick-base").style.pointerEvents = "none";
    document.body.classList.add("is-learning");
    
    // Force live indicator visible and update to LEARNING state
    if (liveIndicator)     liveIndicator.style.display    = "flex";
    if (trackingIndicator) trackingIndicator.style.display = "none";
    const statusLabel = document.querySelector(".status-label");
    const statusDot   = document.querySelector(".status-dot");
    if (statusLabel && statusDot) {
        statusLabel.textContent    = "LEARNING";
        statusLabel.style.color    = "#30d158";
        statusDot.style.background = "#30d158";
        statusDot.style.boxShadow  = "0 0 7px #30d158";
    }
    
    if(_learnPollTimer) clearInterval(_learnPollTimer);
    _learnPollTimer = setInterval(_pollLearning, 120);
}

function exitLearningMode() {
    learningMode = false;
    learnOverlay.classList.remove("active");
    document.getElementById("joystick-base").style.pointerEvents = "";
    document.body.classList.remove("is-learning");
    
    // Restore header indicators to current input mode
    const statusLabel = document.querySelector(".status-label");
    const statusDot   = document.querySelector(".status-dot");
    if (statusLabel && statusDot) {
        statusLabel.textContent    = "LIVE";
        statusLabel.style.color    = "";
        statusDot.style.background = "";
        statusDot.style.boxShadow  = "";
    }
    // Re-apply the correct header indicator for the current mode
    if (typeof setInputModeUI === "function") setInputModeUI(inputMode);
    
    if(_learnPollTimer) { clearInterval(_learnPollTimer); _learnPollTimer = null; }
}



async function _pollLearning() {
    try {
        const res  = await fetch("/learning_progress");
        const data = await res.json();
        learningProgress = data.progress;
        /* % 중복 방지: fill 너비만, 숫자는 span 하나만 */
        learnFill.style.width = data.progress + "%";
        learnPct.textContent  = data.progress + "%";
        if(data.done) {
            clearInterval(_learnPollTimer); _learnPollTimer = null;
            learnFill.style.width = "100%";
            learnPct.textContent  = "100%";
            
            if (data.failed) {
                learnBannerTxt.textContent = "✗ 학습 실패: 특징점 부족";
                learnBannerTxt.style.color = "#ff453a";
                setTimeout(() => {
                    exitLearningMode();
                    // Replace alert() with styled toast
                    showToast('인식된 특징점이 부족합니다. 밝은 곳에서 다시 시도해 주세요.', 'error', 5000);
                }, 1000);
            } else {
                learnBannerTxt.textContent = "✓ 추적 대상을 고정했습니다!";
                learnBannerTxt.style.color = "#30d158";
                setTimeout(() => {
                    exitLearningMode();
                    setTargetUI(data.thumbnail);
                    /* 연속 3회전 학습이므로 추가 모달 표시 안 함 */
                }, 800);
            }
        } else {
            // 진행도에 따라 안내 텍스트 자동 변경 (3회전 안내)
            if (data.progress < 33) {
                learnBannerTxt.textContent = "제자리에서 360도 천천히 돌려주세요 (1/3 회전)";
            } else if (data.progress < 66) {
                learnBannerTxt.textContent = "살짝 기울여서 한 번 더 돌려주세요 (2/3 회전)";
            } else {
                learnBannerTxt.textContent = "마지막으로 반대쪽 측면을 돌려주세요 (3/3 회전)";
            }
        }
    } catch(e) {}
}

btnCancelLearn.addEventListener("click", () => {
    exitLearningMode();
    moreLearnModal.style.display = "none";
    _sessionCount = 0;
    fetch("/clear_target");
});

/* ==========================================
   미디어 라이브러리 (갤러리 및 라이트박스) 제어
   ========================================= */
let captures = [];
let activeCaptureIndex = -1;

const galleryBtn = document.getElementById("gallery-btn");
const galleryModal = document.getElementById("gallery-modal");
const closeGallery = document.getElementById("close-gallery");
const galleryThumb = document.getElementById("gallery-thumb");
const galleryEmptyIcon = document.getElementById("gallery-empty-icon");

async function updateGallery() {
    try {
        const res = await fetch("/captures?_t=" + Date.now());
        captures = await res.json();

        if (captures && captures.length > 0) {
            galleryThumb.src = `/picture/${captures[0]}?_t=${Date.now()}`;
            galleryThumb.style.display = "block";
            galleryEmptyIcon.style.display = "none";
        } else {
            galleryThumb.style.display = "none";
            galleryEmptyIcon.style.display = "flex";
        }
    } catch(e) {
        console.error("Failed to update gallery:", e);
    }
}

function openGalleryModal(index = 0) {
    galleryModal.style.display = "flex";
    if (captures.length === 0) {
        document.getElementById("gallery-active-img").src = "";
        document.getElementById("gallery-img-info").textContent = "사진이 없습니다";
        document.getElementById("gallery-thumbnails-list").innerHTML = "";
        return;
    }
    activeCaptureIndex = index;
    renderActiveImage();
    renderGalleryThumbnails();
}

function closeGalleryModal() {
    _closeModalAnimate(galleryModal);
}

galleryBtn.addEventListener("click", async () => {
    await updateGallery();
    openGalleryModal(0);
});


closeGallery.addEventListener("click", closeGalleryModal);
galleryModal.addEventListener("click", (e) => {
    if (e.target === galleryModal) {
        closeGalleryModal();
    }
});

function renderActiveImage() {
    if (activeCaptureIndex < 0 || activeCaptureIndex >= captures.length) return;
    const filename = captures[activeCaptureIndex];
    const activeImg = document.getElementById("gallery-active-img");
    const imgInfo = document.getElementById("gallery-img-info");
    const downloadBtn = document.getElementById("gallery-download");

    // Skeleton loading: add .loading class until image loads
    activeImg.classList.add('loading');
    activeImg.onload = () => activeImg.classList.remove('loading');
    activeImg.onerror = () => activeImg.classList.remove('loading');
    activeImg.src = `/picture/${filename}`;

    // 이미지 정보 파싱 (예: 320_240_1623456789.jpg -> 날짜 및 조준 좌표)
    let label = filename;
    try {
        const temp = filename.replace(".jpg", "");
        const parts = temp.split("_");
        if (parts.length >= 3) {
            const x = parts[0];
            const y = parts[1];
            const ts = parseInt(parts[2]);
            const date = new Date(ts * 1000).toLocaleString("ko-KR", {
                timeStyle: "medium", 
                dateStyle: "short"
            });
            label = `${date} (${x}, ${y})`;
        }
    } catch(e) {}

    imgInfo.textContent = `${label} [${activeCaptureIndex + 1} / ${captures.length}]`;
    downloadBtn.href = `/picture/${filename}`;
}

function renderGalleryThumbnails() {
    const thumbList = document.getElementById("gallery-thumbnails-list");
    thumbList.innerHTML = "";

    captures.forEach((filename, idx) => {
        const item = document.createElement("img");
        item.className = `gallery-thumb-item ${idx === activeCaptureIndex ? 'active' : ''}`;
        item.src = `/picture/${filename}`;
        item.alt = "Thumbnail";
        
        item.addEventListener("click", () => {
            activeCaptureIndex = idx;
            renderActiveImage();
            updateThumbnailsHighlight();
        });
        thumbList.appendChild(item);
    });
}

function updateThumbnailsHighlight() {
    const thumbs = document.querySelectorAll(".gallery-thumb-item");
    thumbs.forEach((thumb, i) => {
        if (i === activeCaptureIndex) {
            thumb.classList.add("active");
            thumb.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        } else {
            thumb.classList.remove("active");
        }
    });
}

document.getElementById("gallery-prev").addEventListener("click", () => {
    if (captures.length <= 1) return;
    activeCaptureIndex = (activeCaptureIndex - 1 + captures.length) % captures.length;
    renderActiveImage();
    updateThumbnailsHighlight();
});

document.getElementById("gallery-next").addEventListener("click", () => {
    if (captures.length <= 1) return;
    activeCaptureIndex = (activeCaptureIndex + 1) % captures.length;
    renderActiveImage();
    updateThumbnailsHighlight();
});

/* ==========================================
   설정 데이터 로드 및 초기화
   ========================================== */
/* ── 기기 타입 (ESP32 / Arduino) ────────────────────────── */
let deviceType = "esp32";

const deviceSegmentBtns = document.querySelectorAll("#device-type-segment .segment-btn");
const deviceSlider      = document.querySelector("#device-type-segment .segment-slider");
const motorLinkLabel    = document.getElementById("motor-link-label");
const esp32CfgSection   = document.getElementById("esp32-cfg-section");
const arduinoCfgSection = document.getElementById("arduino-cfg-section");

function setDeviceTypeUI(type) {
    deviceType = type;
    deviceSegmentBtns.forEach(btn => {
        btn.classList.toggle("active", btn.dataset.value === type);
    });
    deviceSlider.style.transform = (type === "esp32") ? "translateX(0)" : "translateX(100%)";
    motorLinkLabel.textContent = "모터 파라미터 설정";
    document.getElementById("motor-cfg-title").textContent = "모터 파라미터 설정";
    const applyBtn = document.getElementById("cfg-btn-apply");
    if (applyBtn) applyBtn.textContent = (type === "esp32") ? "ESP32에 적용" : "Arduino에 적용";
}

deviceSegmentBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        const val = btn.dataset.value;
        setDeviceTypeUI(val);
        fetch(`/set_device_type?type=${val}`);
    });
});

function showDeviceCfgSection(_type) {
    esp32CfgSection.style.display   = "";      // ESP32·Arduino 공통 UI
    arduinoCfgSection.style.display = "none";  // 사용 안 함
}

async function loadSettings(){
    try {
        const res  = await fetch("/settings");
        const data = await res.json();

        maxSpeed    = data.speed;

        speedSlider.value       = data.speed;
        speedValue.textContent  = data.speed;

        // Apply 3-way input mode (pointer/joystick/auto)
        const savedMode = data.input_mode || "joystick";
        setInputModeUI(savedMode);

        setDeviceTypeUI(data.device_type || "esp32");

        // Restore tracking thumbnail if target was learned
        if (data.tracking_mode === "custom") {
            setTargetUI("/target_thumbnail?t=" + Date.now());
        }

        // Restore learned ROI zone coordinates
        const lzRes = await fetch("/get_learn_zone");
        const lzData = await lzRes.json();
        currentLearnZone = { x: lzData.x, y: lzData.y, w: lzData.w, h: lzData.h };
    } catch(e) {
        console.log("Failed to load settings:", e);
    }
}


loadSettings();

/* ==========================================
   모터 상태창 (Motor Status Modal)
   ========================================== */
const motorStatusBtn   = document.getElementById("motor-status-btn");
const motorStatusModal = document.getElementById("motor-status-modal");
const closeMotorStatus = document.getElementById("close-motor-status");

function openMotorStatus()  { motorStatusModal.style.display = "flex"; loadAvailablePorts(); }
function closeMotorStatusModal() { motorStatusModal.style.display = "none"; }

motorStatusBtn.addEventListener("click", openMotorStatus);
closeMotorStatus.addEventListener("click", closeMotorStatusModal);
motorStatusModal.addEventListener("click", (e) => {
    if (e.target === motorStatusModal) closeMotorStatusModal();
});

// 연결 상태 dot (헤더)
const motorHeaderDot = document.getElementById("motor-status-dot");

// 상태창 내부 요소
const msConnBanner  = document.getElementById("ms-conn-banner");
const msConnLabel   = document.getElementById("ms-conn-label");
const msConnPort    = document.getElementById("ms-conn-port");
const msPortVal     = document.getElementById("ms-port-val");
const msStateDot    = document.getElementById("ms-state-dot");
const msStateText   = document.getElementById("ms-state-text");
const msTargetVal   = document.getElementById("ms-target-val");
const msExVal       = document.getElementById("ms-ex-val");
const msEyVal       = document.getElementById("ms-ey-val");
const msM1Steps     = document.getElementById("ms-m1-steps");
const msM2Steps     = document.getElementById("ms-m2-steps");
const msM1Bar       = document.getElementById("ms-m1-bar");
const msM2Bar       = document.getElementById("ms-m2-bar");

function _stateLabel(d) {
    if (!d.connected)  return ["disconnected", "연결 안됨"];
    if (d.stopped)     return ["stopped",  "정지됨"];
    if (d.timeout)     return ["timeout",  "타임아웃"];
    if (d.moving)      return ["moving",   "이동 중"];
    return ["idle", "대기"];
}

async function pollMotorStatus() {
    try {
        if (deviceType === "arduino") {
            // ── Arduino Uno 모드 ────────────────────────
            const res = await fetch("/arduino_motor_status");
            const d   = await res.json();

            motorHeaderDot.className = "motor-dot " +
                (d.connected ? "motor-dot-on" : "motor-dot-off");

            if (d.connected) {
                msConnBanner.className   = "ms-banner ms-banner-on";
                msConnLabel.textContent  = "연결됨";
                msConnPort.textContent   = d.port || "";
            } else {
                msConnBanner.className   = "ms-banner ms-banner-off";
                msConnLabel.textContent  = "연결 안됨";
                msConnPort.textContent   = "";
            }

            msPortVal.textContent   = d.port || "—";
            document.getElementById("ms-comm-val").textContent = "STEP / DIR (Arduino Uno)";
            msStateDot.className    = "ms-state-dot ms-state-idle";
            msStateText.textContent = d.connected ? "대기" : "연결 안됨";
            msTargetVal.textContent = `M1: ${d.pos_m1}  /  M2: ${d.pos_m2} step`;
            msExVal.textContent     = "—";
            msEyVal.textContent     = "—";
            msM1Steps.textContent   = `${d.pos_m1} step`;
            msM2Steps.textContent   = `${d.pos_m2} step`;
            msM1Bar.style.width     = "0%";
            msM2Bar.style.width     = "0%";

        } else {
            // ── ESP32 모드 ──────────────────────────────
            const res  = await fetch("/motor_status");
            const d    = await res.json();
            const [stKey, stLabel] = _stateLabel(d);

            motorHeaderDot.className = "motor-dot " +
                (d.connected ? "motor-dot-on" : "motor-dot-off");

            if (d.connected) {
                msConnBanner.className   = "ms-banner ms-banner-on";
                msConnLabel.textContent  = "연결됨";
                msConnPort.textContent   = d.port || "";
            } else {
                msConnBanner.className   = "ms-banner ms-banner-off";
                msConnLabel.textContent  = "연결 안됨";
                msConnPort.textContent   = "";
            }

            msPortVal.textContent   = d.port || "—";
            document.getElementById("ms-comm-val").textContent = "STEP / DIR (ESP32)";
            msStateDot.className    = "ms-state-dot ms-state-" + stKey;
            msStateText.textContent = stLabel;

            if (d.connected) {
                msTargetVal.textContent = `X ${d.target_x}  /  Y ${d.target_y}`;
                msExVal.textContent = `${d.error_x > 0 ? "+" : ""}${d.error_x} px`;
                msEyVal.textContent = `${d.error_y > 0 ? "+" : ""}${d.error_y} px`;
                msM1Steps.textContent = `${d.steps_m1} step`;
                msM2Steps.textContent = `${d.steps_m2} step`;
                const maxS = parseFloat(document.getElementById("cfg-max-steps")?.value || 25);
                msM1Bar.style.width = Math.min(100, (d.steps_m1 / maxS) * 100) + "%";
                msM2Bar.style.width = Math.min(100, (d.steps_m2 / maxS) * 100) + "%";
                msM1Bar.className = "ms-axis-fill " + (d.moving ? "ms-fill-moving" : "");
                msM2Bar.className = "ms-axis-fill " + (d.moving ? "ms-fill-moving" : "");
            } else {
                msTargetVal.textContent = "—";
                msExVal.textContent     = "—";
                msEyVal.textContent     = "—";
                msM1Steps.textContent   = "— step";
                msM2Steps.textContent   = "— step";
                msM1Bar.style.width     = "0%";
                msM2Bar.style.width     = "0%";
            }
        }
    } catch(e) {}
}

// 모달 열려 있을 때는 200ms, 닫혀 있을 때는 헤더 dot만 1초
let _lastMotorPoll = 0;
setInterval(() => {
    const now = Date.now();
    const interval = (motorStatusModal && motorStatusModal.style.display === "flex") ? 200 : 1000;
    if (now - _lastMotorPoll >= interval) {
        _lastMotorPoll = now;
        pollMotorStatus();
    }
}, 50);

/* ==========================================
   COM 포트 재연결 패널
   ========================================== */
const msPortSelect    = document.getElementById("ms-port-select");
const msReconnectBtn  = document.getElementById("ms-reconnect-btn");
const msReconnectMsg  = document.getElementById("ms-reconnect-msg");

// 모터 상태 모달이 열릴 때 포트 목록 자동 새로고침
// (motorStatusBtn은 982번 라인에서 이미 선언됨 — 중복 const 방지)


async function loadAvailablePorts() {
    try {
        const res = await fetch("/available_ports");
        const d   = await res.json();

        if (!msPortSelect) return;
        // 기존 옵션 초기화 (자동 감지 유지)
        msPortSelect.innerHTML = '<option value="">자동 감지</option>';
        d.ports.forEach(p => {
            const opt = document.createElement("option");
            opt.value = p.device;
            opt.textContent = `${p.device} — ${p.description}`;
            // 현재 연결된 포트 선택 상태로
            if (p.device === d.current_port) opt.selected = true;
            msPortSelect.appendChild(opt);
        });
        if (msReconnectMsg) {
            msReconnectMsg.textContent = d.connected
                ? `✓ 현재 ${d.current_port} 연결됨`
                : "연결되지 않음 — 아래에서 포트를 선택하고 연결하세요";
            msReconnectMsg.style.color = d.connected ? "#30d158" : "rgba(235,235,245,0.5)";
        }
    } catch(e) {}
}

if (msReconnectBtn) {
    msReconnectBtn.addEventListener("click", async () => {
        const port = msPortSelect ? msPortSelect.value : "";
        msReconnectBtn.textContent = "연결 중…";
        msReconnectBtn.disabled = true;

        try {
            const url = port ? `/reconnect_esp32?port=${encodeURIComponent(port)}` : "/reconnect_esp32";
            const res = await fetch(url);
            const d   = await res.json();

            if (d.ok) {
                if (msReconnectMsg) {
                    msReconnectMsg.textContent = `✓ ${d.port} 연결 성공!`;
                    msReconnectMsg.style.color = "#30d158";
                }
                msReconnectBtn.textContent = "✓ 연결됨";
                msReconnectBtn.style.background = "rgba(48,209,88,0.20)";
                msReconnectBtn.style.borderColor = "rgba(48,209,88,0.40)";
                msReconnectBtn.style.color = "#30d158";
                // 포트 목록 새로고침
                setTimeout(loadAvailablePorts, 500);
            } else {
                if (msReconnectMsg) {
                    msReconnectMsg.textContent = "❌ 연결 실패 — 아두이노 IDE 시리얼 모니터를 닫고 다시 시도하세요";
                    msReconnectMsg.style.color = "#ff3b30";
                }
                msReconnectBtn.textContent = "🔌 연결";
                msReconnectBtn.disabled = false;
            }
        } catch(e) {
            if (msReconnectMsg) {
                msReconnectMsg.textContent = "❌ 서버 오류";
                msReconnectMsg.style.color = "#ff3b30";
            }
            msReconnectBtn.textContent = "🔌 연결";
            msReconnectBtn.disabled = false;
        }
        // 버튼 상태 복원 (3초 후)
        setTimeout(() => {
            msReconnectBtn.textContent = "🔌 연결";
            msReconnectBtn.disabled = false;
            msReconnectBtn.style.background = "";
            msReconnectBtn.style.borderColor = "";
            msReconnectBtn.style.color = "#007aff";
        }, 3000);
    });
}

/* ==========================================
   모터 설정창 (Motor Config Modal)
   ========================================== */
const btnOpenMotorCfg  = document.getElementById("btn-open-motor-settings");
const motorCfgModal    = document.getElementById("motor-cfg-modal");
const closeMotorCfg    = document.getElementById("close-motor-cfg");

function openMotorCfg() {
    settingsModal.style.display = "none";
    showDeviceCfgSection(deviceType);
    motorCfgModal.style.display = "flex";
    loadMotorSettings();
    loadEsp32MmSettings();
}
function closeMotorCfgModal() {
    motorCfgModal.style.display = "none";
    if (_ardPosPollTimer) { clearInterval(_ardPosPollTimer); _ardPosPollTimer = null; }
    if (typeof esp32Mode !== "undefined" && esp32Mode === "pos") stopKlipperPoll();
}

btnOpenMotorCfg.addEventListener("click", openMotorCfg);
closeMotorCfg.addEventListener("click", closeMotorCfgModal);
motorCfgModal.addEventListener("click", (e) => {
    if (e.target === motorCfgModal) closeMotorCfgModal();
});

// 슬라이더 + 값 표시 헬퍼
// ── 모터 설정 (현재 HTML의 숫자 입력창 기반으로 참조) ──
// HTML에는 슬라이더가 아닌 number input + apply button 구조
// cfg-steps-per-px, cfg-max-steps, cfg-pulse-us 슬라이더는 제거됨
// → cfgDeadZone, cfgTimeout 슬라이더만 유지, 나머지는 klipper-param-apply 버튼으로 동작
const cfgDeadZone  = document.getElementById("cfg-dead-zone");
const cfgDeadZoneV = document.getElementById("cfg-dead-zone-val");
const cfgTimeout   = document.getElementById("cfg-timeout");
const cfgTimeoutV  = document.getElementById("cfg-timeout-val");
const cfgM1Btn     = document.getElementById("cfg-m1-invert");
const cfgM2Btn     = document.getElementById("cfg-m2-invert");
const cfgApplyMsg  = document.getElementById("cfg-apply-msg");

if (cfgDeadZone) cfgDeadZone.addEventListener("input", () => {
    if (cfgDeadZoneV) cfgDeadZoneV.textContent = cfgDeadZone.value;
});
if (cfgTimeout) cfgTimeout.addEventListener("input", () => {
    if (cfgTimeoutV) cfgTimeoutV.textContent = cfgTimeout.value;
});

function toggleInvertBtn(btn) {
    const active = btn.dataset.active === "true";
    btn.dataset.active = (!active).toString();
    btn.textContent = active ? "OFF" : "ON";
    btn.classList.toggle("cfg-toggle-active", !active);
}
if (cfgM1Btn) cfgM1Btn.addEventListener("click", () => toggleInvertBtn(cfgM1Btn));
if (cfgM2Btn) cfgM2Btn.addEventListener("click", () => toggleInvertBtn(cfgM2Btn));

// 설정값 불러오기
async function loadMotorSettings() {
    try {
        const res = await fetch("/motor_settings");
        const d   = await res.json();

        // 숫자 입력창에 현재 값 반영
        const stepsPxNum = document.getElementById("cfg-steps-per-px-num");
        if (stepsPxNum) stepsPxNum.value = d.steps_per_px;

        const maxSpeedEl = document.getElementById("cfg-max-speed-hz");
        if (maxSpeedEl) maxSpeedEl.value = d.max_speed_hz ?? 3000;

        const accelEl = document.getElementById("cfg-accel-rate");
        if (accelEl) accelEl.value = d.accel_rate ?? 8.0;

        if (cfgDeadZone) { cfgDeadZone.value = d.dead_zone; }
        if (cfgDeadZoneV) cfgDeadZoneV.textContent = d.dead_zone;

        if (cfgTimeout) { cfgTimeout.value = d.cmd_timeout_ms; }
        if (cfgTimeoutV) cfgTimeoutV.textContent = d.cmd_timeout_ms;

        if (cfgM1Btn) {
            cfgM1Btn.dataset.active = d.m1_invert.toString();
            cfgM1Btn.textContent    = d.m1_invert ? "ON" : "OFF";
            cfgM1Btn.classList.toggle("cfg-toggle-active", d.m1_invert);
        }
        if (cfgM2Btn) {
            cfgM2Btn.dataset.active = d.m2_invert.toString();
            cfgM2Btn.textContent    = d.m2_invert ? "ON" : "OFF";
            cfgM2Btn.classList.toggle("cfg-toggle-active", d.m2_invert);
        }
    } catch(e) { console.warn('[loadMotorSettings]', e); }
}

loadMotorSettings();

// 보드에 적용 (ESP32 / Arduino 공통 핸들러)
const cfgBtnApply = document.getElementById("cfg-btn-apply");
if (cfgBtnApply) cfgBtnApply.addEventListener("click", async () => {
    const params = [
        ["dead_zone",      cfgDeadZone ? cfgDeadZone.value : 8],
        ["cmd_timeout_ms", cfgTimeout  ? cfgTimeout.value  : 600],
        ["m1_invert",      cfgM1Btn ? cfgM1Btn.dataset.active : 'false'],
        ["m2_invert",      cfgM2Btn ? cfgM2Btn.dataset.active : 'false'],
    ];

    try {
        await Promise.all(params.map(([k, v]) =>
            fetch(`/set_motor_config?key=${k}&value=${v}`)
        ));

        if (deviceType === "arduino") {
            const res = await fetch("/apply_arduino_cfg");
            if (!res.ok) throw new Error("NOT_CONNECTED");
            if (cfgApplyMsg) cfgApplyMsg.textContent = "✓ Arduino에 적용 완료";
        } else {
            if (cfgApplyMsg) cfgApplyMsg.textContent = "✓ ESP32에 적용 완료";
        }
        if (cfgApplyMsg) cfgApplyMsg.style.color = "#30d158";
    } catch(e) {
        if (cfgApplyMsg) {
            cfgApplyMsg.textContent = (e.message === "NOT_CONNECTED") ? "✗ Arduino 연결 안됨" : "✗ 적용 실패";
            cfgApplyMsg.style.color = "#ff453a";
        }
    }
    setTimeout(() => { if (cfgApplyMsg) cfgApplyMsg.textContent = ""; }, 2500);
});

// 기본값 복원
const cfgBtnReset = document.getElementById("cfg-btn-reset");
if (cfgBtnReset) cfgBtnReset.addEventListener("click", () => {
    if (cfgDeadZone)  { cfgDeadZone.value  = 8;   }
    if (cfgDeadZoneV)   cfgDeadZoneV.textContent  = "8";
    if (cfgTimeout)   { cfgTimeout.value   = 600; }
    if (cfgTimeoutV)    cfgTimeoutV.textContent   = "600";
    if (cfgM1Btn) { cfgM1Btn.dataset.active = "false"; cfgM1Btn.textContent = "OFF"; cfgM1Btn.classList.remove("cfg-toggle-active"); }
    if (cfgM2Btn) { cfgM2Btn.dataset.active = "false"; cfgM2Btn.textContent = "OFF"; cfgM2Btn.classList.remove("cfg-toggle-active"); }
});

/* ==========================================
   Arduino Uno 스텝모터 (DM542) 제어창
   ========================================== */
const ardEstopBtn  = document.getElementById("ard-estop-btn");
const ardStepsRev  = document.getElementById("ard-steps-rev");
const ardStepsRevV = document.getElementById("ard-steps-rev-val");
const ardM1Deg     = document.getElementById("ard-m1-deg");
const ardM1DegV    = document.getElementById("ard-m1-deg-val");
const ardM1Spd     = document.getElementById("ard-m1-spd");
const ardM1SpdV    = document.getElementById("ard-m1-spd-val");
const ardM1Acc     = document.getElementById("ard-m1-acc");
const ardM1AccV    = document.getElementById("ard-m1-acc-val");
const ardM1RunBtn  = document.getElementById("ard-m1-run-btn");
const ardM1HomeBtn = document.getElementById("ard-m1-home-btn");
const ardM2Deg     = document.getElementById("ard-m2-deg");
const ardM2DegV    = document.getElementById("ard-m2-deg-val");
const ardM2Spd     = document.getElementById("ard-m2-spd");
const ardM2SpdV    = document.getElementById("ard-m2-spd-val");
const ardM2Acc     = document.getElementById("ard-m2-acc");
const ardM2AccV    = document.getElementById("ard-m2-acc-val");
const ardM2RunBtn  = document.getElementById("ard-m2-run-btn");
const ardM2HomeBtn = document.getElementById("ard-m2-home-btn");
const ardPosM1     = document.getElementById("ard-pos-m1");
const ardPosM2     = document.getElementById("ard-pos-m2");
const ardSaveBtn   = document.getElementById("ard-save-btn");
const ardApplyMsg  = document.getElementById("ard-apply-msg");

ardStepsRev.addEventListener("input", () => { ardStepsRevV.textContent = ardStepsRev.value; });
ardM1Deg.addEventListener("input",    () => { ardM1DegV.textContent = ardM1Deg.value + "°"; });
ardM1Spd.addEventListener("input",    () => { ardM1SpdV.textContent = ardM1Spd.value; });
ardM1Acc.addEventListener("input",    () => { ardM1AccV.textContent = ardM1Acc.value; });
ardM2Deg.addEventListener("input",    () => { ardM2DegV.textContent = ardM2Deg.value + "°"; });
ardM2Spd.addEventListener("input",    () => { ardM2SpdV.textContent = ardM2Spd.value; });
ardM2Acc.addEventListener("input",    () => { ardM2AccV.textContent = ardM2Acc.value; });

function _ardMsg(text, color, ms = 2500) {
    ardApplyMsg.textContent = text;
    ardApplyMsg.style.color = color;
    setTimeout(() => { ardApplyMsg.textContent = ""; }, ms);
}

/* 비상 정지 */
ardEstopBtn.addEventListener("click", async () => {
    try {
        const res = await fetch("/arduino_estop");
        if (res.ok) _ardMsg("⏹ 비상 정지 전송 완료", "#ff453a");
        else        _ardMsg("✗ 연결 안됨", "#ff453a");
    } catch(e) { _ardMsg("✗ 전송 실패", "#ff453a"); }
});

/* M1 RUN — Apply 시 단 1회 JSON 전송 */
ardM1RunBtn.addEventListener("click", async () => {
    try {
        const p = new URLSearchParams({
            id: 1, deg: ardM1Deg.value,
            spd: ardM1Spd.value, acc: ardM1Acc.value,
        });
        const res = await fetch(`/arduino_run?${p}`);
        if (res.ok) _ardMsg("✓ M1 RUN 전송", "#30d158");
        else        _ardMsg("✗ 연결 안됨", "#ff453a");
    } catch(e) { _ardMsg("✗ 전송 실패", "#ff453a"); }
});

/* M1 HOME */
ardM1HomeBtn.addEventListener("click", async () => {
    try {
        const res = await fetch("/arduino_home?id=1");
        if (res.ok) _ardMsg("✓ M1 HOME 전송", "#30d158");
        else        _ardMsg("✗ 연결 안됨", "#ff453a");
    } catch(e) { _ardMsg("✗ 전송 실패", "#ff453a"); }
});

/* M2 RUN */
ardM2RunBtn.addEventListener("click", async () => {
    try {
        const p = new URLSearchParams({
            id: 2, deg: ardM2Deg.value,
            spd: ardM2Spd.value, acc: ardM2Acc.value,
        });
        const res = await fetch(`/arduino_run?${p}`);
        if (res.ok) _ardMsg("✓ M2 RUN 전송", "#30d158");
        else        _ardMsg("✗ 연결 안됨", "#ff453a");
    } catch(e) { _ardMsg("✗ 전송 실패", "#ff453a"); }
});

/* M2 HOME */
ardM2HomeBtn.addEventListener("click", async () => {
    try {
        const res = await fetch("/arduino_home?id=2");
        if (res.ok) _ardMsg("✓ M2 HOME 전송", "#30d158");
        else        _ardMsg("✗ 연결 안됨", "#ff453a");
    } catch(e) { _ardMsg("✗ 전송 실패", "#ff453a"); }
});

/* 파라미터 저장 (서버 state에만 기록, Arduino로는 전송 안 함) */
ardSaveBtn.addEventListener("click", async () => {
    try {
        await Promise.all([
            fetch(`/set_arduino_motor_config?key=steps_per_rev&value=${ardStepsRev.value}`),
            fetch(`/set_arduino_motor_config?key=m1_max_speed&value=${ardM1Spd.value}`),
            fetch(`/set_arduino_motor_config?key=m1_accel&value=${ardM1Acc.value}`),
            fetch(`/set_arduino_motor_config?key=m2_max_speed&value=${ardM2Spd.value}`),
            fetch(`/set_arduino_motor_config?key=m2_accel&value=${ardM2Acc.value}`),
        ]);
        _ardMsg("✓ 파라미터 저장 완료", "#30d158");
    } catch(e) { _ardMsg("✗ 저장 실패", "#ff453a"); }
});

/* 설정값 불러오기 */
async function loadArduinoSettings() {
    try {
        const res = await fetch("/arduino_motor_settings");
        const d   = await res.json();
        ardStepsRev.value = d.steps_per_rev; ardStepsRevV.textContent = d.steps_per_rev;
        ardM1Spd.value = d.m1_max_speed;     ardM1SpdV.textContent    = d.m1_max_speed;
        ardM1Acc.value = d.m1_accel;         ardM1AccV.textContent    = d.m1_accel;
        ardM2Spd.value = d.m2_max_speed;     ardM2SpdV.textContent    = d.m2_max_speed;
        ardM2Acc.value = d.m2_accel;         ardM2AccV.textContent    = d.m2_accel;
    } catch(e) {}
}

/* 위치 폴링 — 모달 열려 있을 때만 실행 */
let _ardPosPollTimer = null;

async function _pollArduinoPos() {
    try {
        const res = await fetch("/arduino_motor_status");
        const d   = await res.json();
        ardPosM1.textContent = `${d.pos_m1} step`;
        ardPosM2.textContent = `${d.pos_m2} step`;
    } catch(e) {}
}

/* ==========================================
   Klipper 스타일 ESP32 mm 위치 제어
   ========================================== */

// ── 상태 변수 ──────────────────────────────────────────────────────────────────────
let klipperAxis   = "M1";        // 현재 선택된 축
let klipperPosM1  = 0.0;         // M1 현재 위치 (mm)
let klipperPosM2  = 0.0;         // M2 현재 위치 (mm)
let klipperPollTimer = null;     // 위치 폴링 타이머
let esp32Mode = "track";         // 현재 ESP32 모드

// ── 요소 참조 ──────────────────────────────────────────────────────────────────────
const esp32ModeSegment = document.getElementById("esp32-mode-segment");
const esp32TrackTab    = document.getElementById("esp32-track-tab");
const esp32PosTab      = document.getElementById("esp32-pos-tab");
const mmAxisSegment    = document.getElementById("mm-axis-segment");
const kpAbsInput       = document.getElementById("kp-abs-input");
const kpAbsGo          = document.getElementById("kp-abs-go");
const kpSethomeBtn     = document.getElementById("kp-sethome-btn");
const kpEstopBtn       = document.getElementById("kp-estop-btn");
const kpApplyMsg       = document.getElementById("kp-apply-msg");

// ── 탭 전환 (추적 / 위치 제어) ────────────────────────────────────────────────────
if (esp32ModeSegment) {
    esp32ModeSegment.addEventListener("click", e => {
        const btn = e.target.closest(".segment-btn");
        if (!btn) return;

        // 슬라이더 이동
        const btns  = [...esp32ModeSegment.querySelectorAll(".segment-btn")];
        const idx   = btns.indexOf(btn);
        const slider = esp32ModeSegment.querySelector(".segment-slider");
        btns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        slider.style.transform = `translateX(${idx * 100}%)`;

        const mode = btn.dataset.value;
        esp32Mode = mode;

        if (mode === "track") {
            if (esp32TrackTab) esp32TrackTab.style.display = "";
            if (esp32PosTab)   esp32PosTab.style.display = "none";
            stopKlipperPoll();
            fetch("/esp32_set_mode?mode=track");
        } else {
            if (esp32TrackTab) esp32TrackTab.style.display = "none";
            if (esp32PosTab)   esp32PosTab.style.display = "";
            fetch("/esp32_set_mode?mode=pos");
            startKlipperPoll();
        }
    });
}

// ── 축 선택 세그먼트 ─────────────────────────────────────────────────────────────
if (mmAxisSegment) {
    mmAxisSegment.addEventListener("click", e => {
        const btn = e.target.closest(".segment-btn");
        if (!btn) return;
        const btns  = [...mmAxisSegment.querySelectorAll(".segment-btn")];
        const idx   = btns.indexOf(btn);
        const slider = mmAxisSegment.querySelector(".segment-slider");
        btns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        slider.style.transform = `translateX(${idx * 100}%)`;
        klipperAxis = btn.dataset.value;
    });
}

// ── Jog 버튼 (상대 이동) ─────────────────────────────────────────────────────────
document.querySelectorAll(".klipper-jog-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
        const delta = parseFloat(btn.dataset.delta);
        if (isNaN(delta)) return;

        // 상대 이동(delta) 요청을 전송하여 백엔드 큐에서 순차 처리되도록 함
        await klipperMove(klipperAxis, null, delta);

        // UI 입력창에 예상 도달 위치 업데이트
        let curPos = (klipperAxis === "M1") ? klipperPosM1 : ((klipperAxis === "M2") ? klipperPosM2 : klipperPosM1);
        const targetMM = curPos + delta;
        if (kpAbsInput) kpAbsInput.value = targetMM.toFixed(2);
    });
});

// ── 절대 위치 이동 버튼 ───────────────────────────────────────────────────────────
if (kpAbsGo) {
    kpAbsGo.addEventListener("click", async () => {
        const mm = parseFloat(kpAbsInput?.value || 0);
        if (isNaN(mm)) return;
        await klipperMove(klipperAxis, mm);
    });
}

if (kpAbsInput) {
    kpAbsInput.addEventListener("keydown", async e => {
        if (e.key === "Enter") {
            e.preventDefault();
            const mm = parseFloat(kpAbsInput.value || 0);
            if (!isNaN(mm)) await klipperMove(klipperAxis, mm);
        }
    });
}

// ── SET HOME ─────────────────────────────────────────────────────────────────────
if (kpSethomeBtn) {
    kpSethomeBtn.addEventListener("click", async () => {
        try {
            await fetch("/esp32_sethome");
            klipperPosM1 = 0.0;
            klipperPosM2 = 0.0;
            updateKlipperGauge(0, 0, 0, 0);
            if (kpAbsInput) kpAbsInput.value = "0";
            showKlipperMsg("✓ 원점 설정 완료", "#30d158");
        } catch(e) {
            showKlipperMsg("❌ 연결 없음", "#ff3b30");
        }
    });
}

// ── E-STOP ────────────────────────────────────────────────────────────────────────
if (kpEstopBtn) {
    kpEstopBtn.addEventListener("click", async () => {
        try {
            await fetch("/esp32_stop");
            showKlipperMsg("⏹ 비상 정지 완료", "#ff9f0a");
        } catch(e) {}
    });
}

// ── 파라미터 카드 '적용' 버튼 ─────────────────────────────────────────────────────
document.querySelectorAll(".klipper-param-apply").forEach(btn => {
    btn.addEventListener("click", async () => {
        const key   = btn.dataset.key;
        const srcId = btn.dataset.src;
        const input = document.getElementById(srcId);
        if (!input) return;

        const value = input.value;
        try {
            const res = await fetch(`/set_esp32_mm_config?key=${key}&value=${encodeURIComponent(value)}`);
            if (res.ok) {
                // 부모 카드에 초록 플래시 효과
                const card = btn.closest(".klipper-param-card");
                if (card) {
                    card.classList.remove("flash-ok");
                    void card.offsetWidth; // reflow
                    card.classList.add("flash-ok");
                }
                showKlipperMsg(`✓ ${key} = ${value} 적용됨`, "#30d158");
            } else {
                showKlipperMsg("❌ 적용 실패", "#ff3b30");
            }
        } catch(e) {
            showKlipperMsg("❌ 서버 연결 오류", "#ff3b30");
        }
    });
});

// 방향 반전 토글 (위치 제어 탭)
const kpM1Inv = document.getElementById("kp-m1-invert");
const kpM2Inv = document.getElementById("kp-m2-invert");

function bindKlipperInvert(btn, key) {
    if (!btn) return;
    btn.addEventListener("click", async () => {
        const cur = btn.dataset.active === "true";
        const next = !cur;
        btn.dataset.active = next ? "true" : "false";
        btn.textContent    = next ? "ON" : "OFF";
        btn.style.background = next
            ? "rgba(48,209,88,0.25)"
            : "rgba(255,255,255,0.08)";
        btn.style.color = next ? "#30d158" : "";
        await fetch(`/set_esp32_mm_config?key=${key}&value=${next}`);
    });
}

bindKlipperInvert(kpM1Inv, "m1_invert");
bindKlipperInvert(kpM2Inv, "m2_invert");

// ── 핵심 이동 함수 ────────────────────────────────────────────────────────────────
async function klipperMove(axis, mm, delta = null) {
    try {
        let url;
        if (delta !== null) {
            url = `/esp32_move?target=${encodeURIComponent(axis)}&delta=${delta.toFixed(3)}`;
        } else {
            url = `/esp32_move?target=${encodeURIComponent(axis)}&mm=${mm.toFixed(3)}`;
        }
        const res = await fetch(url);
        if (!res.ok) {
            showKlipperMsg("❌ 연결 없음 (ESP32)", "#ff3b30");
        }
    } catch(e) {
        showKlipperMsg("❌ 서버 오류", "#ff3b30");
    }
}

// ── 실시간 위치 폴링 ──────────────────────────────────────────────────────────────
function startKlipperPoll() {
    if (klipperPollTimer) return;
    klipperPollTimer = setInterval(pollKlipperPos, 200);
}

function stopKlipperPoll() {
    if (klipperPollTimer) {
        clearInterval(klipperPollTimer);
        klipperPollTimer = null;
    }
}

async function pollKlipperPos() {
    try {
        const res = await fetch("/esp32_pos_status");
        if (!res.ok) return;
        const d = await res.json();
        klipperPosM1 = d.pos_m1_mm ?? 0;
        klipperPosM2 = d.pos_m2_mm ?? 0;
        updateKlipperGauge(klipperPosM1, klipperPosM2, d.speed_m1 ?? 0, d.speed_m2 ?? 0);
    } catch(e) {}
}

// ── 위치 게이지 업데이트 ──────────────────────────────────────────────────────────
const POS_RANGE = 200; // ±200mm 범위로 게이지 표시

function updateKlipperGauge(m1mm, m2mm, spd1, spd2) {
    const m1Val  = document.getElementById("kp-m1-val");
    const m2Val  = document.getElementById("kp-m2-val");
    const m1Fill = document.getElementById("kp-m1-fill");
    const m2Fill = document.getElementById("kp-m2-fill");
    const m1Spd  = document.getElementById("kp-m1-spd");
    const m2Spd  = document.getElementById("kp-m2-spd");

    if (m1Val) m1Val.textContent = m1mm.toFixed(2) + " mm";
    if (m2Val) m2Val.textContent = m2mm.toFixed(2) + " mm";

    if (m1Fill) {
        // 0mm = 50%, +POS_RANGE = 100%, -POS_RANGE = 0%
        const pct1 = Math.min(100, Math.max(0, 50 + (m1mm / POS_RANGE) * 50));
        m1Fill.style.width = pct1 + "%";
        m1Fill.classList.toggle("is-moving", spd1 > 10);
    }
    if (m2Fill) {
        const pct2 = Math.min(100, Math.max(0, 50 + (m2mm / POS_RANGE) * 50));
        m2Fill.style.width = pct2 + "%";
        m2Fill.classList.toggle("is-moving", spd2 > 10);
    }

    if (m1Spd) m1Spd.textContent = Math.round(spd1) + " Hz";
    if (m2Spd) m2Spd.textContent = Math.round(spd2) + " Hz";
}

// ── 메시지 표시 ──────────────────────────────────────────────────────────────────
function showKlipperMsg(text, color = "#fff") {
    if (!kpApplyMsg) return;
    kpApplyMsg.textContent  = text;
    kpApplyMsg.style.color  = color;
    kpApplyMsg.style.opacity = "1";
    setTimeout(() => { kpApplyMsg.style.opacity = "0"; }, 2500);
}

// ── 초기 파라미터 로드 ────────────────────────────────────────────────────────────
async function loadEsp32MmSettings() {
    try {
        const res = await fetch("/esp32_mm_settings");
        if (!res.ok) return;
        const d = await res.json();

        // ── 위치 제어(mm) 탭 파라미터 ──
        const spm1El   = document.getElementById("kp-spm1");
        const spm2El   = document.getElementById("kp-spm2");
        const maxSpdEl = document.getElementById("kp-maxspd");
        const accelEl  = document.getElementById("kp-accel");
        const pulsEl   = document.getElementById("kp-pulseus");

        if (spm1El)   spm1El.value   = d.steps_per_mm_m1;
        if (spm2El)   spm2El.value   = d.steps_per_mm_m2;
        if (maxSpdEl) maxSpdEl.value = d.max_speed_hz;
        if (accelEl)  accelEl.value  = d.accel_rate;
        if (pulsEl)   pulsEl.value   = d.pulse_us;

        // ── 카메라 추적 탭 파라미터 (새로 추가된 필드) ──
        const spxEl      = document.getElementById("cfg-steps-per-px-num");
        const trackSpdEl = document.getElementById("cfg-max-speed-hz");
        const trackAccEl = document.getElementById("cfg-accel-rate");

        if (spxEl)      spxEl.value      = d.steps_per_px  ?? d.steps_per_px  ?? 3.5;
        if (trackSpdEl) trackSpdEl.value = d.max_speed_hz;
        if (trackAccEl) trackAccEl.value = d.accel_rate;

        // 방향 반전 상태 반영
        [kpM1Inv, kpM2Inv].forEach((btn, i) => {
            if (!btn) return;
            const active = i === 0 ? d.m1_invert : d.m2_invert;
            btn.dataset.active = active ? "true" : "false";
            btn.textContent    = active ? "ON" : "OFF";
            btn.style.background = active ? "rgba(48,209,88,0.25)" : "";
            btn.style.color      = active ? "#30d158" : "";
        });

        // 현재 ESP32 모드 반영
        if (d.control_mode === "pos") {
            // 탭을 위치 제어로 전환
            const btns = [...(esp32ModeSegment?.querySelectorAll(".segment-btn") || [])];
            btns.forEach(b => b.classList.remove("active"));
            const posBtn = btns.find(b => b.dataset.value === "pos");
            if (posBtn) posBtn.classList.add("active");
            const slider = esp32ModeSegment?.querySelector(".segment-slider");
            if (slider) slider.style.transform = "translateX(100%)";
            if (esp32TrackTab) esp32TrackTab.style.display = "none";
            if (esp32PosTab)   esp32PosTab.style.display = "";
            esp32Mode = "pos";
            startKlipperPoll();
        }
    } catch(e) {}
}

// 모터 설정 모달이 열릴 때 Klipper 파라미터 로드
// (btnOpenMotorSettings는 위에서 이미 선언됨 — 중복 const 방지)


/* ==========================================
   카메라 설정 모달
   ========================================== */

const cameraCfgModal    = document.getElementById("camera-cfg-modal");
const closeCameraCfgBtn = document.getElementById("close-camera-cfg");
const btnOpenCameraSettings = document.getElementById("btn-open-camera-settings");
const camIndexSelect    = document.getElementById("cam-index-select");
const camRefreshBtn     = document.getElementById("cam-refresh-btn");
const camConnectBtn     = document.getElementById("cam-connect-btn");
const camConnectMsg     = document.getElementById("cam-connect-msg");
const camStatusBanner   = document.getElementById("cam-status-banner");
const camStatusDot      = document.getElementById("cam-status-dot");
const camStatusLabel    = document.getElementById("cam-status-label");
const camFlipToggle     = document.getElementById("cam-flip-toggle");
const camResSelect      = document.getElementById("cam-res-select");
const camFpsSelect      = document.getElementById("cam-fps-select");

function openCameraSettings() {
    settingsModal.style.display = "none";
    cameraCfgModal.style.display = "flex";
    loadCameraSettings();
}

function closeCameraSettings() {
    cameraCfgModal.style.display = "none";
}

if (btnOpenCameraSettings) {
    btnOpenCameraSettings.addEventListener("click", openCameraSettings);
}
if (closeCameraCfgBtn) {
    closeCameraCfgBtn.addEventListener("click", closeCameraSettings);
}
if (cameraCfgModal) {
    cameraCfgModal.addEventListener("click", (e) => {
        if (e.target === cameraCfgModal) closeCameraSettings();
    });
}

// Load current camera info from server
async function loadCameraSettings() {
    try {
        const res  = await fetch("/camera_settings");
        const data = await res.json();

        // Update info card
        const idxEl    = document.getElementById("cam-info-index");
        const resEl    = document.getElementById("cam-info-res");
        const fpsEl    = document.getElementById("cam-info-fps");
        const statEl   = document.getElementById("cam-info-status");

        if (idxEl)  idxEl.textContent  = `Camera ${data.index}`;
        if (resEl)  resEl.textContent  = `${data.width} × ${data.height}`;
        if (fpsEl)  fpsEl.textContent  = `${data.fps} fps`;
        if (statEl) statEl.textContent = data.is_dummy ? "더미 (카메라 없음)" : "정상 연결됨";

        // Status banner
        if (camStatusBanner && camStatusDot && camStatusLabel) {
            if (data.is_dummy) {
                camStatusBanner.className = "ms-banner ms-banner-off";
                camStatusDot.style.background = "#ff3b30";
                camStatusDot.style.boxShadow  = "0 0 5px #ff3b30";
                camStatusLabel.textContent = "카메라가 감지되지 않았습니다";
            } else {
                camStatusBanner.className = "ms-banner ms-banner-on";
                camStatusDot.style.background = "#30d158";
                camStatusDot.style.boxShadow  = "0 0 5px #30d158";
                camStatusLabel.textContent = `Camera ${data.index} 연결됨`;
            }
        }

        // Flip toggle sync
        if (camFlipToggle) {
            camFlipToggle.dataset.active = data.flip ? "true" : "false";
            camFlipToggle.textContent    = data.flip ? "ON" : "OFF";
            camFlipToggle.style.background = data.flip
                ? "rgba(48,209,88,0.25)" : "rgba(255,255,255,0.08)";
            camFlipToggle.style.color = data.flip ? "#30d158" : "";
        }

        // Set select to current index
        if (camIndexSelect) {
            camIndexSelect.value = String(data.index);
        }

        // Populate and set Resolution select
        if (camResSelect && data.res_presets) {
            camResSelect.innerHTML = "";
            data.res_presets.forEach(res => {
                const opt = document.createElement("option");
                const val = `${res[0]},${res[1]}`;
                opt.value = val;
                opt.textContent = `${res[0]} × ${res[1]}`;
                if (res[0] === data.width && res[1] === data.height) {
                    opt.selected = true;
                }
                camResSelect.appendChild(opt);
            });
            // If current resolution is not in presets, add it
            if (!data.res_presets.some(res => res[0] === data.width && res[1] === data.height)) {
                const opt = document.createElement("option");
                const val = `${data.width},${data.height}`;
                opt.value = val;
                opt.textContent = `${data.width} × ${data.height} (Custom)`;
                opt.selected = true;
                camResSelect.appendChild(opt);
            }
        }

        // Populate and set FPS select
        if (camFpsSelect && data.fps_presets) {
            camFpsSelect.innerHTML = "";
            const currentFps = Math.round(data.fps); // round to handle 30.00003
            data.fps_presets.forEach(fps => {
                const opt = document.createElement("option");
                opt.value = String(fps);
                opt.textContent = `${fps} fps`;
                if (fps === currentFps) {
                    opt.selected = true;
                }
                camFpsSelect.appendChild(opt);
            });
            if (!data.fps_presets.includes(currentFps)) {
                const opt = document.createElement("option");
                opt.value = String(currentFps);
                opt.textContent = `${currentFps} fps (Custom)`;
                opt.selected = true;
                camFpsSelect.appendChild(opt);
            }
        }

    } catch(e) {
        console.warn("Failed to load camera settings:", e);
    }
}

// Probe available cameras
if (camRefreshBtn) {
    camRefreshBtn.addEventListener("click", async () => {
        camRefreshBtn.textContent = "탐색 중...";
        camRefreshBtn.disabled = true;
        try {
            const res  = await fetch("/list_cameras");
            const data = await res.json();

            if (!camIndexSelect) return;
            const currentVal = camIndexSelect.value;
            camIndexSelect.innerHTML = "";

            if (data.cameras.length === 0) {
                const opt = document.createElement("option");
                opt.value = "0";
                opt.textContent = "감지된 카메라 없음";
                camIndexSelect.appendChild(opt);
            } else {
                data.cameras.forEach(idx => {
                    const opt = document.createElement("option");
                    opt.value = String(idx);
                    opt.textContent = `Camera ${idx}`;
                    if (String(idx) === currentVal) opt.selected = true;
                    camIndexSelect.appendChild(opt);
                });
            }
            if (camConnectMsg) {
                camConnectMsg.textContent = `${data.cameras.length}개 카메라 감지됨`;
                camConnectMsg.style.color = "#30d158";
            }
        } catch(e) {
            if (camConnectMsg) {
                camConnectMsg.textContent = "탐색 실패";
                camConnectMsg.style.color = "#ff3b30";
            }
        }
        camRefreshBtn.textContent = "🔍 탐색";
        camRefreshBtn.disabled = false;
    });
}

// Switch camera
if (camConnectBtn) {
    camConnectBtn.addEventListener("click", async () => {
        const index = parseInt(camIndexSelect?.value || "0");
        camConnectBtn.textContent = "전환 중...";
        camConnectBtn.disabled = true;
        try {
            const res  = await fetch(`/set_camera?index=${index}`);
            const data = await res.json();
            if (data.ok) {
                if (camConnectMsg) {
                    camConnectMsg.textContent = `✓ Camera ${index} 전환 완료`;
                    camConnectMsg.style.color = "#30d158";
                }
                setTimeout(loadCameraSettings, 800);
            } else {
                if (camConnectMsg) {
                    camConnectMsg.textContent = `❌ Camera ${index} 열기 실패`;
                    camConnectMsg.style.color = "#ff3b30";
                }
            }
        } catch(e) {
            if (camConnectMsg) {
                camConnectMsg.textContent = "서버 오류";
                camConnectMsg.style.color = "#ff3b30";
            }
        }
        camConnectBtn.textContent = "📷 적용";
        camConnectBtn.disabled = false;
        setTimeout(() => { if (camConnectMsg) camConnectMsg.textContent = ""; }, 3000);
    });
}

// Flip toggle
if (camFlipToggle) {
    camFlipToggle.addEventListener("click", async () => {
        const cur  = camFlipToggle.dataset.active === "true";
        const next = !cur;
        camFlipToggle.dataset.active = next ? "true" : "false";
        camFlipToggle.textContent    = next ? "ON" : "OFF";
        camFlipToggle.style.background = next
            ? "rgba(48,209,88,0.25)" : "rgba(255,255,255,0.08)";
        camFlipToggle.style.color = next ? "#30d158" : "";
        await fetch("/flip");
    });
}

// Resolution change
if (camResSelect) {
    camResSelect.addEventListener("change", async (e) => {
        const [w, h] = e.target.value.split(",");
        try {
            await fetch(`/set_camera_resolution?w=${w}&h=${h}`);
            setTimeout(loadCameraSettings, 500); // refresh UI to reflect actual applied values
        } catch(err) {
            console.error("Failed to change resolution:", err);
        }
    });
}

// FPS change
if (camFpsSelect) {
    camFpsSelect.addEventListener("change", async (e) => {
        const fps = e.target.value;
        try {
            await fetch(`/set_camera_fps?fps=${fps}`);
            setTimeout(loadCameraSettings, 500);
        } catch(err) {
            console.error("Failed to change fps:", err);
        }
    });
}

// ══════════════════════════════════════════
// ESP32 펌웨어 업로드 로직
// ══════════════════════════════════════════
const btnUploadFirmware = document.getElementById("btn-upload-firmware");
const firmwareModal = document.getElementById("firmware-modal");
const closeFirmware = document.getElementById("close-firmware");
const btnStartUpload = document.getElementById("btn-start-upload");
const firmwareProgress = document.getElementById("firmware-progress");

if (btnUploadFirmware) {
    btnUploadFirmware.addEventListener("click", () => {
        closeSettingsModal();
        firmwareModal.style.display = "flex";
        btnStartUpload.style.display = "block";
        firmwareProgress.style.display = "none";
    });
}

if (closeFirmware) {
    closeFirmware.addEventListener("click", () => {
        _closeModalAnimate(firmwareModal);
    });
}

if (btnStartUpload) {
    btnStartUpload.addEventListener("click", async () => {
        btnStartUpload.style.display = "none";
        firmwareProgress.style.display = "flex";
        try {
            showToast("업로드를 시작합니다...", "info");
            const res = await fetch("/upload_firmware", { method: "POST" });
            const data = await res.json();
            if (data.ok) {
                showToast("펌웨어 업로드 완료!", "success");
                setTimeout(() => _closeModalAnimate(firmwareModal), 1500);
            } else {
                showToast("업로드 실패. 백엔드 콘솔을 확인하세요.", "error");
                console.error("Upload failed:\n", data.log);
                btnStartUpload.style.display = "block";
                firmwareProgress.style.display = "none";
            }
        } catch(e) {
            showToast("업로드 중 네트워크 오류가 발생했습니다.", "error");
            btnStartUpload.style.display = "block";
            firmwareProgress.style.display = "none";
        }
    });
}

/* ═══════════════════════════════════════════════════════════════
   펌웨어 버전 불일치 감지 & 경고 모달
   ═══════════════════════════════════════════════════════════════ */
(function initFirmwareMismatchWatcher() {
    const overlay   = document.getElementById("firmware-mismatch-overlay");
    const modal     = document.getElementById("firmware-mismatch-modal");
    const elExp     = document.getElementById("fw-expected");
    const elAct     = document.getElementById("fw-actual");
    const btnUpload = document.getElementById("fw-upload-btn");
    const btnDismiss= document.getElementById("fw-dismiss-btn");

    if (!overlay || !modal) return;

    let dismissed        = false;   // 사용자가 '나중에 하기' 누른 경우
    let uploadInProgress = false;

    /* ── 모달 표시 ── */
    function showMismatchModal(expected, actual) {
        elExp.textContent = expected || "—";
        elAct.textContent = actual   || "(없음)";
        overlay.style.display = "flex";
    }

    /* ── 모달 숨김 ── */
    function hideMismatchModal() {
        overlay.style.display = "none";
        modal.classList.remove("fw-uploading");
    }

    /* ── 5초마다 /firmware_status 폴링 ── */
    async function pollFirmwareStatus() {
        if (uploadInProgress) return;
        try {
            const res  = await fetch("/firmware_status");
            if (!res.ok) return;
            const data = await res.json();

            if (data.mismatch && !dismissed) {
                showMismatchModal(data.expected, data.actual);
            } else if (!data.mismatch) {
                // 버전이 맞으면 모달 숨기고 dismissed 초기화
                hideMismatchModal();
                dismissed = false;
            }
        } catch (_) {
            /* 서버 미응답 시 무시 */
        }
    }

    setInterval(pollFirmwareStatus, 5000);
    // 페이지 로드 후 3초 뒤 첫 번째 체크 (ESP32 부팅 대기)
    setTimeout(pollFirmwareStatus, 3000);

    /* ── '나중에 하기' 버튼 ── */
    btnDismiss.addEventListener("click", () => {
        dismissed = true;
        hideMismatchModal();
        showToast("⚠️ 펌웨어가 맞지 않습니다. 문제가 생길 수 있습니다.", "warn");
    });

    /* ── '펌웨어 업로드' 버튼 → 기존 /upload_firmware API 재활용 ── */
    btnUpload.addEventListener("click", async () => {
        if (uploadInProgress) return;
        uploadInProgress = true;
        modal.classList.add("fw-uploading");

        // 버튼 텍스트를 업로드 중 상태로 변경
        btnUpload.innerHTML = `
            <div class="spinner" style="width:18px;height:18px;border-width:2.5px;"></div>
            업로드 중…
        `;

        showToast("펌웨어 업로드를 시작합니다…", "info");

        try {
            const res  = await fetch("/upload_firmware", { method: "POST" });
            const data = await res.json();

            if (data.ok) {
                showToast("✅ 펌웨어 업로드 완료! ESP32가 재부팅됩니다.", "success");
                dismissed = false;
                // 재부팅 후 VER: 재수신까지 8초 대기 후 재폴링
                setTimeout(() => {
                    uploadInProgress = false;
                    modal.classList.remove("fw-uploading");
                    btnUpload.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                            <polyline points="16 16 12 12 8 16"></polyline>
                            <line x1="12" y1="12" x2="12" y2="21"></line>
                            <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"></path>
                        </svg>
                        펌웨어 업로드
                    `;
                    pollFirmwareStatus();
                }, 8000);
            } else {
                showToast("❌ 업로드 실패. 백엔드 콘솔을 확인하세요.", "error");
                console.error("[firmware] 업로드 실패 로그:\n", data.log);
                uploadInProgress = false;
                modal.classList.remove("fw-uploading");
                btnUpload.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                        <polyline points="16 16 12 12 8 16"></polyline>
                        <line x1="12" y1="12" x2="12" y2="21"></line>
                        <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"></path>
                    </svg>
                    펌웨어 업로드
                `;
            }
        } catch (e) {
            showToast("❌ 업로드 중 네트워크 오류가 발생했습니다.", "error");
            uploadInProgress = false;
            modal.classList.remove("fw-uploading");
            btnUpload.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
                    <polyline points="16 16 12 12 8 16"></polyline>
                    <line x1="12" y1="12" x2="12" y2="21"></line>
                    <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"></path>
                </svg>
                펌웨어 업로드
            `;
        }
    });
})();
