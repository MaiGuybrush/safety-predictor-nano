import cv2
import threading
import queue
import time

import web_ui

class StreamHandler:
    def __init__(self, rtsp_url, fps_limit):
        self.rtsp_url = rtsp_url
        self.fps_limit = fps_limit
        self.frame_queue = queue.Queue(maxsize=1)
        self.running = False
        self.thread = None
        self.last_frame = None
        self.last_pts = 0.0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._capture_frames)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _open_capture(self):
        """建立 VideoCapture，統一設定 RTSP 接收 buffer（4MB）。
        
        加大 buffer 可防止高位元率 IDR frame（單幀可達 500KB+）截斷，
        避免 'corrupted macroblock' / 'Invalid level prefix' 解碼錯誤。
        """
        delimiter = "&" if "?" in self.rtsp_url else "?"
        cap = cv2.VideoCapture(
            f"{self.rtsp_url}{delimiter}buffer_size=4194304",
            cv2.CAP_FFMPEG
        )
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)  # OpenCV 內部幀佇列
        return cap

    def _capture_frames(self):
        cap = self._open_capture()
        fail_count = 0
        last_retrieve_time = 0
        try:
            while self.running:
                if not cap.isOpened():
                    cap.release()
                    time.sleep(2)
                    if not self.running:
                        break
                    cap = self._open_capture()  # 重連時保持相同 buffer 設定
                    continue

                grab_ok = cap.grab()
                if not grab_ok:
                    fail_count += 1
                    if fail_count > 10:  # 失敗超過 10 次，嘗試重新連線
                        cap.release()
                        time.sleep(1)
                        fail_count = 0
                    time.sleep(0.5)
                    continue
                
                fail_count = 0
                now = time.time()

                # 判斷是否需要進行昂貴的像素解碼 (retrieve)
                streaming_active = web_ui.is_streaming_active() if hasattr(web_ui, 'is_streaming_active') else False
                interval = (1.0 / self.fps_limit) if self.fps_limit > 0 else 0
                should_retrieve = streaming_active or (now - last_retrieve_time >= interval)

                if should_retrieve:
                    ret, frame = cap.retrieve()
                    if ret and frame is not None:
                        last_retrieve_time = now
                        pts_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                        if isinstance(pts_ms, (int, float)) and pts_ms > 0:
                            pts = float(pts_ms) / 1000.0
                        else:
                            pts = now

                        if self.frame_queue.full():
                            try:
                                self.frame_queue.get_nowait()
                            except queue.Empty:
                                pass
                        self.frame_queue.put((frame, pts))
                        self.last_frame = frame
                        self.last_pts = pts

                time.sleep(0.001)
        finally:
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
