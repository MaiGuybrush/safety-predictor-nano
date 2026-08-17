import unittest
from unittest.mock import MagicMock, patch


class TestInferenceEngineLabel(unittest.TestCase):
    @patch("inference_engine.YOLO")
    def test_infer_attaches_label_from_model_names(self, mock_yolo_cls):
        from inference_engine import InferenceEngine

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

    @patch("inference_engine.YOLO")
    def test_infer_falls_back_to_class_id_string_when_unmapped(self, mock_yolo_cls):
        from inference_engine import InferenceEngine

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

    @patch("inference_engine.YOLO")
    def test_directory_with_pt_resolves_to_pt_file(self, mock_yolo_cls):
        import tempfile
        import os
        from inference_engine import InferenceEngine

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

    @patch("inference_engine.YOLO")
    def test_directory_with_onnx_resolves_to_onnx_file(self, mock_yolo_cls):
        import tempfile
        import os
        from inference_engine import InferenceEngine

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

    @patch("inference_engine.YOLO")
    def test_directory_with_ncnn_resolves_to_ncnn_directory(self, mock_yolo_cls):
        import tempfile
        import os
        from inference_engine import InferenceEngine

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


    @patch("inference_engine.YOLO")
    def test_explicit_format_pt_overrides_onnx_in_directory(self, mock_yolo_cls):
        import tempfile
        import os
        from inference_engine import InferenceEngine

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

    @patch("inference_engine.YOLO")
    def test_explicit_format_onnx_selects_onnx(self, mock_yolo_cls):
        import tempfile
        import os
        from inference_engine import InferenceEngine

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


if __name__ == "__main__":
    unittest.main()
