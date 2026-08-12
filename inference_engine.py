import os
import time
from ultralytics import YOLO

class InferenceEngine:
    """
    統一推論引擎，根據 model_path 自動選擇後端：
    - .pt 結尾  → ultralytics PyTorch 後端
    - 資料夾    → ultralytics NCNN 後端（支援 float32 / int8）
    """

    def __init__(self, model_path="yolov8n.pt", num_threads=4):
        self.model_path = model_path
        self.num_threads = num_threads

        # 判斷後端類型（供 /model_info 使用）
        if os.path.isdir(model_path):
            self.model_type = "NCNN"
        else:
            self.model_type = "PyTorch"

        self.model = YOLO(model_path)

    def infer(self, frame, conf_threshold=0.25):
        start_time = time.time()
        results = self.model.predict(
            frame,
            device='cpu',
            verbose=False,
            conf=conf_threshold
        )
        end_time = time.time()

        inference_time = (end_time - start_time) * 1000  # ms

        detections = []
        for r in results:
            for box in r.boxes:
                detections.append({
                    "cls": int(box.cls),
                    "conf": float(box.conf),
                    "xyxy": box.xyxy.tolist()
                })

        return detections, inference_time

