import logging
import os
import sys
import time
import types
from ultralytics import YOLO

logger = logging.getLogger(__name__)

_is_compatibility_ensured = False

def _ensure_torchvision_compatibility():
    """
    確保 torchvision 可用；若遇到 operator torchvision::nms 缺失（常見於 PyInstaller 打包或
    ARM64 / 樹莓派環境中的 C++ extension 缺失），自動註冊相容 fallback，避免 AutoBackend.warmup
    觸發 RuntimeError 導致推論 worker 崩潰。
    """
    global _is_compatibility_ensured
    if _is_compatibility_ensured:
        return

    try:
        import torchvision
        if not hasattr(torchvision, "ops") or not hasattr(torchvision.ops, "nms"):
            raise RuntimeError("torchvision 缺少 ops.nms 算子屬性")
        import torch
        _test_boxes = torch.zeros((1, 4), dtype=torch.float32)
        _test_scores = torch.zeros((1,), dtype=torch.float32)
        torchvision.ops.nms(_test_boxes, _test_scores, 0.5)
        _is_compatibility_ensured = True
        return
    except Exception as e:
        logger.warning(
            f"[InferenceEngine] torchvision C++ 擴充不可用 ({e})，已啟用 Pure PyTorch NMS 容錯模式。"
        )
        from ultralytics.utils.nms import TorchNMS
        fallback_nms = TorchNMS.nms

        tv_module = sys.modules.get("torchvision")
        if tv_module is None or not isinstance(tv_module, types.ModuleType):
            tv_module = types.ModuleType("torchvision")
            sys.modules["torchvision"] = tv_module
        ops = types.ModuleType("torchvision.ops")
        ops.nms = fallback_nms
        tv_module.ops = ops
        sys.modules["torchvision.ops"] = ops
        _is_compatibility_ensured = True

# 模組載入時預先檢查並準備相容性環境
_ensure_torchvision_compatibility()

class InferenceEngine:
    """
    統一推論引擎，根據 model_path 自動選擇後端：
    - .onnx 結尾  → ultralytics ONNX 後端
    - .pt 結尾    → ultralytics PyTorch 後端
    - NCNN 資料夾 → ultralytics NCNN 後端（支援 float32 / int8）
    - 一般資料夾  → 自動尋找內部 *.onnx 或 *.pt 檔案載入
    """

    def __init__(self, model_path="yolov8n.pt", num_threads=4, model_format="auto"):
        _ensure_torchvision_compatibility()
        self.model_path = model_path
        self.num_threads = num_threads
        self.model_format = (model_format or "auto").lower()

        actual_model_path = model_path

        # 1. 檢查明確目錄語法是否不存在
        clean_path = str(model_path).replace("\\", "/")
        if clean_path.endswith("/") and not os.path.exists(model_path):
            raise FileNotFoundError(f"模型目錄不存在: '{model_path}'")

        if os.path.isdir(model_path):
            files = os.listdir(model_path)
            onnx_files = [f for f in files if f.lower().endswith(".onnx")]
            pt_files = [f for f in files if f.lower().endswith(".pt")]
            has_ncnn = (
                os.path.exists(os.path.join(model_path, "model.ncnn.param")) or
                os.path.exists(os.path.join(model_path, "model.ncnn.bin")) or
                any(f.endswith(".ncnn.param") or f.endswith(".ncnn.bin") for f in files)
            )

            if self.model_format == "onnx" and onnx_files:
                best_onnx = "best.onnx" if "best.onnx" in onnx_files else onnx_files[0]
                actual_model_path = os.path.join(model_path, best_onnx)
                self.model_type = "ONNX"
            elif self.model_format == "pt" and pt_files:
                best_pt = "best.pt" if "best.pt" in pt_files else pt_files[0]
                actual_model_path = os.path.join(model_path, best_pt)
                self.model_type = "PyTorch"
            elif self.model_format == "ncnn" and has_ncnn:
                self.model_type = "NCNN"
                actual_model_path = model_path
            else:
                # Auto preference: ONNX -> PyTorch -> NCNN
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
                    raise FileNotFoundError(f"模型目錄 '{model_path}' 中找不到有效的模型檔案 (.onnx, .pt 或 NCNN 模型)")
        elif model_path.lower().endswith(".onnx") or self.model_format == "onnx":
            self.model_type = "ONNX"
        else:
            self.model_type = "PyTorch"

        # 2. 若為 ONNX 模型，預先檢查 ONNX Runtime 依賴，避免觸發 AutoUpdate 導致 process 崩潰
        if getattr(self, "model_type", None) == "ONNX" or str(actual_model_path).lower().endswith(".onnx"):
            self.model_type = "ONNX"
            import sys
            has_ort = False
            if "onnxruntime" in sys.modules:
                has_ort = sys.modules["onnxruntime"] is not None
            else:
                try:
                    import importlib
                    ort = importlib.import_module("onnxruntime")
                    has_ort = ort is not None
                except (ImportError, Exception):
                    has_ort = False

            if not has_ort:
                raise RuntimeError(
                    f"環境缺少 onnxruntime 套件，無法載入 ONNX 模型 '{actual_model_path}'。"
                    "請先安裝 onnxruntime 或改用 PyTorch (.pt) / NCNN 模型。"
                )

        self.actual_model_path = actual_model_path
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

