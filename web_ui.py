from flask import Flask, render_template, request, send_from_directory, abort, jsonify
import yaml
import os
import sys

def get_resource_path(relative_path):
    """取得資源檔案路徑，相容 PyInstaller 凍結環境 (_MEIPASS) 與開發環境"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)

MANUAL_DIR = get_resource_path(os.path.join("docs", "user-manual", "book"))

import model_sync
import ums_config
from config_manager import ConfigManager, DEFAULT_UMS_BASE_URLS
from stats_logger import configure_werkzeug_logger
import logging

configure_werkzeug_logger(logging.WARNING)

try:
    from ums_client import UmsApiClient
except ImportError:
    UmsApiClient = None

try:
    from failover_ums_client import FailoverUmsClient
except ImportError:
    FailoverUmsClient = None
from state_poller import GLOBAL_STATE_POLLER

app = Flask(__name__)
CONFIG_FILE = "config.yaml"

CURRENT_EXTERNAL_STATES = {}
LATEST_COMPLIANCE_STATUS = {}

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
        is_ajax = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in request.headers.get("Accept", "")
            or request.is_json
        )
        try:
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

            # Parse event_retention_days defensively
            raw_retention_days = request.form.get("event_retention_days")
            try:
                event_retention_days = int(raw_retention_days) if raw_retention_days is not None and str(raw_retention_days).strip() else int(current.get("event_retention_days", 30))
                if event_retention_days < 1:
                    event_retention_days = 30
            except (ValueError, TypeError):
                event_retention_days = int(current.get("event_retention_days", 30))

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
                "system_log_file": request.form.get("system_log_file", current.get("system_log_file", "logs/system.log")),
                "log_file": request.form.get("log_file", current.get("log_file", "logs/performance.log")),
                "detection_log_file": request.form.get("detection_log_file", current.get("detection_log_file", "logs/detections.log")),
                "log_level": request.form.get("log_level", current.get("log_level", "INFO")),
                "log_backup_count": log_backup_count,
                "event_retention_days": event_retention_days
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
            if "ums_fab" in request.form:
                new_fab = request.form["ums_fab"].strip().lower()
                if new_fab:
                    new_config["ums_fab"] = new_fab
            elif "ums_fab" not in new_config and "ums_fab" in current:
                new_config["ums_fab"] = current["ums_fab"]

            # 確保完全排除舊有端點清單欄位
            new_config.pop("ums_base_urls", None)
            new_config.pop("ums_base_url", None)

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

            if is_ajax:
                return jsonify({
                    "status": "ok",
                    "message": "設定已成功儲存並生效"
                })
        except Exception as e:
            if is_ajax:
                return jsonify({
                    "status": "error",
                    "message": f"儲存失敗: {e}"
                }), 500
            raise
    
    config = load_config() or {}
    try:
        mgr = ConfigManager(CONFIG_FILE)
        ums_api_cfg = mgr.get_ums_api_config()
        current_fab = mgr.get_ums_fab()
    except Exception:
        ums_api_cfg = ums_config.load_ums_api_config()
        current_fab = str(config.get("ums_fab") or "oa").strip().lower()

    fabs_map = ums_config.get_all_fabs_and_endpoints(ums_api_cfg)
    available_fabs = [
        {
            "fab": f,
            "display_name": ums_config.format_fab_display_name(f),
            "endpoints": eps
        }
        for f, eps in fabs_map.items()
    ]

    return render_template(
        "index.html",
        config=config,
        available_fabs=available_fabs,
        ums_fabs_map=fabs_map,
        current_fab=current_fab
    )


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

@app.route('/api/external_state', methods=['POST'])
def post_external_state():
    """接收外部系統 (MES/PLC/Webhook) 主動推送之設備狀態。"""
    data = request.get_json(force=True, silent=True) or {}
    source = data.get("source")
    status = data.get("status")
    if not source or status is None:
        return jsonify({"status": "error", "message": "Missing 'source' or 'status' field"}), 400

    ttl_seconds = data.get("ttl_seconds")
    if ttl_seconds is not None:
        try:
            ttl_seconds = float(ttl_seconds)
        except (ValueError, TypeError):
            ttl_seconds = None

    GLOBAL_STATE_POLLER.update_state(str(source), status, ttl_seconds=ttl_seconds)
    CURRENT_EXTERNAL_STATES[str(source)] = status

    return jsonify({
        "status": "ok",
        "source": str(source),
        "value": status,
        "ttl_seconds": ttl_seconds,
    })

@app.route('/api/compliance_status', methods=['GET'])
def get_compliance_status():
    """查詢當前所有串流之設備外部狀態與工安合規總覽。"""
    return jsonify({
        "external_states": GLOBAL_STATE_POLLER.get_current_states(),
        "compliance": LATEST_COMPLIANCE_STATUS,
    })

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """安全取得日誌內容，supports ?file=system|performance|detections&lines=200

    - file 參數僅允許白名單中的三種日誌類型
    - lines 參數為整數，預設 200，上限 1000
    - 檔案不存在時回傳 200 OK 且 content 為空字串
    - 非法 file 參數回傳 400
    """
    import os

    # 嚴格白名單：僅允許以下三種日誌類型
    LOG_WHITELIST = {
        "system": None,        # 將從 config 動態取得
        "performance": None,
        "detections": None,
    }

    file_type = request.args.get('file', 'system').strip().lower()

    # 路徑穿越防護：不允許任何路徑分隔符
    if '/' in file_type or '\\' in file_type or '..' in file_type:
        return jsonify({'status': 'error', 'message': 'Invalid file parameter'}), 400

    if file_type not in LOG_WHITELIST:
        return jsonify({'status': 'error', 'message': f'Unknown log type: {file_type}. Valid: system, performance, detections'}), 400

    # 取得 lines 參數
    try:
        lines = int(request.args.get('lines', 200))
    except (ValueError, TypeError):
        lines = 200
    lines = max(1, min(lines, 1000))  # 上限 1000 行

    # 從 config 取得實際檔案路徑
    try:
        cfg = load_config()
    except Exception:
        cfg = {}

    file_path_map = {
        'system': cfg.get('system_log_file', 'logs/system.log'),
        'performance': cfg.get('log_file', 'logs/performance.log'),
        'detections': cfg.get('detection_log_file', 'logs/detections.log'),
    }

    log_path = file_path_map[file_type]

    # 檔案不存在時，優雅回傳 200 且 content 為空字串
    if not os.path.exists(log_path):
        return jsonify({
            'status': 'ok',
            'file_type': file_type,
            'file_path': log_path,
            'lines': 0,
            'content': ''
        })

    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        content = ''.join(tail)
        return jsonify({
            'status': 'ok',
            'file_type': file_type,
            'file_path': log_path,
            'lines': len(tail),
            'content': content
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

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

@app.route('/api/ums/fabs', methods=['GET'])
def get_ums_fabs():
    """取得所有可用廠區清單與對應主備端點"""
    try:
        mgr = ConfigManager(CONFIG_FILE)
        current_fab = mgr.get_ums_fab()
        ums_api_cfg = mgr.get_ums_api_config()
    except Exception:
        current_fab = "oa"
        ums_api_cfg = ums_config.load_ums_api_config()

    fabs_map = ums_config.get_all_fabs_and_endpoints(ums_api_cfg)
    fabs_list = [
        {
            "fab": f,
            "display_name": ums_config.format_fab_display_name(f),
            "endpoints": eps
        }
        for f, eps in fabs_map.items()
    ]
    return jsonify({
        "status": "ok",
        "current_fab": current_fab,
        "fabs": fabs_list,
        "endpoints_map": fabs_map
    })

@app.route('/api/ums/test_connection', methods=['POST'])
def test_ums_connection():
    if FailoverUmsClient is None and UmsApiClient is None:
        return jsonify({"status": "error", "message": "ums_client 套件未安裝"})
    
    data = request.get_json(force=True, silent=True) or request.form.to_dict() or {}
    api_key = data.get("api_key") or os.environ.get("UMS_API_KEY")
    
    if not api_key:
        return jsonify({"status": "error", "message": "API Key 不得為空"})
    
    candidate_urls = []
    if "fab" in data and data["fab"]:
        try:
            mgr = ConfigManager(CONFIG_FILE)
            ums_api_cfg = mgr.get_ums_api_config()
        except Exception:
            ums_api_cfg = ums_config.load_ums_api_config()
        candidate_urls = ums_config.get_ums_endpoints_for_fab(data["fab"], ums_api_config=ums_api_cfg)
    elif "base_urls" in data:
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

@app.route('/manual')
@app.route('/manual/')
@app.route('/manual/<path:filename>')
def serve_manual(filename="index.html"):
    """提供 mdBook 靜態使用手冊"""
    if not os.path.exists(MANUAL_DIR):
        abort(404, description="使用手冊尚未建置或不存在，請先執行 mdbook build docs/user-manual")
    return send_from_directory(MANUAL_DIR, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8188)



