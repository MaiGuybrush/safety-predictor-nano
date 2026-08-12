import os
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"
import cv2
import web_ui
import time
from config_manager import ConfigManager
from stream_handler import StreamHandler
from video_handler import VideoHandler

import threading
from web_ui import app

def run_web_ui():
    app.run(host="0.0.0.0", port=8188, use_reloader=False)

from inference_engine import InferenceEngine
from stats_logger import StatsLogger
def main():
    # 啟動 Web UI
    threading.Thread(target=run_web_ui, daemon=True).start()
    
    config_mgr = ConfigManager()
    config = config_mgr.config
    
    engine = InferenceEngine(
        model_path=config.get("model_path", "yolov8n.pt"),
        num_threads=config.get("cpu_cores", 4)
    )
    web_ui.MODEL_INFO = {
        "type": engine.model_type,
        "path": engine.model_path,
        "cpu_cores": config.get("cpu_cores", 4)
    }
    logger = StatsLogger(log_file=config.get("log_file", "performance.log"), detection_log_file=config.get("detection_log_file", "detections.log"))
    
    mode = config.get("mode", "rtsp")
    video_path = config.get("video_path", "")
    video_handler = None
    
    streams = []
    if mode == 'rtsp':
        streams = [StreamHandler(url, config.get("fps_limit", 5)) for url in config.get("rtsp_streams", [])]
        for s in streams:
            s.start()
    elif mode == 'video' and video_path:
        video_handler = VideoHandler(video_path)
        video_handler.start()

    last_log_time = time.time()
    log_interval = config.get("log_interval_seconds", 60)

    try:
        while True:
            if config_mgr.check_for_updates():
                new_config = config_mgr.config
                print("[Config] Settings updated dynamically!")
                
                # 更新 Logger
                logger = StatsLogger(log_file=new_config.get("log_file", "performance.log"), 
                                     detection_log_file=new_config.get("detection_log_file", "detections.log"))
                
                # 更新 Inference Engine
                model_changed = new_config.get("model_path") != config.get("model_path")
                cores_changed = new_config.get("cpu_cores") != config.get("cpu_cores")
                if model_changed or cores_changed:
                    engine = InferenceEngine(
                        model_path=new_config.get("model_path", "yolov8n.pt"),
                        num_threads=new_config.get("cpu_cores", 4)
                    )
                    web_ui.MODEL_INFO = {
                        "type": engine.model_type,
                        "path": engine.model_path,
                        "cpu_cores": new_config.get("cpu_cores", 4)
                    }
                
                # 更新 Streams / 模式
                mode_changed = new_config.get("mode") != config.get("mode")
                video_path_changed = new_config.get("video_path") != config.get("video_path")
                rtsp_changed = new_config.get("rtsp_streams") != config.get("rtsp_streams") or new_config.get("fps_limit") != config.get("fps_limit")
                
                if mode_changed or video_path_changed or rtsp_changed:
                    for s in streams:
                        s.stop()
                    streams = []
                    
                    if video_handler:
                        video_handler.stop()
                        video_handler = None
                        
                    mode = new_config.get("mode", "rtsp")
                    if mode == 'rtsp':
                        streams = [StreamHandler(url, new_config.get("fps_limit", 5)) for url in new_config.get("rtsp_streams", [])]
                        for s in streams:
                            s.start()
                    elif mode == 'video' and new_config.get("video_path", ""):
                        video_handler = VideoHandler(new_config.get("video_path", ""))
                        video_handler.start()
                log_interval = new_config.get("log_interval_seconds", 60)
                config = new_config

            mode = config.get("mode", "rtsp")
            
            if mode == 'rtsp':
                for s in streams:
                    frame = s.get_latest_frame()
                    if frame is not None:
                        detections, inf_time = engine.infer(frame, config.get("conf_threshold", 0.25))
                        logger.add_inference_time(inf_time)
                        
                        if detections:
                            logger.log_detection(s.rtsp_url, detections)
            elif mode == 'video' and video_handler:
                frame = video_handler.get_latest_frame()
                if frame is not None:
                    detections, inf_time = engine.infer(frame, config.get("conf_threshold", 0.25))
                    logger.add_inference_time(inf_time)
                    video_handler.update_detections(detections)
                    if detections:
                        logger.log_detection(config.get("video_path", ""), detections)
                
                fps_limit = config.get("fps_limit", 30)
                if fps_limit > 0:
                    time.sleep(1.0 / fps_limit)

            if time.time() - last_log_time > log_interval:
                logger.log_stats()
                last_log_time = time.time()
            
            if mode == 'rtsp':
                time.sleep(0.01)
    except KeyboardInterrupt:
        for s in streams:
            s.stop()
        if video_handler:
            video_handler.stop()

if __name__ == "__main__":
    main()

