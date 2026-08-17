import os
import time
from ultralytics import YOLO

class InferenceEngine:
    """
    統一推論引擎，根據 model_path 自動選擇後端：
    - .onnx 結尾  → ultralytics ONNX 後端
    - .pt 結尾    → ultralytics PyTorch 後端
    - NCNN 資料夾 → ultralytics NCNN 後端（支援 float32 / int8）
    - 一般資料夾  → 自動尋找內部 *.onnx 或 *.pt 檔案載入
    """

    def __init__(self, model_path="yolov8n.pt", num_threads=4):
        self.model_path = model_path
        self.num_threads = num_threads

        actual_model_path = model_path

        if os.path.isdir(model_path):
            files = os.listdir(model_path)
            onnx_files = [f for f in files if f.lower().endswith(".onnx")]
            pt_files = [f for f in files if f.lower().endswith(".pt")]
            has_ncnn = (
                os.path.exists(os.path.join(model_path, "model.ncnn.param")) or
                os.path.exists(os.path.join(model_path, "model.ncnn.bin")) or
                any(f.endswith(".ncnn.param") or f.endswith(".ncnn.bin") for f in files)
            )

            if onnx_files:
                best_onnx = "best.onnx" if "best.onnx" in onnx_files else onnx_files[0]
                actual_model_path = os.path.join(model_path, best_onnx)
                self.model_type = "ONNX"
            elif pt_files:
                best_pt = "best.pt" if "best.pt" in pt_files else pt_files[0]
                actual_model_path = os.path.join(model_path, best_pt)
                self.model_type = "PyTorch"
            elif has_ncnn:
                self.model_type = "NCNN"
                actual_model_path = model_path
            else:
                self.model_type = "PyTorch"
                actual_model_path = model_path
        elif model_path.lower().endswith(".onnx"):
            self.model_type = "ONNX"
        else:
            self.model_type = "PyTorch"

        self.model = YOLO(actual_model_path)

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
                cls_id = int(box.cls)
                detections.append({
                    "cls": cls_id,
                    "conf": float(box.conf),
                    "xyxy": box.xyxy.tolist(),
                    "label": r.names.get(cls_id, str(cls_id))
                })

        return detections, inference_time

