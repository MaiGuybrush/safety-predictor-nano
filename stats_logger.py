import os
import psutil
import time
import logging
from logging.handlers import TimedRotatingFileHandler

class StatsLogger:
    def __init__(self, log_file="logs/performance.log", detection_log_file="logs/detections.log", backup_count=3):
        self.log_file = log_file
        self.detection_log_file = detection_log_file
        self.backup_count = int(backup_count) if backup_count is not None else 3

        # 自動建立日誌所在目錄
        for path in (self.log_file, self.detection_log_file):
            if path:
                dir_path = os.path.dirname(os.path.abspath(path))
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
        
        formatter = logging.Formatter('%(asctime)s - %(message)s')

        # 設定 Performance Logger
        self.perf_logger = logging.getLogger("performance")
        self.perf_logger.setLevel(logging.INFO)
        self.perf_logger.propagate = False
        for h in list(self.perf_logger.handlers):
            try:
                h.close()
            except Exception:
                pass
            self.perf_logger.removeHandler(h)

        perf_handler = TimedRotatingFileHandler(
            self.log_file,
            when="midnight",
            interval=1,
            backupCount=self.backup_count,
            encoding="utf-8"
        )
        perf_handler.setFormatter(formatter)
        self.perf_logger.addHandler(perf_handler)

        # 設定 Detection Logger
        self.det_logger = logging.getLogger("detection")
        self.det_logger.setLevel(logging.INFO)
        self.det_logger.propagate = False
        for h in list(self.det_logger.handlers):
            try:
                h.close()
            except Exception:
                pass
            self.det_logger.removeHandler(h)

        det_handler = TimedRotatingFileHandler(
            self.detection_log_file,
            when="midnight",
            interval=1,
            backupCount=self.backup_count,
            encoding="utf-8"
        )
        det_handler.setFormatter(formatter)
        self.det_logger.addHandler(det_handler)

        self.inference_times = []

    def log_detection(self, rtsp_url, detections):
        # 將包含位置資訊的 dict 轉為字串記錄
        det_str = ", ".join([f"[Class:{d['cls']}, Conf:{d['conf']:.2f}, Box:{[int(x) for x in d['xyxy'][0]]}]" for d in detections])
        self.det_logger.info(f"Stream: {rtsp_url} - Detections: {len(detections)} - Details: {det_str}")

    def add_inference_time(self, time_ms):
        self.inference_times.append(time_ms)

    def log_stats(self):
        if not self.inference_times:
            return

        avg_time = sum(self.inference_times) / len(self.inference_times)
        max_time = max(self.inference_times)
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent

        msg = f"Avg Inference: {avg_time:.2f}ms, Max Inference: {max_time:.2f}ms, CPU: {cpu_usage}%, RAM: {ram_usage}%"
        self.perf_logger.info(msg)
        print(f"[Stats] {msg}")
        
        self.inference_times = []  # Reset
