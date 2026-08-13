import os
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

import cv2
import numpy as np
import time
import threading

import web_ui
from web_ui import app
from config_manager import ConfigManager
from stream_handler import StreamHandler
from video_handler import VideoHandler
from inference_engine import InferenceEngine
from stats_logger import StatsLogger
from grid_composer import annotate_frame, compose_grid

def run_web_ui():
    app.run(host="0.0.0.0", port=8188, use_reloader=False)

def _inference_worker(context):
    """
    背景推論執行緒，Round-Robin 對各 RTSP 串流執行 YOLO 推論，
    寫入 web_ui.LATEST_DETECTIONS。
    """
    rr_index = 0
    while context.get("running", True):
        mode = context.get("mode", "rtsp")
        stream_units = context.get("stream_units", [])
        config = context.get("config", {})
        logger = context.get("logger", None)

        if mode != 'rtsp' or not stream_units:
            time.sleep(0.05)
            continue

        unit_idx = rr_index % len(stream_units)
        unit = stream_units[unit_idx]

        handler = unit.get("handler")
        engine = unit.get("engine")
        url = unit.get("url", "")
        label = unit.get("label", "")

        frame = unit.get("latest_raw_frame")
        if frame is None and handler is not None:
            frame = handler.get_latest_frame()

        if frame is not None and engine is not None:
            conf_thresh = config.get("conf_threshold", 0.25)
            detections, inf_time = engine.infer(frame, conf_thresh)
            if logger:
                logger.add_inference_time(inf_time)
                if detections:
                    logger.log_detection(url, detections)

            formatted_detections = []
            for det in detections:
                xyxy = det.get("xyxy", [])
                if isinstance(xyxy, list) and len(xyxy) > 0 and isinstance(xyxy[0], (list, tuple)):
                    coords = [float(x) for x in xyxy[0]]
                elif isinstance(xyxy, np.ndarray):
                    coords = [float(x) for x in xyxy.tolist()]
                else:
                    coords = [float(x) for x in xyxy]

                formatted_detections.append({
                    "xyxy": coords,
                    "cls": int(det["cls"]),
                    "conf": float(det["conf"])
                })

            h, w = frame.shape[:2]
            web_ui.LATEST_DETECTIONS[unit_idx] = {
                "stream_url": url,
                "stream_index": unit_idx,
                "label": label if label else url,
                "detections": formatted_detections,
                "frame_w": w,
                "frame_h": h,
                "ts": time.time()
            }

        rr_index = (rr_index + 1) % len(stream_units)
        time.sleep(0.01)


def build_stream_units(stream_configs, cpu_cores=4, fps_limit=5, existing_engine_cache=None):
    if existing_engine_cache is None:
        existing_engine_cache = {}
        
    new_engine_cache = {}
    stream_units = []
    
    for cfg in stream_configs:
        url = cfg["url"]
        model_path = cfg["model"]
        label = cfg["label"]
        
        if model_path in new_engine_cache:
            engine = new_engine_cache[model_path]
        elif model_path in existing_engine_cache and getattr(existing_engine_cache[model_path], 'num_threads', None) == cpu_cores:
            engine = existing_engine_cache[model_path]
            new_engine_cache[model_path] = engine
        else:
            print(f"[EngineCache] Loading InferenceEngine for model: {model_path} (threads: {cpu_cores})")
            engine = InferenceEngine(model_path=model_path, num_threads=cpu_cores)
            new_engine_cache[model_path] = engine
            
        handler = StreamHandler(url, fps_limit)
        handler.start()
        stream_units.append({
            "handler": handler,
            "engine": engine,
            "url": url,
            "model_path": model_path,
            "label": label,
            "latest_raw_frame": None
        })
        
    return stream_units, new_engine_cache

def main():
    # 啟動 Web UI
    threading.Thread(target=run_web_ui, daemon=True).start()
    
    config_mgr = ConfigManager()
    config = config_mgr.config
    
    logger = StatsLogger(
        log_file=config.get("log_file", "performance.log"),
        detection_log_file=config.get("detection_log_file", "detections.log")
    )
    
    mode = config.get("mode", "rtsp")
    cpu_cores = config.get("cpu_cores", 4)
    fps_limit = config.get("fps_limit", 5)
    
    engine_cache = {}
    stream_units = []
    video_handler = None
    video_engine = None
    
    context = {
        "stream_units": [],
        "config": config,
        "logger": logger,
        "mode": mode,
        "running": True
    }
    
    threading.Thread(target=_inference_worker, args=(context,), daemon=True).start()
    
    if mode == 'rtsp':
        stream_configs = config_mgr.get_stream_configs()
        stream_units, engine_cache = build_stream_units(stream_configs, cpu_cores, fps_limit)
        web_ui.STREAM_UNITS = stream_units
        context["stream_units"] = stream_units
        if stream_units:
            first_engine = stream_units[0]["engine"]
            web_ui.MODEL_INFO = {
                "type": first_engine.model_type,
                "path": ", ".join(list(engine_cache.keys())),
                "cpu_cores": cpu_cores
            }
    elif mode == 'video':
        video_path = config.get("video_path", "")
        if video_path:
            video_handler = VideoHandler(video_path)
            video_handler.start()
        video_engine = InferenceEngine(
            model_path=config.get("model_path", "yolov8n.pt"),
            num_threads=cpu_cores
        )
        web_ui.STREAM_UNITS = [{
            "handler": video_handler,
            "url": video_path,
            "label": "Video Stream",
            "latest_raw_frame": None
        }]
        web_ui.MODEL_INFO = {
            "type": video_engine.model_type,
            "path": video_engine.model_path,
            "cpu_cores": cpu_cores
        }

    last_log_time = time.time()
    log_interval = config.get("log_interval_seconds", 60)
    
    latest_frames = {}

    try:
        while True:
            if config_mgr.check_for_updates():
                new_config = config_mgr.config
                print("[Config] Settings updated dynamically!")
                
                logger = StatsLogger(
                    log_file=new_config.get("log_file", "performance.log"),
                    detection_log_file=new_config.get("detection_log_file", "detections.log")
                )
                
                new_mode = new_config.get("mode", "rtsp")
                new_cores = new_config.get("cpu_cores", 4)
                new_fps = new_config.get("fps_limit", 5)
                
                for unit in stream_units:
                    unit["handler"].stop()
                stream_units = []
                web_ui.STREAM_UNITS = []
                
                if video_handler:
                    video_handler.stop()
                    video_handler = None
                
                latest_frames = {}
                
                mode = new_mode
                cpu_cores = new_cores
                fps_limit = new_fps
                
                if mode == 'rtsp':
                    stream_configs = config_mgr.get_stream_configs()
                    stream_units, engine_cache = build_stream_units(
                        stream_configs, cpu_cores, fps_limit, existing_engine_cache=engine_cache
                    )
                    web_ui.STREAM_UNITS = stream_units
                    if stream_units:
                        first_engine = stream_units[0]["engine"]
                        web_ui.MODEL_INFO = {
                            "type": first_engine.model_type,
                            "path": ", ".join(list(engine_cache.keys())),
                            "cpu_cores": cpu_cores
                        }
                elif mode == 'video':
                    video_path = new_config.get("video_path", "")
                    if video_path:
                        video_handler = VideoHandler(video_path)
                        video_handler.start()
                    
                    model_path = new_config.get("model_path", "yolov8n.pt")
                    video_engine = InferenceEngine(model_path=model_path, num_threads=cpu_cores)
                    web_ui.STREAM_UNITS = [{
                        "handler": video_handler,
                        "url": video_path,
                        "label": "Video Stream",
                        "latest_raw_frame": None
                    }]
                    web_ui.MODEL_INFO = {
                        "type": video_engine.model_type,
                        "path": video_engine.model_path,
                        "cpu_cores": cpu_cores
                    }
                    
                log_interval = new_config.get("log_interval_seconds", 60)
                config = new_config
                
                context["stream_units"] = stream_units
                context["config"] = config
                context["logger"] = logger
                context["mode"] = mode

            if mode == 'rtsp':
                if stream_units:
                    for unit in stream_units:
                        handler = unit["handler"]
                        frame = handler.get_latest_frame()
                        if frame is not None:
                            unit["latest_raw_frame"] = frame
                            latest_frames[unit["url"]] = frame
                    
                    active_frames = [latest_frames[u["url"]] for u in stream_units if u["url"] in latest_frames]
                    if active_frames:
                        grid_img = compose_grid(active_frames, target_width=640)
                        if grid_img is not None:
                            ret_enc, buffer = cv2.imencode('.jpg', grid_img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                            if ret_enc:
                                web_ui.LATEST_FRAME = buffer.tobytes()

            elif mode == 'video' and video_handler and video_engine:
                frame = video_handler.get_latest_frame()
                if frame is not None:
                    if web_ui.STREAM_UNITS:
                        web_ui.STREAM_UNITS[0]["latest_raw_frame"] = frame
                    detections, inf_time = video_engine.infer(frame, config.get("conf_threshold", 0.25))
                    logger.add_inference_time(inf_time)
                    video_handler.update_detections(detections)
                    if detections:
                        logger.log_detection(config.get("video_path", ""), detections)
                
                fps_lim = config.get("fps_limit", 30)
                if fps_lim > 0:
                    time.sleep(1.0 / fps_lim)

            if time.time() - last_log_time > log_interval:
                logger.log_stats()
                last_log_time = time.time()
            
            if mode == 'rtsp':
                time.sleep(0.01)

    except KeyboardInterrupt:
        context["running"] = False
        for unit in stream_units:
            unit["handler"].stop()
        if video_handler:
            video_handler.stop()

if __name__ == "__main__":
    main()

