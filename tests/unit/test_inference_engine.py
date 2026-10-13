import unittest
from unittest.mock import MagicMock, patch


class TestInferenceEngineLabel(unittest.TestCase):
    @patch("argus.vision.inference_engine.YOLO")
    def test_infer_attaches_label_from_model_names(self, mock_yolo_cls):
        from argus.vision.inference_engine import InferenceEngine

        box = MagicMock()
        box.cls = 0
        box.conf = 0.9
        box.xyxy.tolist.return_value = [[1.0, 2.0, 3.0, 4.0]]

        result = MagicMock()
        result.names = {0: "no_helmet"}
        result.boxes = [box]

        mock_model = MagicMock()
        mock_model.predict.return_value = [result]
        mock_yolo_cls.return_value = mock_model

        engine = InferenceEngine(model_path="dummy.pt", num_threads=1)
        detections, _ = engine.infer(object(), conf_threshold=0.25)

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["label"], "no_helmet")
        self.assertEqual(detections[0]["cls"], 0)

    @patch("argus.vision.inference_engine.YOLO")
    def test_infer_falls_back_to_class_id_string_when_unmapped(self, mock_yolo_cls):
        from argus.vision.inference_engine import InferenceEngine

        box = MagicMock()
        box.cls = 7
        box.conf = 0.5
        box.xyxy.tolist.return_value = [[0.0, 0.0, 1.0, 1.0]]

        result = MagicMock()
        result.names = {}
        result.boxes = [box]

        mock_model = MagicMock()
        mock_model.predict.return_value = [result]
        mock_yolo_cls.return_value = mock_model

        engine = InferenceEngine(model_path="dummy.pt", num_threads=1)
        detections, _ = engine.infer(object(), conf_threshold=0.25)

        self.assertEqual(detections[0]["label"], "7")

    @patch("argus.vision.inference_engine.YOLO")
    def test_directory_with_pt_resolves_to_pt_file(self, mock_yolo_cls):
        import tempfile
        import os
        from argus.vision.inference_engine import InferenceEngine

        tmp_dir = tempfile.mkdtemp()
        try:
            pt_file = os.path.join(tmp_dir, "best.pt")
            open(pt_file, "w").close()

            engine = InferenceEngine(model_path=tmp_dir, num_threads=1)
            self.assertEqual(engine.model_type, "PyTorch")
            mock_yolo_cls.assert_called_with(pt_file)
        finally:
            if os.path.exists(tmp_dir):
                import shutil
                shutil.rmtree(tmp_dir)

    @patch("argus.vision.inference_engine.YOLO")
    def test_directory_with_onnx_resolves_to_onnx_file(self, mock_yolo_cls):
        import tempfile
        import os
        from argus.vision.inference_engine import InferenceEngine

        tmp_dir = tempfile.mkdtemp()
        try:
            onnx_file = os.path.join(tmp_dir, "best.onnx")
            open(onnx_file, "w").close()
            pt_file = os.path.join(tmp_dir, "best.pt")
            open(pt_file, "w").close()

            engine = InferenceEngine(model_path=tmp_dir, num_threads=1)
            self.assertEqual(engine.model_type, "ONNX")
            mock_yolo_cls.assert_called_with(onnx_file)
        finally:
            if os.path.exists(tmp_dir):
                import shutil
                shutil.rmtree(tmp_dir)

    @patch("argus.vision.inference_engine.YOLO")
    def test_directory_with_ncnn_resolves_to_ncnn_directory(self, mock_yolo_cls):
        import tempfile
        import os
        from argus.vision.inference_engine import InferenceEngine

        tmp_dir = tempfile.mkdtemp()
        try:
            param_file = os.path.join(tmp_dir, "model.ncnn.param")
            open(param_file, "w").close()

            engine = InferenceEngine(model_path=tmp_dir, num_threads=1)
            self.assertEqual(engine.model_type, "NCNN")
            mock_yolo_cls.assert_called_with(tmp_dir)
        finally:
            if os.path.exists(tmp_dir):
                import shutil
                shutil.rmtree(tmp_dir)


    @patch("argus.vision.inference_engine.YOLO")
    def test_explicit_format_pt_overrides_onnx_in_directory(self, mock_yolo_cls):
        import tempfile
        import os
        from argus.vision.inference_engine import InferenceEngine

        tmp_dir = tempfile.mkdtemp()
        try:
            onnx_file = os.path.join(tmp_dir, "best.onnx")
            open(onnx_file, "w").close()
            pt_file = os.path.join(tmp_dir, "best.pt")
            open(pt_file, "w").close()

            engine = InferenceEngine(model_path=tmp_dir, num_threads=1, model_format="pt")
            self.assertEqual(engine.model_type, "PyTorch")
            mock_yolo_cls.assert_called_with(pt_file)
        finally:
            if os.path.exists(tmp_dir):
                import shutil
                shutil.rmtree(tmp_dir)

    @patch("argus.vision.inference_engine.YOLO")
    def test_explicit_format_onnx_selects_onnx(self, mock_yolo_cls):
        import tempfile
        import os
        from argus.vision.inference_engine import InferenceEngine

        tmp_dir = tempfile.mkdtemp()
        try:
            onnx_file = os.path.join(tmp_dir, "best.onnx")
            open(onnx_file, "w").close()
            pt_file = os.path.join(tmp_dir, "best.pt")
            open(pt_file, "w").close()

            engine = InferenceEngine(model_path=tmp_dir, num_threads=1, model_format="onnx")
            self.assertEqual(engine.model_type, "ONNX")
            mock_yolo_cls.assert_called_with(onnx_file)
        finally:
            if os.path.exists(tmp_dir):
                import shutil
                shutil.rmtree(tmp_dir)

    def test_nonexistent_directory_raises_filenotfounderror(self):
        from argus.vision.inference_engine import InferenceEngine
        # Models with trailing slash or nonexistent paths should fail fast with FileNotFoundError
        with self.assertRaises(FileNotFoundError) as ctx:
            InferenceEngine(model_path="models/person_detector/", num_threads=1)
        self.assertIn("不存在", str(ctx.exception))

    def test_empty_directory_raises_filenotfounderror(self):
        import tempfile
        import os
        from argus.vision.inference_engine import InferenceEngine

        tmp_dir = tempfile.mkdtemp()
        try:
            with self.assertRaises(FileNotFoundError) as ctx:
                InferenceEngine(model_path=tmp_dir, num_threads=1)
            self.assertIn("找不到有效的模型檔案", str(ctx.exception))
        finally:
            if os.path.exists(tmp_dir):
                import shutil
                shutil.rmtree(tmp_dir)

    def test_onnx_without_onnxruntime_raises_runtimeerror(self):
        import tempfile
        import os
        import sys
        from unittest.mock import patch
        from argus.vision.inference_engine import InferenceEngine

        tmp_dir = tempfile.mkdtemp()
        try:
            onnx_file = os.path.join(tmp_dir, "test.onnx")
            open(onnx_file, "w").close()

            with patch.dict(sys.modules, {"onnxruntime": None}):
                with self.assertRaises(RuntimeError) as ctx:
                    InferenceEngine(model_path=onnx_file, num_threads=1)
                self.assertIn("onnxruntime", str(ctx.exception))
        finally:
            if os.path.exists(tmp_dir):
                import shutil
                shutil.rmtree(tmp_dir)

    def test_torchvision_nms_fallback_when_operator_missing(self):
        import sys
        import types
        import torch
        from argus.vision.inference_engine import _ensure_torchvision_compatibility

        # 模擬破壞性的 torchvision 模組（C++ operator 遺失且無 ops 屬性，驗證 hasattr 缺失處理）
        broken_tv = types.ModuleType("torchvision")

        orig_tv = sys.modules.get("torchvision")
        orig_ops = sys.modules.get("torchvision.ops")
        try:
            sys.modules["torchvision"] = broken_tv
            sys.modules.pop("torchvision.ops", None)

            # 強制觸發檢查
            _ensure_torchvision_compatibility(force=True)

            import torchvision
            self.assertTrue(hasattr(torchvision, "ops"))
            self.assertTrue(hasattr(torchvision.ops, "nms"))

            boxes = torch.tensor([[0.0, 0.0, 10.0, 10.0], [1.0, 1.0, 9.0, 9.0]], dtype=torch.float32)
            scores = torch.tensor([0.9, 0.8], dtype=torch.float32)
            keep = torchvision.ops.nms(boxes, scores, 0.5)
            self.assertTrue(len(keep) > 0)
        finally:
            if orig_tv is not None:
                sys.modules["torchvision"] = orig_tv
            else:
                sys.modules.pop("torchvision", None)
            if orig_ops is not None:
                sys.modules["torchvision.ops"] = orig_ops
            else:
                sys.modules.pop("torchvision.ops", None)

    @patch("argus.vision.inference_engine.YOLO")
    def test_inference_engine_lifecycle_with_broken_torchvision(self, mock_yolo_cls):
        import sys
        import types
        import numpy as np
        from argus.vision.inference_engine import InferenceEngine, _ensure_torchvision_compatibility

        # 模擬呼叫時拋出 operator torchvision::nms does not exist 的情境
        broken_tv = types.ModuleType("torchvision")
        broken_ops = types.ModuleType("torchvision.ops")
        def broken_nms(*args, **kwargs):
            raise RuntimeError("operator torchvision::nms does not exist")
        broken_ops.nms = broken_nms
        broken_tv.ops = broken_ops

        orig_tv = sys.modules.get("torchvision")
        orig_ops = sys.modules.get("torchvision.ops")
        try:
            sys.modules["torchvision"] = broken_tv
            sys.modules["torchvision.ops"] = broken_ops

            # 重設快取並強制修正
            _ensure_torchvision_compatibility(force=True)

            box = MagicMock()
            box.cls = 0
            box.conf = 0.95
            box.xyxy.tolist.return_value = [[10.0, 10.0, 50.0, 50.0]]
            res = MagicMock()
            res.names = {0: "person"}
            res.boxes = [box]
            mock_model = MagicMock()
            mock_model.predict.return_value = [res]
            mock_yolo_cls.return_value = mock_model

            engine = InferenceEngine(model_path="dummy.pt", num_threads=1)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            detections, inf_time = engine.infer(frame, conf_threshold=0.25)

            self.assertEqual(len(detections), 1)
            self.assertEqual(detections[0]["label"], "person")
            self.assertGreaterEqual(inf_time, 0)
        finally:
            if orig_tv is not None:
                sys.modules["torchvision"] = orig_tv
            else:
                sys.modules.pop("torchvision", None)
            if orig_ops is not None:
                sys.modules["torchvision.ops"] = orig_ops
            else:
                sys.modules.pop("torchvision.ops", None)


if __name__ == "__main__":
    unittest.main()


