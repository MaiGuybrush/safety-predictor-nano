from flask import Flask, render_template, request
import yaml
import os

import model_sync
from config_manager import ConfigManager, DEFAULT_UMS_BASE_URLS
try:
    from ums_client import UmsApiClient
except ImportError:
    UmsApiClient = None

try:
    from failover_ums_client import FailoverUmsClient
except ImportError:
    FailoverUmsClient = None

app = Flask(__name__)
CONFIG_FILE = "config.yaml"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_config(config):
    temp_file = CONFIG_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    os.replace(temp_file, CONFIG_FILE)

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

        # Parse log_backup_count defensively
        raw_backup_count = request.form.get("log_backup_count")
        try:
            log_backup_count = int(raw_backup_count) if raw_backup_count is not None and str(raw_backup_count).strip() else int(current.get("log_backup_count", 3))
            if log_backup_count < 1:
                log_backup_count = 3
        except (ValueError, TypeError):
            log_backup_count = int(current.get("log_backup_count", 3))

        # 2. Base fields
        new_config = {
            **current,
            "streams": updated_streams,
            "mode": request.form.get("mode", current.get("mode", "rtsp")),
            "model_path": request.form.get("model_path", current.get("model_path", "best.onnx")),
            "model_format": request.form.get("model_format", current.get("model_format", "auto")),
            "video_path": request.form.get("video_path", current.get("video_path", "")),
            "fps_limit": int(request.form.get("fps_limit", current.get("fps_limit", 2))),
            "cpu_cores": int(request.form.get("cpu_cores", current.get("cpu_cores", 4))),
            "conf_threshold": float(request.form.get("conf_threshold", current.get("conf_threshold", 0.25))),
            "log_interval_seconds": int(request.form.get("log_interval_seconds", current.get("log_interval_seconds", 60))),
            "log_file": request.form.get("log_file", current.get("log_file", "logs/performance.log")),
            "detection_log_file": request.form.get("detection_log_file", current.get("detection_log_file", "logs/detections.log")),
            "log_backup_count": log_backup_count
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
        if "ums_base_urls" in request.form or "ums_base_urls[]" in request.form:
            raw_urls = request.form.getlist("ums_base_urls") or request.form.getlist("ums_base_urls[]")
            parsed_urls = []
            for item in raw_urls:
                if not item:
                    continue
                if item.startswith("[") and item.endswith("]"):
                    try:
                        sub_list = json.loads(item)
                        if isinstance(sub_list, list):
                            for u in sub_list:
                                if str(u).strip():
                                    parsed_urls.append(str(u).strip())
                            continue
                    except Exception:
                        pass
                for u in item.split(","):
                    if u.strip():
                        parsed_urls.append(u.strip())
            if parsed_urls:
                new_config["ums_base_urls"] = parsed_urls
                new_config.pop("ums_base_url", None)
        elif "ums_base_url" in request.form:
            u_single = request.form["ums_base_url"].strip()
            if u_single:
                new_config["ums_base_url"] = u_single
                new_config["ums_base_urls"] = [u_single]

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


LATEST_FRAME = None
_clients_lock = threading.Lock()
ACTIVE_VIDEO_CLIENTS = 0

def register_video_client():
    global ACTIVE_VIDEO_CLIENTS
    with _clients_lock:
        ACTIVE_VIDEO_CLIENTS += 1

def unregister_video_client():
    global ACTIVE_VIDEO_CLIENTS
    with _clients_lock:
        if ACTIVE_VIDEO_CLIENTS > 0:
            ACTIVE_VIDEO_CLIENTS -= 1

def is_streaming_active():
    with _clients_lock:
        return ACTIVE_VIDEO_CLIENTS > 0

STREAM_UNITS = []
LATEST_DETECTIONS = {}
MODEL_INFO = {
    "type": "Unknown",
    "path": "",
    "cpu_cores": 4,
    "streams": []
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
    register_video_client()
    try:
        while True:
            frame = LATEST_FRAME if LATEST_FRAME is not None else NO_SIGNAL_FRAME
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            if app.config.get('TESTING'):
                break
            time.sleep(0.03)
    finally:
        unregister_video_client()

def gen_single_stream_frames(stream_id):
    import time
    register_video_client()
    try:
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
    finally:
        unregister_video_client()

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
        return jsonify({
            "polygon": None,
            "zone_name": None,
            "trigger_mode": "center",
            "sensitivity": 0.0
        })
    res = dict(zone)
    if "trigger_mode" not in res:
        res["trigger_mode"] = "center"
    if "sensitivity" not in res:
        res["sensitivity"] = 0.0
    return jsonify(res)

@app.route('/zone/<path:stream_url>', methods=['POST'])
def post_zone(stream_url):
    mgr = ConfigManager(CONFIG_FILE)
    data = request.get_json(force=True, silent=True) or {}
    polygon = data.get("polygon", [])
    zone_name = data.get("zone_name")
    trigger_mode = data.get("trigger_mode", "center")
    sensitivity = data.get("sensitivity", 0.0)
    mgr.save_zone(stream_url, polygon, zone_name, trigger_mode=trigger_mode, sensitivity=sensitivity)
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
    if FailoverUmsClient is None and UmsApiClient is None:
        return jsonify({"status": "error", "message": "ums_client 套件未安裝"})
    
    try:
        mgr = ConfigManager(CONFIG_FILE)
        base_urls = mgr.get_ums_base_urls()
        cfg_key = mgr.get("ums_api_key")
    except Exception:
        base_urls = list(DEFAULT_UMS_BASE_URLS)
        cfg_key = None

    api_key = os.environ.get("UMS_API_KEY") or cfg_key
    
    if not api_key:
        return jsonify({"status": "error", "message": "尚未設定 UMS API Key"})
    
    try:
        if FailoverUmsClient is not None:
            client = FailoverUmsClient(base_urls=base_urls, api_key=api_key)
        else:
            client = UmsApiClient(base_url=base_urls[0], api_key=api_key)
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
    if FailoverUmsClient is None and UmsApiClient is None:
        return jsonify({"status": "error", "message": "ums_client 套件未安裝"})
    
    data = request.get_json(force=True, silent=True) or request.form.to_dict() or {}
    api_key = data.get("api_key") or os.environ.get("UMS_API_KEY")
    
    if not api_key:
        return jsonify({"status": "error", "message": "API Key 不得為空"})
    
    candidate_urls = []
    if "base_urls" in data:
        raw_val = data["base_urls"]
        if isinstance(raw_val, list):
            candidate_urls = [str(u).strip() for u in raw_val if str(u).strip()]
        elif isinstance(raw_val, str):
            candidate_urls = [u.strip() for u in raw_val.split(",") if u.strip()]
    elif "base_url" in data and data["base_url"]:
        candidate_urls = [data["base_url"].strip()]
    
    if not candidate_urls:
        try:
            mgr = ConfigManager(CONFIG_FILE)
            candidate_urls = mgr.get_ums_base_urls()
        except Exception:
            candidate_urls = list(DEFAULT_UMS_BASE_URLS)

    if FailoverUmsClient is not None:
        client = FailoverUmsClient(base_urls=candidate_urls, api_key=api_key, timeout=10)
        endpoints_results = client.test_endpoints()
    else:
        endpoints_results = []
        for u in candidate_urls:
            try:
                c = UmsApiClient(base_url=u, api_key=api_key, timeout=10)
                ms = c.fetch_my_models()
                endpoints_results.append({"url": u, "status": "ok", "models_count": len(ms), "message": f"連線成功，共取得 {len(ms)} 個模型"})
            except Exception as e:
                endpoints_results.append({"url": u, "status": "error", "message": str(e), "error": str(e)})

    success_count = sum(1 for ep in endpoints_results if ep.get("status") == "ok")
    total_count = len(endpoints_results)

    if success_count > 0:
        first_success = next(ep for ep in endpoints_results if ep.get("status") == "ok")
        models_cnt = first_success.get("models_count", 0)
        return jsonify({
            "status": "ok",
            "models_count": models_cnt,
            "message": f"連線測試完成：{success_count}/{total_count} 個端點連線成功",
            "endpoints": endpoints_results
        })
    else:
        err_msg = endpoints_results[0].get("message") if endpoints_results else "連線失敗"
        return jsonify({
            "status": "error",
            "message": f"所有端點皆連線失敗: {err_msg}",
            "endpoints": endpoints_results
        })

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



