import cv2
import threading
import queue
import time

class StreamHandler:
    def __init__(self, rtsp_url, fps_limit):
        self.rtsp_url = rtsp_url
        self.fps_limit = fps_limit
        self.frame_queue = queue.Queue(maxsize=1)
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._capture_frames)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _capture_frames(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        # 設定為無頭模式，不需要 GUI
        # 對 RPi 來說，使用 FFmpeg 作為後端通常較好
        
        fail_count = 0
        while self.running:
            if not cap.isOpened():
                time.sleep(2)
                cap = cv2.VideoCapture(self.rtsp_url)
                continue

            ret, frame = cap.read()
            if not ret:
                fail_count += 1
                if fail_count > 10:  # 失敗超過 10 次，嘗試重新連線
                    cap.release()
                    time.sleep(1)
                    fail_count = 0
                time.sleep(0.5)
                continue
            
            fail_count = 0
            
            # 更新 queue，只保留最新的一幀
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            self.frame_queue.put(frame)
            time.sleep(1.0 / self.fps_limit)
        
        cap.release()

    def get_latest_frame(self):
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None
