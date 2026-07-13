from ultralytics import YOLO
import time

class InferenceEngine:
    def __init__(self, model_path="yolov8n.pt"):
        self.model = YOLO(model_path)
        
    def infer(self, frame, conf_threshold=0.25):
        start_time = time.time()
        # RPi 5 CPU 推論建議：使用 cpu，half=False (除非模型轉為 ONNX/OpenVINO)，verbose=False
        results = self.model.predict(frame, device='cpu', verbose=False, conf=conf_threshold)
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
