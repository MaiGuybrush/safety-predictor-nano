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
from stats_logger import StatsLogger, setup_system_logger, get_system_logger, configure_werkzeug_logger
from grid_composer import annotate_frame, compose_grid
import model_sync
from retention_cleaner import RetentionCleanerService
from state_poller import GLOBAL_STATE_POLLER
from compliance_engine import ComplianceEngine
import argus_eventlog
from argus_eventlog import EventWriterService, HeartbeatService, get_event_output_path, parse_camera_id
import event_producer
from diagnostic_collector import install_crash_handler

install_crash_handler("logs")

argus_eventlog.writer.DEFAULT_PROG = "SafetyNano"


def start_heartbeat_services(config, stream_units, mode="rtsp", video_camera_id="video"):
    """根據 config 與當前串流單元為各 stream / video 啟動 HeartbeatService 實例列表。"""
    hb_cfg = config.get("heartbeat", {})
    if not isinstance(hb_cfg, dict):
        hb_cfg = {}

    if not hb_cfg.get("enabled", True):
        return []

    ap_name = hb_cfg.get("ap_name", "SafetyNano")
    interval = hb_cfg.get("interval_seconds", 60)
    version = hb_cfg.get("version", "0.1.0")
    agent_port = hb_cfg.get("agent_port", None)

    services = []
    if mode == "rtsp":
        for unit in stream_units:
            cam_id = unit.get("camera_id", "unknown")
            events_dir, _ = get_event_output_path(unit.get("url", ""))
            if f"/{cam_id}/events" not in events_dir.replace("\\", "/"):
                import sys
                exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(sys.argv[0]))
                events_dir = os.path.normpath(os.path.join(exe_dir, "recordings", cam_id, "events"))

            svc = HeartbeatService(
                ap_name=ap_name,
                instance=cam_id,
                version=version,
                event_output_path=events_dir,
                camera_id=cam_id,
                interval_seconds=interval,
                agent_port=agent_port,
            )
            svc.start()
            services.append(svc)
    elif mode == "video":
        import sys
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(sys.argv[0]))
        events_dir = os.path.normpath(os.path.join(exe_dir, "recordings", video_camera_id, "events"))
        svc = HeartbeatService(
            ap_name=ap_name,
            instance=video_camera_id,
            version=version,
            event_output_path=events_dir,
            camera_id=video_camera_id,
            interval_seconds=interval,
            agent_port=agent_port,
        )
        svc.start()
        services.append(svc)

    return services


def stop_heartbeat_services(services):
    """停止所有 Heartbeat 服務實例。"""
    for svc in services:
        try:
            svc.stop()
        except Exception as e:
            print(f"[Heartbeat] Stop error: {e}")


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
            pts = unit.get("latest_pts")
            if frame is None and handler is not None:
                frame, pts = handler.get_latest_frame_and_pts()

            if frame is not None and engine is not None:
                conf_thresh = config.get("conf_threshold", 0.25)
                detections, inf_time = engine.infer(frame, conf_thresh)
                infer_done_ts = time.time()
                if logger:
                    logger.add_inference_time(inf_time)
                    if detections:
                        logger.log_detection(url, detections)

                formatted_detections = format_detections(detections)

                zones_cfg = config.get("zones") if isinstance(config.get("zones"), dict) else {}
                stream_zone = zones_cfg.get(url)

                h, w = frame.shape[:2]
                if isinstance(stream_zone, dict) and stream_zone.get("polygon") and len(stream_zone["polygon"]) >= 3:
                    poly = stream_zone["polygon"]
                    t_mode = stream_zone.get("trigger_mode", "center")
                    sens = float(stream_zone.get("sensitivity", 0.0))
                    for d in formatted_detections:
                        d["in_zone"] = event_producer._is_inside_zone(d, poly, w, h, trigger_mode=t_mode, sensitivity=sens)
                else:
                    for d in formatted_detections:
                        d["in_zone"] = False

                compliance_engine = context.get("compliance_engine")
                comp_summary = None
                if compliance_engine is not None:
                    ext_states = GLOBAL_STATE_POLLER.get_current_states()
                    rules = config.get("compliance_rules", [])
                    enriched_detections, compliance_events, comp_summary = compliance_engine.evaluate(
                        formatted_detections,
                        stream_zone=stream_zone,
                        external_states=ext_states,
                        rules=rules,
                    )
                    formatted_detections = enriched_detections
                    web_ui.LATEST_COMPLIANCE_STATUS[unit_idx] = comp_summary
                    if compliance_events:
                        event_producer.process_compliance_events(
                            unit_idx, unit.get("camera_id", "unknown"),
                            compliance_events, w, h,
                            config.get("event_severity", {}),
                            config.get("event_absence_tolerance", 2),
                            zone=stream_zone,
                            pts=pts,
                            clean_frame=frame,
                        )

                event_producer.process_detections(
                    unit_idx, unit.get("camera_id", "unknown"),
                    formatted_detections, w, h,
                    config.get("event_severity", {}),
                    config.get("event_absence_tolerance", 2),
                    zone=stream_zone,
                    pts=pts,
                    clean_frame=frame,
                )
                web_ui.LATEST_DETECTIONS[unit_idx] = {
                    "stream_url": url,
                    "stream_index": unit_idx,
                    "label": label if label else url,
                    "detections": formatted_detections,
                    "compliance_summary": comp_summary,
                    "frame_w": w,
                    "frame_h": h,
                    "ts": infer_done_ts,
                    "zone": stream_zone,
                }
                last_infer_times[unit_idx] = infer_done_ts
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
        model_format = cfg.get("model_format", "auto")
        label = cfg["label"]
        camera_id = cfg.get("camera_id") or parse_camera_id(url) or label or f"stream{idx}"

        cache_key = (model_path, model_format)
        if cache_key in new_engine_cache:
            engine = new_engine_cache[cache_key]
        elif cache_key in existing_engine_cache and getattr(existing_engine_cache[cache_key], 'num_threads', None) == cpu_cores:
            engine = existing_engine_cache[cache_key]
            new_engine_cache[cache_key] = engine
        else:
            print(f"[EngineCache] Loading InferenceEngine for model: {model_path} (threads: {cpu_cores})")
            engine = InferenceEngine(model_path=model_path, num_threads=cpu_cores, model_format=model_format)
            new_engine_cache[cache_key] = engine

        print(f"[Stream] Stream #{idx} ({camera_id}) -> Config: {model_path} ({model_format}) -> Resolved: {getattr(engine, 'actual_model_path', model_path)} [{getattr(engine, 'model_type', 'Unknown')}]")

        handler = StreamHandler(url, fps_limit)
        handler.start()
        stream_units.append({
            "handler": handler,
            "engine": engine,
            "url": url,
            "model_path": model_path,
            "model_format": model_format,
            "label": label,
            "camera_id": camera_id,
            "latest_raw_frame": None
        })
        
    return stream_units, new_engine_cache

def update_rtsp_model_info(stream_units, engine_cache, cpu_cores):
    """更新 Web UI 的全域 MODEL_INFO，支援 tuple cache key (model_path, model_format) 解構並附帶各串流解析資訊。"""
    if not stream_units:
        return
    first_engine = stream_units[0]["engine"]
    model_paths = [k[0] if isinstance(k, tuple) else k for k in engine_cache.keys()]
    streams_info = []
    for idx, unit in enumerate(stream_units):
        engine = unit.get("engine")
        streams_info.append({
            "stream_index": idx,
            "camera_id": unit.get("camera_id", ""),
            "url": unit.get("url", ""),
            "label": unit.get("label", ""),
            "configured_model": unit.get("model_path", ""),
            "model_format": unit.get("model_format", "auto"),
            "resolved_model_path": getattr(engine, "actual_model_path", unit.get("model_path", "")),
            "model_type": getattr(engine, "model_type", "PyTorch"),
        })
    web_ui.MODEL_INFO = {
        "type": first_engine.model_type if first_engine else "Unknown",
        "path": ", ".join(list(dict.fromkeys(model_paths))),
        "cpu_cores": cpu_cores,
        "streams": streams_info
    }

def initialize_runtime(config_mgr):
    """開機時執行一次 UMS 模型同步（失敗不中止，沿用舊 model_path/streams[].model），
    再依（可能已被同步寫回更新的）config 建立初始執行環境。"""
    config = config_mgr.config
    sys_logger = setup_system_logger(
        log_file=config.get("system_log_file", "logs/system.log"),
        log_level=config.get("log_level", "INFO"),
        backup_count=int(config.get("log_backup_count", 3))
    )

    sync_report = model_sync.sync_all(config_mgr)
    if sync_report["success"] or sync_report["failed"]:
        sys_logger.info(f"[ModelSync] 開機同步完成：成功 {len(sync_report['success'])}，失敗 {len(sync_report['failed'])}")
    if sync_report["failed"]:
        for fail in sync_report["failed"]:
            sys_logger.error(f"[ModelSync Error] 開機同步失敗 [{fail['name']}@{fail['version']}]: {fail['error']}")
    config = config_mgr.config

    logger = StatsLogger(
        log_file=config.get("log_file", "logs/performance.log"),
        detection_log_file=config.get("detection_log_file", "logs/detections.log"),
        backup_count=int(config.get("log_backup_count", 3))
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
        update_rtsp_model_info(stream_units, engine_cache, cpu_cores)
    elif mode == 'video':
        video_path = config.get("video_path", "")
        if video_path:
            video_handler = VideoHandler(video_path)
            video_handler.start()
        video_model_path = config.get("model_path", "yolov8n.pt")
        video_model_format = config.get("model_format", "auto")
        video_engine = InferenceEngine(
            model_path=video_model_path,
            num_threads=cpu_cores,
            model_format=video_model_format
        )
        video_camera_id = config.get("camera_id") or parse_camera_id(video_path) or "video"
        print(f"[Stream] Video Stream ({video_camera_id}) -> Config: {video_model_path} ({video_model_format}) -> Resolved: {getattr(video_engine, 'actual_model_path', video_model_path)} [{video_engine.model_type}]")
        web_ui.STREAM_UNITS = [{
            "handler": video_handler,
            "url": video_path,
            "label": "Video Stream",
            "latest_raw_frame": None
        }]
        web_ui.MODEL_INFO = {
            "type": video_engine.model_type,
            "path": getattr(video_engine, "actual_model_path", video_engine.model_path),
            "cpu_cores": cpu_cores,
            "streams": [{
                "stream_index": 0,
                "camera_id": video_camera_id,
                "url": video_path,
                "label": "Video Stream",
                "configured_model": video_model_path,
                "model_format": video_model_format,
                "resolved_model_path": getattr(video_engine, "actual_model_path", video_model_path),
                "model_type": video_engine.model_type,
            }]
        }

    compliance_engine = ComplianceEngine(config_mgr.get_ppe_class_mapping())
    GLOBAL_STATE_POLLER.update_config(config_mgr.get_external_states())
    GLOBAL_STATE_POLLER.start()

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
        "compliance_engine": compliance_engine,
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

    retention_cleaner = RetentionCleanerService(config_mgr)
    retention_cleaner.start()

    config = state["config"]
    logger = state["logger"]
    mode = state["mode"]
    cpu_cores = state["cpu_cores"]
    fps_limit = state["fps_limit"]
    engine_cache = state["engine_cache"]
    stream_units = state["stream_units"]
    video_handler = state["video_handler"]
    video_engine = state["video_engine"]
    compliance_engine = state.get("compliance_engine")

    video_camera_id = config.get("camera_id") or parse_camera_id(config.get("video_path", "")) or "video"
    heartbeat_services = start_heartbeat_services(config, stream_units, mode=mode, video_camera_id=video_camera_id)

    context = {
        "stream_units": stream_units,
        "config": config,
        "logger": logger,
        "mode": mode,
        "compliance_engine": compliance_engine,
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
                new_config = config_mgr.config or {}
                sys_logger = setup_system_logger(
                    log_file=new_config.get("system_log_file", "logs/system.log"),
                    log_level=new_config.get("log_level", "INFO"),
                    backup_count=int(new_config.get("log_backup_count", 3))
                )
                sys_logger.info("[Config] Settings updated dynamically!")
                
                logger = StatsLogger(
                    log_file=new_config.get("log_file", "logs/performance.log"),
                    detection_log_file=new_config.get("detection_log_file", "logs/detections.log"),
                    backup_count=int(new_config.get("log_backup_count", 3))
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
                
                stop_heartbeat_services(heartbeat_services)
                heartbeat_services = []

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
                    update_rtsp_model_info(stream_units, engine_cache, cpu_cores)
                elif mode == 'video':
                    video_path = new_config.get("video_path", "")
                    if video_path:
                        video_handler = VideoHandler(video_path)
                        video_handler.start()
                    
                    model_path = new_config.get("model_path", "yolov8n.pt")
                    model_format = new_config.get("model_format", "auto")
                    video_engine = InferenceEngine(model_path=model_path, num_threads=cpu_cores, model_format=model_format)
                    video_camera_id = new_config.get("camera_id") or parse_camera_id(new_config.get("video_path", "")) or "video"
                    print(f"[Stream] Video Stream ({video_camera_id}) -> Config: {model_path} ({model_format}) -> Resolved: {getattr(video_engine, 'actual_model_path', model_path)} [{video_engine.model_type}]")
                    web_ui.STREAM_UNITS = [{
                        "handler": video_handler,
                        "url": video_path,
                        "label": "Video Stream",
                        "latest_raw_frame": None
                    }]
                    web_ui.MODEL_INFO = {
                        "type": video_engine.model_type,
                        "path": getattr(video_engine, "actual_model_path", video_engine.model_path),
                        "cpu_cores": cpu_cores,
                        "streams": [{
                            "stream_index": 0,
                            "camera_id": video_camera_id,
                            "url": video_path,
                            "label": "Video Stream",
                            "configured_model": model_path,
                            "model_format": model_format,
                            "resolved_model_path": getattr(video_engine, "actual_model_path", model_path),
                            "model_type": video_engine.model_type,
                        }]
                    }
                    
                video_camera_id = new_config.get("camera_id") or parse_camera_id(new_config.get("video_path", "")) or "video"
                heartbeat_services = start_heartbeat_services(new_config, stream_units, mode=mode, video_camera_id=video_camera_id)

                log_interval = new_config.get("log_interval_seconds", 60)
                config = new_config
                
                if compliance_engine:
                    compliance_engine.set_mapping(config_mgr.get_ppe_class_mapping())
                GLOBAL_STATE_POLLER.update_config(config_mgr.get_external_states())

                context["stream_units"] = stream_units
                context["config"] = config
                context["logger"] = logger
                context["mode"] = mode
                context["compliance_engine"] = compliance_engine
            if mode == 'rtsp':
                if stream_units:
                    for unit in stream_units:
                        handler = unit["handler"]
                        frame, pts = handler.get_latest_frame_and_pts()
                        if frame is not None:
                            unit["latest_raw_frame"] = frame
                            unit["latest_pts"] = pts
                            latest_frames[unit["url"]] = frame
                    
                    if web_ui.is_streaming_active():
                        active_frames = [latest_frames[u["url"]] for u in stream_units if u["url"] in latest_frames]
                        if active_frames:
                            grid_img = compose_grid(active_frames, target_width=640)
                            if grid_img is not None:
                                ret_enc, buffer = cv2.imencode('.jpg', grid_img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                                if ret_enc:
                                    web_ui.LATEST_FRAME = buffer.tobytes()

            elif mode == 'video' and video_handler and video_engine:
                frame, pts = video_handler.get_latest_frame_and_pts()
                if frame is not None:
                    if web_ui.STREAM_UNITS:
                        web_ui.STREAM_UNITS[0]["latest_raw_frame"] = frame
                        web_ui.STREAM_UNITS[0]["latest_pts"] = pts
                    
                    fps_lim = config.get("fps_limit", 30)
                    interval = 1.0 / fps_lim if fps_lim > 0 else 0
                    now = time.time()

                    if now - last_video_infer_time >= interval:
                        detections, inf_time = video_engine.infer(frame, config.get("conf_threshold", 0.25))
                        infer_done_ts = time.time()
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

                        if isinstance(video_zone, dict) and video_zone.get("polygon") and len(video_zone["polygon"]) >= 3:
                            poly = video_zone["polygon"]
                            t_mode = video_zone.get("trigger_mode", "center")
                            sens = float(video_zone.get("sensitivity", 0.0))
                            for d in formatted_detections:
                                d["in_zone"] = event_producer._is_inside_zone(d, poly, w, h, trigger_mode=t_mode, sensitivity=sens)
                        else:
                            for d in formatted_detections:
                                d["in_zone"] = False
                        comp_summary = None
                        if compliance_engine is not None:
                            ext_states = GLOBAL_STATE_POLLER.get_current_states()
                            rules = config.get("compliance_rules", [])
                            enriched_detections, compliance_events, comp_summary = compliance_engine.evaluate(
                                formatted_detections,
                                stream_zone=video_zone,
                                external_states=ext_states,
                                rules=rules,
                            )
                            formatted_detections = enriched_detections
                            web_ui.LATEST_COMPLIANCE_STATUS[0] = comp_summary
                            if compliance_events:
                                event_producer.process_compliance_events(
                                    "video", video_camera_id,
                                    compliance_events, w, h,
                                    config.get("event_severity", {}),
                                    config.get("event_absence_tolerance", 2),
                                    zone=video_zone,
                                    pts=pts,
                                    clean_frame=frame,
                                )

                        event_producer.process_detections(
                            "video", video_camera_id,
                            formatted_detections, w, h,
                            config.get("event_severity", {}),
                            config.get("event_absence_tolerance", 2),
                            zone=video_zone,
                            pts=pts,
                            clean_frame=frame,
                        )
                        web_ui.LATEST_DETECTIONS[0] = {
                            "stream_url": video_url,
                            "stream_index": 0,
                            "label": "Video Stream",
                            "detections": formatted_detections,
                            "compliance_summary": comp_summary,
                            "frame_w": w,
                            "frame_h": h,
                            "ts": infer_done_ts,
                            "zone": video_zone,
                        }
                        last_video_infer_time = infer_done_ts

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
        stop_heartbeat_services(heartbeat_services)
        retention_cleaner.stop()
        event_writer.stop()

if __name__ == "__main__":
    import sys
    if "--report-issue" in sys.argv or "-r" in sys.argv:
        import report_issue
        cli_args = [arg for arg in sys.argv[1:] if arg not in ("--report-issue", "-r")]
        sys.exit(report_issue.run_cli(cli_args))
    else:
        main()



