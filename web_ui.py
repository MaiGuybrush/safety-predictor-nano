from flask import Flask, render_template, request
import yaml
import os

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

LATEST_FRAME = None
MODEL_INFO = {
    "type": "Unknown",
    "path": "",
    "cpu_cores": 4
}

import cv2
import numpy as np


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
        time.sleep(0.03)


from flask import Response, jsonify

@app.route('/model_info')
def model_info():
    return jsonify(MODEL_INFO)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8188)

