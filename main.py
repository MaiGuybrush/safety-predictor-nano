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
            "label": label
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
    
    if mode == 'rtsp':
        stream_configs = config_mgr.get_stream_configs()
        stream_units, engine_cache = build_stream_units(stream_configs, cpu_cores, fps_limit)
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
        web_ui.MODEL_INFO = {
            "type": video_engine.model_type,
            "path": video_engine.model_path,
            "cpu_cores": cpu_cores
        }

    last_log_time = time.time()
    log_interval = config.get("log_interval_seconds", 60)
    
    rr_index = 0
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
                
                if video_handler:
                    video_handler.stop()
                    video_handler = None
                
                latest_frames = {}
                rr_index = 0
                
                mode = new_mode
                cpu_cores = new_cores
                fps_limit = new_fps
                
                if mode == 'rtsp':
                    stream_configs = config_mgr.get_stream_configs()
                    stream_units, engine_cache = build_stream_units(
                        stream_configs, cpu_cores, fps_limit, existing_engine_cache=engine_cache
                    )
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
                    web_ui.MODEL_INFO = {
                        "type": video_engine.model_type,
                        "path": video_engine.model_path,
                        "cpu_cores": cpu_cores
                    }
                    
                log_interval = new_config.get("log_interval_seconds", 60)
                config = new_config

            if mode == 'rtsp':
                if stream_units:
                    unit = stream_units[rr_index % len(stream_units)]
                    handler = unit["handler"]
                    engine = unit["engine"]
                    url = unit["url"]
                    label = unit["label"]
                    
                    frame = handler.get_latest_frame()
                    if frame is not None:
                        detections, inf_time = engine.infer(frame, config.get("conf_threshold", 0.25))
                        logger.add_inference_time(inf_time)
                        if detections:
                            logger.log_detection(url, detections)
                        
                        annotated = annotate_frame(frame, detections, stream_label=label if label else url)
                        latest_frames[url] = annotated
                    
                    rr_index = (rr_index + 1) % len(stream_units)
                    
                    active_frames = [latest_frames[u["url"]] for u in stream_units if u["url"] in latest_frames]
                    if active_frames:
                        grid_img = compose_grid(active_frames, target_width=640)
                        if grid_img is not None:
                            ret_enc, buffer = cv2.imencode('.jpg', grid_img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                            if ret_enc:
                                web_ui.LATEST_FRAME = buffer.tobytes()

            elif mode == 'video' and video_handler and video_engine:
                frame = video_handler.get_latest_frame()
                if frame is not None:
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
        for unit in stream_units:
            unit["handler"].stop()
        if video_handler:
            video_handler.stop()

if __name__ == "__main__":
    main()
