from flask import Flask, render_template, request
import yaml
import os

import model_sync
from config_manager import ConfigManager
try:
    from ums_client import UmsApiClient
except ImportError:
    UmsApiClient = None

app = Flask(__name__)
CONFIG_FILE = "config.yaml"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)

import json
import threading

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        current = load_config() or {}

        # 1. Parse streams: priority to structured JSON payload `streams_json`
        raw_streams_json = request.form.get("streams_json")
        if raw_streams_json:
            try:
                updated_streams = json.loads(raw_streams_json)
                if not isinstance(updated_streams, list):
                    updated_streams = []
            except Exception:
                updated_streams = current.get("streams", [])
        else:
            # Fallback to plain textarea input
            raw_streams_input = request.form.get("streams", "")
            stream_urls = [s.strip() for s in raw_streams_input.replace("\r", "").split("\n") if s.strip()]
            existing_streams_by_url = {}
            if "streams" in current and isinstance(current["streams"], list):
                for s in current["streams"]:
                    if isinstance(s, dict) and "url" in s:
                        existing_streams_by_url[s["url"]] = s

            updated_streams = []
            for u in stream_urls:
                if u in existing_streams_by_url:
                    updated_streams.append(existing_streams_by_url[u])
                else:
                    updated_streams.append({"url": u})

        # 2. Base fields
        new_config = {
            **current,
            "streams": updated_streams,
            "mode": request.form.get("mode", current.get("mode", "rtsp")),
            "model_path": request.form.get("model_path", current.get("model_path", "best.onnx")),
            "video_path": request.form.get("video_path", current.get("video_path", "")),
            "fps_limit": int(request.form.get("fps_limit", current.get("fps_limit", 2))),
            "cpu_cores": int(request.form.get("cpu_cores", current.get("cpu_cores", 4))),
            "conf_threshold": float(request.form.get("conf_threshold", current.get("conf_threshold", 0.25))),
            "log_interval_seconds": int(request.form.get("log_interval_seconds", current.get("log_interval_seconds", 60))),
            "log_file": request.form.get("log_file", current.get("log_file", "performance.log")),
            "detection_log_file": request.form.get("detection_log_file", current.get("detection_log_file", "detections.log"))
        }

        # 3. Model source & ums_model
        model_source = request.form.get("model_source")
        ums_changed = False
        old_ums = current.get("ums_model")

        if model_source == "ums":
            ums_name = request.form.get("ums_model_name", "").strip()
            ums_version = request.form.get("ums_model_version", "latest").strip()
            if ums_name:
                new_ums = {"name": ums_name, "version": ums_version}
                new_config["ums_model"] = new_ums
                if old_ums != new_ums:
                    ums_changed = True
            else:
                new_config.pop("ums_model", None)
                if old_ums is not None:
                    ums_changed = True
        elif model_source == "local":
            new_config.pop("ums_model", None)
            if old_ums is not None:
                ums_changed = True
        else:
            if "ums_model" in current:
                new_config["ums_model"] = current["ums_model"]

        # Check if any per-stream ums_model changed
        if not ums_changed:
            old_stream_ums = [s.get("ums_model") for s in current.get("streams", []) if isinstance(s, dict)]
            new_stream_ums = [s.get("ums_model") for s in updated_streams if isinstance(s, dict)]
            if old_stream_ums != new_stream_ums:
                ums_changed = True

        # 4. UMS settings
        if "ums_base_url" in request.form:
            new_config["ums_base_url"] = request.form["ums_base_url"].strip()
        if "ums_api_key" in request.form:
            new_config["ums_api_key"] = request.form["ums_api_key"].strip()

        # 5. Heartbeat settings
        if "heartbeat_enabled" in request.form:
            enabled = request.form["heartbeat_enabled"].lower() in ("true", "1", "yes", "on")
            hb_curr = current.get("heartbeat", {}) if isinstance(current.get("heartbeat"), dict) else {}
            new_config["heartbeat"] = {
                **hb_curr,
                "enabled": enabled,
                "agent_port": int(request.form.get("heartbeat_agent_port", hb_curr.get("agent_port", 8080))),
                "interval_seconds": int(request.form.get("heartbeat_interval_seconds", hb_curr.get("interval_seconds", 60))),
                "ap_name": request.form.get("heartbeat_ap_name", hb_curr.get("ap_name", "SafetyNano")),
                "version": request.form.get("heartbeat_version", hb_curr.get("version", "0.1.0"))
            }

        # 6. Event settings
        if "event_absence_tolerance" in request.form:
            new_config["event_absence_tolerance"] = int(request.form["event_absence_tolerance"])

        save_config(new_config)

        # 7. Background sync trigger if ums_model changed
        has_any_ums = bool(new_config.get("ums_model")) or any(
            isinstance(s, dict) and bool(s.get("ums_model")) for s in updated_streams
        )
        if ums_changed and has_any_ums:
            threading.Thread(
                target=model_sync.sync_all,
                args=(ConfigManager(CONFIG_FILE),),
                daemon=True
            ).start()
    
    config = load_config()
    return render_template("index.html", config=config)


STREAM_UNITS = []
LATEST_DETECTIONS = {}
MODEL_INFO = {
    "type": "Unknown",
    "path": "",
    "cpu_cores": 4
}

import cv2
import numpy as np
import json


def _create_no_signal_frame():
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    text = "NO SIGNAL"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.2
    thickness = 2
    color = (0, 255, 65)
    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    text_x = (640 - text_size[0]) // 2
    text_y = (360 + text_size[1]) // 2
    cv2.putText(img, text, (text_x, text_y), font, font_scale, color, thickness, cv2.LINE_AA)
    ret, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return buf.tobytes() if ret else b''

NO_SIGNAL_FRAME = _create_no_signal_frame()

def gen_frames():
    import time
    while True:
        frame = LATEST_FRAME if LATEST_FRAME is not None else NO_SIGNAL_FRAME
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        if app.config.get('TESTING'):
            break
        time.sleep(0.03)

def gen_single_stream_frames(stream_id):
    import time
    while True:
        frame_bytes = None
        if 0 <= stream_id < len(STREAM_UNITS):
            unit = STREAM_UNITS[stream_id]
            raw_frame = unit.get("latest_raw_frame")
            if raw_frame is None and "handler" in unit:
                raw_frame = unit["handler"].get_latest_frame()
                
            if raw_frame is not None:
                if isinstance(raw_frame, bytes):
                    frame_bytes = raw_frame
                elif isinstance(raw_frame, np.ndarray):
                    ret, buf = cv2.imencode('.jpg', raw_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    if ret:
                        frame_bytes = buf.tobytes()
        
        if frame_bytes is None:
            frame_bytes = NO_SIGNAL_FRAME

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        if app.config.get('TESTING'):
            break
        time.sleep(0.03)

def gen_detections_feed():
    import time
    while True:
        data_str = json.dumps(LATEST_DETECTIONS)
        yield f"data: {data_str}\n\n"
        if app.config.get('TESTING'):
            break
        time.sleep(0.05)


from flask import Response, jsonify

@app.route('/model_info')
def model_info():
    return jsonify(MODEL_INFO)

@app.route('/zone/<path:stream_url>', methods=['GET'])
def get_zone(stream_url):
    mgr = ConfigManager(CONFIG_FILE)
    zone = mgr.get_zone(stream_url)
    if zone is None:
        return jsonify({"polygon": None, "zone_name": None})
    return jsonify(zone)

@app.route('/zone/<path:stream_url>', methods=['POST'])
def post_zone(stream_url):
    mgr = ConfigManager(CONFIG_FILE)
    data = request.get_json(force=True, silent=True) or {}
    polygon = data.get("polygon", [])
    zone_name = data.get("zone_name")
    mgr.save_zone(stream_url, polygon, zone_name)
    return jsonify({
        "status": "ok",
        "stream_url": stream_url,
        "zone": mgr.get_zone(stream_url)
    })

@app.route('/sync_models', methods=['POST'])
def sync_models():
    report = model_sync.sync_all(ConfigManager(CONFIG_FILE))
    return jsonify(report)

@app.route('/sync_status')
def sync_status():
    return jsonify(model_sync.get_last_report())

@app.route('/api/ums/models', methods=['GET'])
def get_ums_models():
    if UmsApiClient is None:
        return jsonify({"status": "error", "message": "ums_client 套件未安裝"})
    
    mgr = ConfigManager(CONFIG_FILE)
    base_url = os.environ.get("UMS_BASE_URL") or mgr.get("ums_base_url") or "http://tncimweb.cminl.oa/umsapiproxy/fab4ums"
    api_key = os.environ.get("UMS_API_KEY") or mgr.get("ums_api_key")
    
    if not api_key:
        return jsonify({"status": "error", "message": "尚未設定 UMS API Key"})
    
    try:
        client = UmsApiClient(base_url=base_url, api_key=api_key)
        raw_models = client.fetch_my_models()
        
        projects_dict = {}
        for m in raw_models:
            pid = m.project_id
            if pid not in projects_dict:
                projects_dict[pid] = {
                    "project_id": pid,
                    "project_name": m.project_name,
                    "models": []
                }
            
            versions = [
                {
                    "version_id": v.version_id,
                    "version_number": v.version_number,
                    "status": v.status,
                    "accuracy": getattr(v, "accuracy", None),
                    "artifact_size": getattr(v, "artifact_size", None),
                    "comment": getattr(v, "comment", None),
                    "created_at": getattr(v, "created_at", "")
                }
                for v in m.versions
            ]
            
            projects_dict[pid]["models"].append({
                "model_id": m.model_id,
                "model_name": m.model_name,
                "description": getattr(m, "description", ""),
                "architecture_name": getattr(m, "architecture_name", ""),
                "status": m.status,
                "versions": versions
            })
            
        return jsonify({
            "status": "ok",
            "projects": list(projects_dict.values())
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/ums/test_connection', methods=['POST'])
def test_ums_connection():
    if UmsApiClient is None:
        return jsonify({"status": "error", "message": "ums_client 套件未安裝"})
    
    data = request.get_json(force=True, silent=True) or request.form.to_dict() or {}
    base_url = data.get("base_url") or os.environ.get("UMS_BASE_URL") or "http://tncimweb.cminl.oa/umsapiproxy/fab4ums"
    api_key = data.get("api_key") or os.environ.get("UMS_API_KEY")
    
    if not api_key:
        return jsonify({"status": "error", "message": "API Key 不得為空"})
    
    try:
        client = UmsApiClient(base_url=base_url, api_key=api_key, timeout=10)
        models = client.fetch_my_models()
        return jsonify({
            "status": "ok",
            "models_count": len(models),
            "message": f"連線成功，共取得 {len(models)} 個模型"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed/<int:stream_id>')
def video_feed_stream(stream_id):
    return Response(gen_single_stream_frames(stream_id), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detections_feed')
def detections_feed():
    return Response(gen_detections_feed(), mimetype='text/event-stream')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8188)



