from flask import Flask, render_template, request
import yaml
import os

import model_sync
from config_manager import ConfigManager

app = Flask(__name__)
CONFIG_FILE = "config.yaml"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        new_config = {
            "model_path": request.form["model_path"],
            "rtsp_streams": [s.strip() for s in request.form["rtsp_streams"].replace("\r", "").split("\n") if s.strip()],
            "fps_limit": int(request.form["fps_limit"]),
            "cpu_cores": int(request.form["cpu_cores"]),
            "log_interval_seconds": int(request.form["log_interval_seconds"]),
            "log_file": request.form["log_file"],
            "detection_log_file": request.form["detection_log_file"],
            "mode": request.form.get("mode", "rtsp"),
            "video_path": request.form.get("video_path", ""),
            "conf_threshold": float(request.form.get("conf_threshold", 0.25))
        }
        save_config(new_config)
    
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

@app.route('/sync_models', methods=['POST'])
def sync_models():
    report = model_sync.sync_all(ConfigManager(CONFIG_FILE))
    return jsonify(report)

@app.route('/sync_status')
def sync_status():
    return jsonify(model_sync.get_last_report())

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


