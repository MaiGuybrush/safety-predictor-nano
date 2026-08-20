import os
import sys
import psutil
import time
import logging
from logging.handlers import TimedRotatingFileHandler

SYSTEM_LOG_FORMAT = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'


class SystemLogger:
    def __init__(self, log_file="logs/system.log", log_level="INFO", backup_count=3, name="system"):
        self.log_file = log_file
        self.backup_count = int(backup_count) if backup_count is not None else 3
        self.log_level_str = str(log_level).upper() if log_level else "INFO"
        self.level = getattr(logging, self.log_level_str, logging.INFO)
        self.name = name

        if self.log_file:
            dir_path = os.path.dirname(os.path.abspath(self.log_file))
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.level)
        self.logger.propagate = False

        # 清除既有 Handler 避免重載時重複掛載
        for h in list(self.logger.handlers):
            try:
                h.close()
            except Exception:
                pass
            self.logger.removeHandler(h)

        formatter = logging.Formatter(SYSTEM_LOG_FORMAT)

        # 1. Console (sys.stdout)
        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setLevel(self.level)
        self.console_handler.setFormatter(formatter)
        self.logger.addHandler(self.console_handler)

        # 2. TimedRotatingFileHandler (每日輪替, UTF-8)
        if self.log_file:
            self.file_handler = TimedRotatingFileHandler(
                self.log_file,
                when="midnight",
                interval=1,
                backupCount=self.backup_count,
                encoding="utf-8"
            )
            self.file_handler.setLevel(self.level)
            self.file_handler.setFormatter(formatter)
            self.logger.addHandler(self.file_handler)
        else:
            self.file_handler = None

    def get_logger(self):
        return self.logger

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self.logger.exception(msg, *args, **kwargs)


_system_logger_instance = None


def setup_system_logger(log_file="logs/system.log", log_level="INFO", backup_count=3, name="system") -> SystemLogger:
    global _system_logger_instance
    _system_logger_instance = SystemLogger(log_file=log_file, log_level=log_level, backup_count=backup_count, name=name)
    return _system_logger_instance


def get_system_logger(name="system") -> logging.Logger:
    return logging.getLogger(name)


def configure_werkzeug_logger(level=logging.WARNING):
    logging.getLogger('werkzeug').setLevel(level)


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
