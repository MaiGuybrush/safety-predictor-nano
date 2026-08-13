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
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

            # 更新 raw frame 至 queue 供推論引擎讀取
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            self.frame_queue.put(frame.copy())

            # 繪製最新 Bounding Box 疊加層
            display_frame = frame.copy()
            dets = self.get_latest_detections()
            for det in dets:
                xyxy = det.get("xyxy", [])
                if isinstance(xyxy, list) and len(xyxy) > 0 and isinstance(xyxy[0], (list, tuple)):
                    coords = xyxy[0]
                else:
                    coords = xyxy
                x1, y1, x2, y2 = map(int, coords)
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"Class {det['cls']} ({det['conf']:.2f})"
                cv2.putText(display_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # 編碼成 JPG 供 Web UI MJPEG 串流
            ret_enc, buffer = cv2.imencode('.jpg', display_frame)
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
            frame = self.frame_queue.get_nowait()
            self.last_frame = frame
            return frame
        except queue.Empty:
            return self.last_frame
