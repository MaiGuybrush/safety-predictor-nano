import os
import sys
import time
import json
import threading
import cv2
import numpy as np
from flask import Flask, render_template, jsonify, request, Response
from playwright.sync_api import sync_playwright

OUTPUT_DIR = os.path.abspath("docs/user-manual/src/images")
os.makedirs(OUTPUT_DIR, exist_ok=True)

server_app = Flask(__name__, template_folder=os.path.abspath("templates"))
server_app.config['TESTING'] = True

MOCK_CONFIG = {
    "mode": "rtsp",
    "model_path": "models/person_detector/best.onnx",
    "model_format": "auto",
    "video_path": "",
    "fps_limit": 4,
    "cpu_cores": 4,
    "conf_threshold": 0.25,
    "log_interval_seconds": 60,
    "log_file": "logs/performance.log",
    "detection_log_file": "logs/detections.log",
    "log_backup_count": 3,
    "ums_base_urls": [
        "http://ums-proxy-01.corp.internal:8000",
        "http://ums-proxy-02.corp.internal:8000"
    ],
    "ums_api_key": "ums_sec_99a8b7c6d5e4",
    "heartbeat": {
        "enabled": True,
        "agent_port": 8080,
        "interval_seconds": 60,
        "ap_name": "SafetyNano-Gate",
        "version": "0.1.0"
    },
    "event_absence_tolerance": 3,
    "streams": [
        {
            "url": "rtsp://192.168.1.100:8554/live/cam-01",
            "label": "大門入口",
            "camera_id": "cam-01"
        },
        {
            "url": "rtsp://192.168.1.101:8554/live/cam-02",
            "label": "A區產線",
            "camera_id": "cam-02",
            "model": "models/gear_inspect/gear.onnx",
            "model_format": "onnx"
        },
        {
            "url": "rtsp://192.168.1.102:8554/live/cam-03",
            "label": "倉庫走道",
            "camera_id": "cam-03"
        }
    ],
    "zones": {
        "rtsp://192.168.1.100:8554/live/cam-01": {
            "polygon": [[0.15, 0.25], [0.85, 0.25], [0.85, 0.85], [0.15, 0.85]],
            "zone_name": "禁入警戒區",
            "trigger_mode": "intersect",
            "sensitivity": 0.3
        }
    }
}

def create_mock_frame():
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    img[:] = (12, 14, 16)
    
    for x in range(0, 640, 40):
        cv2.line(img, (x, 0), (x, 360), (20, 26, 22), 1)
    for y in range(0, 360, 40):
        cv2.line(img, (0, y), (640, y), (20, 26, 22), 1)

    pts = np.array([[96, 90], [544, 90], [544, 306], [96, 306]], np.int32)
    pts = pts.reshape((-1, 1, 2))
    cv2.polylines(img, [pts], True, (255, 229, 0), 2)
    cv2.putText(img, "ZONE: RESTRICTED [INTERSECT 30%]", (102, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 229, 0), 1, cv2.LINE_AA)

    cv2.rectangle(img, (220, 130), (360, 290), (0, 255, 65), 2)
    cv2.rectangle(img, (220, 110), (360, 130), (0, 255, 65), -1)
    cv2.putText(img, "person: 0.92 [ALARM]", (225, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

    cv2.putText(img, "CAM-01 [GATE] // LIVE // 25.0 FPS", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 65), 1, cv2.LINE_AA)
    cv2.putText(img, "2026-08-20 08:25:00 CST", (430, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 143, 17), 1, cv2.LINE_AA)

    ret, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    return buf.tobytes()

MOCK_FRAME_BYTES = create_mock_frame()

@server_app.route("/")
def index():
    return render_template("index.html", config=MOCK_CONFIG)

@server_app.route("/video_feed")
@server_app.route("/video_feed/<int:stream_id>")
def video_feed(stream_id=0):
    def gen():
        while True:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + MOCK_FRAME_BYTES + b'\r\n')
            time.sleep(0.05)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@server_app.route("/model_info")
def model_info():
    return jsonify({
        "type": "ONNX",
        "path": "models/person_detector/best.onnx",
        "cpu_cores": 4,
        "streams": [
            {"url": "rtsp://192.168.1.100:8554/live/cam-01", "model": "best.onnx", "type": "ONNX"},
            {"url": "rtsp://192.168.1.101:8554/live/cam-02", "model": "gear.onnx", "type": "ONNX"},
            {"url": "rtsp://192.168.1.102:8554/live/cam-03", "model": "best.onnx", "type": "ONNX"}
        ]
    })

@server_app.route("/sync_status")
def sync_status():
    return jsonify({
        "status": "ok",
        "synced_count": 1,
        "failed_count": 0,
        "message": "OK:1 FAIL:0"
    })

@server_app.route("/sync_models", methods=["POST"])
def sync_models():
    return jsonify({
        "status": "ok",
        "synced_count": 1,
        "failed_count": 0,
        "message": "OK:1 FAIL:0"
    })

@server_app.route("/zone/<path:stream_url>", methods=["GET", "POST"])
def zone_api(stream_url):
    if request.method == "POST":
        return jsonify({"status": "ok", "stream_url": stream_url})
    z = MOCK_CONFIG["zones"].get(stream_url)
    if z:
        return jsonify(z)
    return jsonify({
        "polygon": [[0.15, 0.25], [0.85, 0.25], [0.85, 0.85], [0.15, 0.85]],
        "zone_name": "禁入警戒區",
        "trigger_mode": "intersect",
        "sensitivity": 0.3
    })

@server_app.route("/api/ums/models")
def api_ums_models():
    return jsonify({
        "status": "ok",
        "projects": [
            {
                "project_id": "proj-safety-01",
                "project_name": "廠區人員工安防護",
                "models": [
                    {
                        "model_id": "m-person-01",
                        "model_name": "YOLOv8-Person-Detector",
                        "versions": [
                            {"version_id": "v-1", "version_number": "latest", "status": "active"},
                            {"version_id": "v-2", "version_number": "v1.2.0", "status": "active"},
                            {"version_id": "v-3", "version_number": "v1.1.0", "status": "deprecated"}
                        ]
                    },
                    {
                        "model_id": "m-helmet-01",
                        "model_name": "YOLOv8-Safety-Helmet",
                        "versions": [
                            {"version_id": "v-h-1", "version_number": "latest", "status": "active"},
                            {"version_id": "v-h-2", "version_number": "v2.0.1", "status": "active"}
                        ]
                    }
                ]
            },
            {
                "project_id": "proj-gear-02",
                "project_name": "產線機具工件瑕疵檢測",
                "models": [
                    {
                        "model_id": "m-gear-01",
                        "model_name": "YOLOv8-Gear-Defect",
                        "versions": [
                            {"version_id": "v-g-1", "version_number": "latest", "status": "active"}
                        ]
                    }
                ]
            }
        ]
    })

@server_app.route("/api/ums/test_connection", methods=["POST"])
def api_ums_test_connection():
    return jsonify({
        "status": "ok",
        "endpoints": [
            {
                "url": "http://ums-proxy-01.corp.internal:8000",
                "status": "ok",
                "models_count": 3,
                "message": "連線成功，共取得 3 個模型"
            },
            {
                "url": "http://ums-proxy-02.corp.internal:8000",
                "status": "ok",
                "models_count": 3,
                "message": "連線成功，共取得 3 個模型"
            }
        ]
    })

@server_app.route("/detections_feed")
def detections_feed():
    def gen():
        while True:
            data = {
                "cam-01": [
                    {
                        "class": "person",
                        "confidence": 0.92,
                        "box": [0.35, 0.36, 0.56, 0.8],
                        "in_zone": True,
                        "zone_alarm": True
                    }
                ]
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.1)
    return Response(gen(), mimetype="text/event-stream")


def start_server():
    server_app.run(host="127.0.0.1", port=8199, debug=False, use_reloader=False)


ANNOTATION_JS = """
(specs) => {
    document.querySelectorAll('[data-manual-annotation]').forEach(el => el.remove());

    function getContrastTextColor(bgColor, userTextColor) {
        if (userTextColor) return userTextColor;
        try {
            const temp = document.createElement('div');
            temp.style.color = bgColor || 'red';
            document.body.appendChild(temp);
            const computedColor = window.getComputedStyle(temp).color;
            document.body.removeChild(temp);

            const match = computedColor.match(/\\d+/g);
            if (match && match.length >= 3) {
                const r = parseInt(match[0], 10);
                const g = parseInt(match[1], 10);
                const b = parseInt(match[2], 10);
                const yiq = (r * 299 + g * 587 + b * 114) / 1000;
                return yiq >= 140 ? '#111827' : '#ffffff';
            }
        } catch (e) {
            console.warn('Failed to calculate contrast color', e);
        }
        return '#ffffff';
    }

    specs.forEach(spec => {
        const el = document.querySelector(spec.selector);
        if (!el) { console.warn('Annotation selector not found:', spec.selector); return; }
        const rect = el.getBoundingClientRect();
        const color = spec.color || '#ef4444';
        const textColor = getContrastTextColor(color, spec.textColor);
        const overlay = document.createElement('div');
        overlay.setAttribute('data-manual-annotation', 'true');
        overlay.style.cssText = [
            'position:fixed',
            `left:${rect.left}px`,
            `top:${rect.top}px`,
            `width:${rect.width}px`,
            `height:${rect.height}px`,
            `border:2.5px solid ${color}`,
            'background:rgba(255,255,255,0.02)',
            'z-index:99999',
            'pointer-events:none',
            'box-sizing:border-box',
        ].join(';');

        if (spec.label) {
            const badge = document.createElement('span');
            badge.textContent = spec.label;

            const topSpace = rect.top;
            const bottomSpace = window.innerHeight - rect.bottom;
            const elementHeight = rect.height;

            let positionStyles = '';
            if (spec.position === 'inner-top') {
                positionStyles = 'top:4px; left:4px;';
            } else if (spec.position === 'bottom-outer') {
                positionStyles = 'top:100%; left:-1px; margin-top:4px;';
            } else if (topSpace >= 36) {
                positionStyles = 'bottom:100%; left:-1px; margin-bottom:4px;';
            } else if (elementHeight < 45 && bottomSpace >= 36) {
                positionStyles = 'top:100%; left:-1px; margin-top:4px;';
            } else {
                positionStyles = 'top:4px; left:4px;';
            }

            if (rect.left < 4) {
                positionStyles += ' left:2px;';
            } else if (rect.right > window.innerWidth - 20) {
                positionStyles += ' right:2px; left:auto;';
            }

            badge.style.cssText = [
                'position:absolute',
                positionStyles,
                `background:${color}`,
                `color:${textColor}`,
                'font:bold 13px/1.3 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                'padding:3px 8px',
                'border-radius:4px',
                'box-shadow:0 2px 6px rgba(0,0,0,0.4)',
                'white-space:nowrap',
                'letter-spacing:0.3px',
            ].join(';');
            overlay.appendChild(badge);
        }
        document.body.appendChild(overlay);
    });
}
"""

def take_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # 1. ui-main-layout.png
        print("[1/12] Generating ui-main-layout.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(800)
        page.evaluate("""() => {
            document.getElementById('model-type').innerText = 'ONNX';
            document.getElementById('model-path').innerText = 'models/person_detector/best.onnx';
            document.getElementById('model-cores').innerText = '4';
            document.getElementById('sync-status').innerText = 'OK:1 FAIL:0';
            document.getElementById('sync-status').style.color = 'var(--text)';
        }""")
        page.evaluate(ANNOTATION_JS, [
            {"selector": ".top-container", "label": "① 頂部系統狀態列", "position": "inner-top"},
            {"selector": "#config-panel", "label": "② 系統設定參數面板", "position": "inner-top"},
            {"selector": ".right-workspace > div:first-child", "label": "③ 即時預覽視窗", "position": "inner-top"},
            {"selector": "#stream-detail-inspector", "label": "④ 串流詳細屬性檢視器", "position": "inner-top"}
        ])
        page.screenshot(path=os.path.join(OUTPUT_DIR, "ui-main-layout.png"))

        # 2. ui-monitor-mode.png
        print("[2/12] Generating ui-monitor-mode.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
            document.getElementById('sys-core').classList.add('hide-config');
            document.getElementById('model-type').innerText = 'ONNX';
            document.getElementById('model-path').innerText = 'models/person_detector/best.onnx';
            document.getElementById('model-cores').innerText = '4';
            document.getElementById('sync-status').innerText = 'OK:1 FAIL:0';
        }""")
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "ui-monitor-mode.png"))

        # 3. stream-master-list.png
        print("[3/12] Generating stream-master-list.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
            const panel = document.getElementById('config-panel');
            if (panel) panel.scrollTop = 120;
        }""")
        page.wait_for_timeout(200)
        page.evaluate(ANNOTATION_JS, [
            {"selector": "#mode-select", "label": "① 運作模式 (MODE)"},
            {"selector": "#master-stream-list", "label": "② 攝影機串流清單"},
            {"selector": "#streams-master-section button", "label": "③ 新增串流按鈕"}
        ])
        page.screenshot(path=os.path.join(OUTPUT_DIR, "stream-master-list.png"))

        # 4. stream-detail-inspector.png
        print("[4/12] Generating stream-detail-inspector.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(500)
        page.evaluate(ANNOTATION_JS, [
            {"selector": "#detail-input-url", "label": "① 串流 URL"},
            {"selector": "#detail-input-label", "label": "② 畫面標籤 (LABEL)"},
            {"selector": "#detail-input-camid", "label": "③ 鏡頭識別碼 (CAMERA_ID)"}
        ])
        page.screenshot(path=os.path.join(OUTPUT_DIR, "stream-detail-inspector.png"))

        # 5. stream-camid-warning.png
        print("[5/12] Generating stream-camid-warning.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
            const inputCamid = document.getElementById('detail-input-camid');
            inputCamid.value = 'cam-99';
            const warnBox = document.getElementById('detail-camid-warning');
            warnBox.style.display = 'flex';
            document.getElementById('detail-expected-camid').innerText = 'cam-01';
        }""")
        page.evaluate(ANNOTATION_JS, [
            {"selector": "#detail-camid-warning", "label": "⚠ 防呆警示與還原按鈕", "color": "#ffaa00"}
        ])
        page.screenshot(path=os.path.join(OUTPUT_DIR, "stream-camid-warning.png"))

        # 6. model-source-global.png
        print("[6/12] Generating model-source-global.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(500)
        page.evaluate(ANNOTATION_JS, [
            {"selector": ".radio-switch", "label": "① 模型來源切換 (MODEL_SOURCE)"},
            {"selector": "#local-model-box", "label": "② 本地模型目錄路徑 (MODEL_PATH)"},
            {"selector": "#global-model-format-select", "label": "③ 模型格式偏好類別 (MODEL_FORMAT)"}
        ])
        page.screenshot(path=os.path.join(OUTPUT_DIR, "model-source-global.png"))

        # 7. model-stream-override.png
        print("[7/12] Generating model-stream-override.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
            if (typeof selectStreamItem === 'function') {
                selectStreamItem(1);
            }
            document.getElementById('detail-override-toggle').checked = true;
            document.getElementById('detail-override-box').style.display = 'block';
            document.getElementById('detail-input-model').value = 'models/gear_inspect/gear.onnx';
            document.getElementById('detail-resolved-model-path').innerText = 'models/gear_inspect/gear.onnx';
            document.getElementById('detail-resolved-model-badge').innerText = 'ONNX';
        }""")
        page.evaluate(ANNOTATION_JS, [
            {"selector": "#detail-override-toggle", "label": "① 勾選獨立模型 (OVERRIDE_MODEL)"},
            {"selector": "#detail-override-box", "label": "② 獨立模型配置區"},
            {"selector": "#detail-resolved-model-box", "label": "③ 實際生效模型 (RESOLVED MODEL)"}
        ])
        page.screenshot(path=os.path.join(OUTPUT_DIR, "model-stream-override.png"))

        # 8. model-sync-status.png
        print("[8/12] Generating model-sync-status.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
            document.getElementById('model-type').innerText = 'ONNX';
            document.getElementById('model-path').innerText = 'models/person_detector/best.onnx';
            document.getElementById('model-cores').innerText = '4';
            document.getElementById('sync-status').innerText = 'OK:1 FAIL:0';
            document.getElementById('sync-status').style.color = 'var(--text)';
        }""")
        page.evaluate(ANNOTATION_JS, [
            {"selector": "#model-status-bar", "label": "頂部系統狀態列與模型同步狀態 (SYNC_MODELS)", "position": "bottom-outer"}
        ])
        page.screenshot(path=os.path.join(OUTPUT_DIR, "model-sync-status.png"))

        # 9. fullscreen-live-monitor.png
        print("[9/12] Generating fullscreen-live-monitor.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
            openFullscreen(0);
            document.getElementById('zone-status-badge').innerText = '警戒區：ACTIVE: 禁入警戒區 [相交 30%]';
            document.getElementById('zone-status-badge').style.color = 'var(--cyan)';
        }""")
        page.wait_for_timeout(400)
        page.evaluate(ANNOTATION_JS, [
            {"selector": "#modal-title", "label": "① 全螢幕串流標題"},
            {"selector": "#zone-status-badge", "label": "② ROI 區域生效狀態"},
            {"selector": "#btn-edit-zone", "label": "③ 進入區域編輯模式"},
            {"selector": ".modal-close-btn", "label": "④ 關閉全螢幕 (EXIT)"}
        ])
        page.screenshot(path=os.path.join(OUTPUT_DIR, "fullscreen-live-monitor.png"))

        # 10. roi-editor-drawing.png
        print("[10/12] Generating roi-editor-drawing.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
            openFullscreen(0);
            enterZoneEditMode();
            document.getElementById('zone-name-input').value = 'RESTRICTED_ZONE_1';
            document.getElementById('zone-trigger-mode-select').value = 'intersect';
            updateTriggerModeUI();
            document.getElementById('zone-sensitivity-range').value = 30;
            document.getElementById('zone-sensitivity-val').innerText = '30%';
            
            const canvas = document.getElementById('fullscreen-canvas');
            if (canvas) {
                const ctx = canvas.getContext('2d');
                canvas.width = canvas.parentElement.clientWidth;
                canvas.height = canvas.parentElement.clientHeight;
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                ctx.strokeStyle = '#00e5ff';
                ctx.lineWidth = 2.5;
                ctx.fillStyle = 'rgba(0, 229, 255, 0.15)';
                ctx.beginPath();
                const p1 = {x: canvas.width * 0.18, y: canvas.height * 0.22};
                const p2 = {x: canvas.width * 0.82, y: canvas.height * 0.22};
                const p3 = {x: canvas.width * 0.82, y: canvas.height * 0.82};
                const p4 = {x: canvas.width * 0.18, y: canvas.height * 0.82};
                ctx.moveTo(p1.x, p1.y);
                ctx.lineTo(p2.x, p2.y);
                ctx.lineTo(p3.x, p3.y);
                ctx.lineTo(p4.x, p4.y);
                ctx.closePath();
                ctx.fill();
                ctx.stroke();
                
                [p1, p2, p3, p4].forEach((p, idx) => {
                    ctx.fillStyle = '#ffaa00';
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, 6, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.strokeStyle = '#fff';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                });
            }
        }""")
        page.wait_for_timeout(400)
        page.evaluate(ANNOTATION_JS, [
            {"selector": "#zone-edit-controls", "label": "ROI 警戒區繪製工具列 (Trigger Mode & Sensitivity)", "position": "bottom-outer"}
        ])
        page.screenshot(path=os.path.join(OUTPUT_DIR, "roi-editor-drawing.png"))

        # 11. settings-performance.png
        print("[11/12] Generating settings-performance.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(500)
        page.evaluate(ANNOTATION_JS, [
            {"selector": "input[name='fps_limit']", "label": "① FPS 限制"},
            {"selector": "input[name='cpu_cores']", "label": "② CPU 核心數"},
            {"selector": "input[name='conf_threshold']", "label": "③ 信心度門檻 (CONF_THRESHOLD)"}
        ])
        page.screenshot(path=os.path.join(OUTPUT_DIR, "settings-performance.png"))

        # 12. settings-advanced-ums.png
        print("[12/12] Generating settings-advanced-ums.png...")
        page.goto("http://127.0.0.1:8199/")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
            const sec = document.getElementById('advanced-section');
            if (sec && !sec.classList.contains('open')) {
                toggleAdvancedSection();
            }
            const panel = document.getElementById('config-panel');
            if (panel) panel.scrollTop = 380;
        }""")
        page.wait_for_timeout(400)
        page.evaluate(ANNOTATION_JS, [
            {"selector": "#ums-endpoints-container", "label": "① UMS 服務端點與備援清單 (UMS_BASE_URLS)"},
            {"selector": "#ums_api_key", "label": "② UMS API KEY"},
            {"selector": "input[name='heartbeat_enabled']", "label": "③ HEARTBEAT 服務"},
            {"selector": "input[name='event_absence_tolerance']", "label": "④ 消失容忍幀數"}
        ])
        page.screenshot(path=os.path.join(OUTPUT_DIR, "settings-advanced-ums.png"))

        browser.close()
        print("All 12 screenshots successfully generated!")

if __name__ == "__main__":
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(1.5)
    take_screenshots()
    sys.exit(0)
