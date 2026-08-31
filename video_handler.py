import cv2
import threading
import queue
import time

class VideoHandler:
    """
    專屬本地影片檔案處理器：
    - 採用雙執行緒解耦架構，獨立於 YOLO 推論引擎。
    - 依照影片原始 FPS (原生速率) 進行時間步進與無縫循環播放。
    - 即時將疊減最新辨識框的影像推送至 web_ui.LATEST_FRAME (實現 30 FPS 高流暢度)。
    """
    def __init__(self, video_path):
        self.video_path = video_path
        self.frame_queue = queue.Queue(maxsize=1)
        self.running = False
        self.thread = None
        self.latest_detections = []
        self.lock = threading.Lock()
        self.native_fps = 30.0
        self.last_frame = None
        self.last_pts = 0.0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._play_video, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

    def update_detections(self, detections):
        with self.lock:
            self.latest_detections = list(detections)

    def get_latest_detections(self):
        with self.lock:
            return list(self.latest_detections)

    def _play_video(self):
        import web_ui
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print(f"[VideoHandler] Error: Cannot open video file: {self.video_path}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps and fps > 0:
            self.native_fps = fps
        else:
            self.native_fps = 30.0

        frame_interval = 1.0 / self.native_fps

        while self.running:
            start_t = time.time()
            ret, frame = cap.read()
            if not ret:
                # 無縫倒帶循環播放
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.update_detections([])
                if 0 in web_ui.LATEST_DETECTIONS:
                    web_ui.LATEST_DETECTIONS[0] = {}
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

            pts_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            # 946684800000 ms = 2000-01-01 00:00:00 UTC
            if isinstance(pts_ms, (int, float)) and pts_ms >= 946684800000.0:
                pts = float(pts_ms) / 1000.0
            else:
                pts = start_t

            # 更新 raw frame 至 queue 供推論引擎讀取
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            self.frame_queue.put((frame.copy(), pts))
            self.last_frame = frame
            self.last_pts = pts

            # 直接編碼原始 Clean 畫面供 Web UI MJPEG 串流
            ret_enc, buffer = cv2.imencode('.jpg', frame)
            if ret_enc:
                web_ui.LATEST_FRAME = buffer.tobytes()

            # 動態補償時間，確保維持影片原速 1.0x 播放
            elapsed = time.time() - start_t
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        cap.release()

    def get_latest_frame(self):
        try:
            item = self.frame_queue.get_nowait()
            if isinstance(item, tuple):
                self.last_frame, self.last_pts = item
            else:
                self.last_frame = item
                self.last_pts = time.time()
            return self.last_frame
        except queue.Empty:
            return self.last_frame

    def get_latest_pts(self):
        return getattr(self, "last_pts", 0.0)

    def get_latest_frame_and_pts(self):
        frame = self.get_latest_frame()
        return frame, self.get_latest_pts()
