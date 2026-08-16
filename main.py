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
import model_sync

import argus_eventlog
from argus_eventlog import EventWriterService
import event_producer

argus_eventlog.writer.DEFAULT_PROG = "SafetyNano"


def format_detections(raw_detections):
    """把 InferenceEngine.infer() 回傳的原始 detections 轉成扁平格式，
    供 Web UI 顯示與 event_producer 共用（取代先前 RTSP/video 兩路各自重複一份的格式化程式碼）。
    """
    formatted = []
    for det in raw_detections:
        xyxy = det.get("xyxy", [])
        if isinstance(xyxy, list) and len(xyxy) > 0 and isinstance(xyxy[0], (list, tuple)):
            coords = [float(x) for x in xyxy[0]]
        elif isinstance(xyxy, np.ndarray):
            coords = [float(x) for x in xyxy.tolist()]
        else:
            coords = [float(x) for x in xyxy]

        formatted.append({
            "xyxy": coords,
            "cls": int(det["cls"]),
            "conf": float(det["conf"]),
            "label": det.get("label", str(int(det["cls"])))
        })
    return formatted


def run_web_ui():
    app.run(host="0.0.0.0", port=8188, use_reloader=False)

def _inference_worker(context):
    """
    背景推論執行緒，Round-Robin 對各 RTSP 串流根據 fps_limit 獨立時間點抽樣執行 YOLO 推論，
    寫入 web_ui.LATEST_DETECTIONS。
    """
    rr_index = 0
    last_infer_times = {}
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

        fps_limit = config.get("fps_limit", 5)
        interval = 1.0 / fps_limit if fps_limit > 0 else 0
        now = time.time()

        if now - last_infer_times.get(unit_idx, 0) >= interval:
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

                formatted_detections = format_detections(detections)

                zones_cfg = config.get("zones") if isinstance(config.get("zones"), dict) else {}
                stream_zone = zones_cfg.get(url)

                h, w = frame.shape[:2]
                event_producer.process_detections(
                    unit_idx, unit.get("camera_id", "unknown"),
                    formatted_detections, w, h,
                    config.get("event_severity", {}),
                    config.get("event_absence_tolerance", 2),
                    zone=stream_zone,
                )
                web_ui.LATEST_DETECTIONS[unit_idx] = {
                    "stream_url": url,
                    "stream_index": unit_idx,
                    "label": label if label else url,
                    "detections": formatted_detections,
                    "frame_w": w,
                    "frame_h": h,
                    "ts": now,
                    "zone": stream_zone,
                }
                last_infer_times[unit_idx] = now

        rr_index = (rr_index + 1) % len(stream_units)
        time.sleep(0.01)


def build_stream_units(stream_configs, cpu_cores=4, fps_limit=5, existing_engine_cache=None):
    if existing_engine_cache is None:
        existing_engine_cache = {}
        
    new_engine_cache = {}
    stream_units = []
    
    for idx, cfg in enumerate(stream_configs):
        url = cfg["url"]
        model_path = cfg["model"]
        label = cfg["label"]
        camera_id = cfg.get("camera_id") or label or f"stream{idx}"

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
            "camera_id": camera_id,
            "latest_raw_frame": None
        })
        
    return stream_units, new_engine_cache

def initialize_runtime(config_mgr):
    """開機時執行一次 UMS 模型同步（失敗不中止，沿用舊 model_path/streams[].model），
    再依（可能已被同步寫回更新的）config 建立初始執行環境。"""
    sync_report = model_sync.sync_all(config_mgr)
    if sync_report["success"] or sync_report["failed"]:
        print(f"[ModelSync] 開機同步完成：成功 {len(sync_report['success'])}，失敗 {len(sync_report['failed'])}")
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
        web_ui.STREAM_UNITS = stream_units
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

    return {
        "config": config,
        "logger": logger,
        "mode": mode,
        "cpu_cores": cpu_cores,
        "fps_limit": fps_limit,
        "engine_cache": engine_cache,
        "stream_units": stream_units,
        "video_handler": video_handler,
        "video_engine": video_engine,
    }


def main():
    # 啟動 Web UI
    threading.Thread(target=run_web_ui, daemon=True).start()

    # 整個 process 只開一個 EventWriterService（見 ADR-014 決策 5：多鏡頭共用一個
    # 全域 event_queue，寫入路徑改依 record 自己的 camera_id 路由，不用每鏡頭各開一個實例）
    event_writer = EventWriterService()
    event_writer.start()

    config_mgr = ConfigManager()
    state = initialize_runtime(config_mgr)

    config = state["config"]
    logger = state["logger"]
    mode = state["mode"]
    cpu_cores = state["cpu_cores"]
    fps_limit = state["fps_limit"]
    engine_cache = state["engine_cache"]
    stream_units = state["stream_units"]
    video_handler = state["video_handler"]
    video_engine = state["video_engine"]

    context = {
        "stream_units": stream_units,
        "config": config,
        "logger": logger,
        "mode": mode,
        "running": True
    }

    threading.Thread(target=_inference_worker, args=(context,), daemon=True).start()

    last_log_time = time.time()
    last_video_infer_time = 0
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
                    
                    fps_lim = config.get("fps_limit", 30)
                    interval = 1.0 / fps_lim if fps_lim > 0 else 0
                    now = time.time()

                    if now - last_video_infer_time >= interval:
                        detections, inf_time = video_engine.infer(frame, config.get("conf_threshold", 0.25))
                        logger.add_inference_time(inf_time)
                        video_handler.update_detections(detections)
                        if detections:
                            logger.log_detection(config.get("video_path", ""), detections)
                        
                        formatted_detections = format_detections(detections)
                        h, w = frame.shape[:2]
                        video_camera_id = config.get("camera_id") or "video"
                        video_url = config.get("video_path", "")
                        zones_cfg = config.get("zones") if isinstance(config.get("zones"), dict) else {}
                        video_zone = zones_cfg.get(video_url)

                        event_producer.process_detections(
                            "video", video_camera_id,
                            formatted_detections, w, h,
                            config.get("event_severity", {}),
                            config.get("event_absence_tolerance", 2),
                            zone=video_zone,
                        )
                        web_ui.LATEST_DETECTIONS[0] = {
                            "stream_url": video_url,
                            "stream_index": 0,
                            "label": "Video Stream",
                            "detections": formatted_detections,
                            "frame_w": w,
                            "frame_h": h,
                            "ts": now,
                            "zone": video_zone,
                        }
                        last_video_infer_time = now

            if time.time() - last_log_time > log_interval:
                logger.log_stats()
                last_log_time = time.time()
            
            time.sleep(0.01)

    except KeyboardInterrupt:
        context["running"] = False
        for unit in stream_units:
            unit["handler"].stop()
        if video_handler:
            video_handler.stop()
        event_writer.stop()

if __name__ == "__main__":
    main()

