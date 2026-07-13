import psutil
import time
import logging

class StatsLogger:
    def __init__(self, log_file="performance.log", detection_log_file="detections.log"):
        self.log_file = log_file
        self.detection_log_file = detection_log_file
        
        # 設定 Performance Logger
        self.perf_logger = logging.getLogger("performance")
        self.perf_logger.setLevel(logging.INFO)
        if not self.perf_logger.handlers:
            handler = logging.FileHandler(self.log_file)
            handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
            self.perf_logger.addHandler(handler)

        # 設定 Detection Logger
        self.det_logger = logging.getLogger("detection")
        self.det_logger.setLevel(logging.INFO)
        if not self.det_logger.handlers:
            det_handler = logging.FileHandler(self.detection_log_file)
            det_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
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
