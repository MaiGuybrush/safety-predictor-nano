import unittest
import os
import sys
import tempfile
import json
from unittest.mock import patch, MagicMock

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import web_ui
from inference_engine import InferenceEngine



class TestNCNNInferenceEngine(unittest.TestCase):
    @patch("inference_engine.YOLO")
    def test_pytorch_model_detection(self, mock_yolo):
        """測試當 model_path 為 .pt 檔案時，model_type 正確設為 PyTorch"""
        mock_yolo.return_value = MagicMock()
        engine = InferenceEngine(model_path="best.pt", num_threads=4)
        
        self.assertEqual(engine.model_type, "PyTorch")
        self.assertEqual(engine.model_path, "best.pt")
        self.assertEqual(engine.num_threads, 4)
        mock_yolo.assert_called_once_with("best.pt")

    @patch("inference_engine.YOLO")
    def test_ncnn_model_detection(self, mock_yolo):
        """測試當 model_path 為資料夾時，model_type 正確設為 NCNN"""
        mock_yolo.return_value = MagicMock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            engine = InferenceEngine(model_path=tmp_dir, num_threads=8)
            
            self.assertEqual(engine.model_type, "NCNN")
            self.assertEqual(engine.model_path, tmp_dir)
            self.assertEqual(engine.num_threads, 8)
            mock_yolo.assert_called_once_with(tmp_dir)

    @patch("inference_engine.YOLO")
    def test_infer_output_format(self, mock_yolo):
        """測試 infer() 輸出的 detections 與 inference_time 格式"""
        mock_model = MagicMock()
        # 模擬 YOLO predict 傳回結果
        mock_box = MagicMock()
        mock_box.cls = 0
        mock_box.conf = 0.95
        mock_box.xyxy.tolist.return_value = [[10.0, 20.0, 100.0, 200.0]]
        
        mock_result = MagicMock()
        mock_result.boxes = [mock_box]
        mock_model.predict.return_value = [mock_result]
        mock_yolo.return_value = mock_model
        
        engine = InferenceEngine(model_path="best.pt")
        mock_frame = MagicMock()
        
        detections, inf_time = engine.infer(mock_frame, conf_threshold=0.5)
        
        self.assertIsInstance(detections, list)
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["cls"], 0)
        self.assertEqual(detections[0]["conf"], 0.95)
        self.assertEqual(detections[0]["xyxy"], [[10.0, 20.0, 100.0, 200.0]])
        self.assertGreaterEqual(inf_time, 0.0)


class TestWebUIModelInfo(unittest.TestCase):
    def setUp(self):
        web_ui.app.config["TESTING"] = True
        self.client = web_ui.app.test_client()

    def test_model_info_endpoint(self):
        """測試 /model_info API 正確回傳 MODEL_INFO JSON"""
        web_ui.MODEL_INFO = {
            "type": "NCNN",
            "path": "best_ncnn_model",
            "cpu_cores": 4
        }
        
        response = self.client.get("/model_info")
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data["type"], "NCNN")
        self.assertEqual(data["path"], "best_ncnn_model")
        self.assertEqual(data["cpu_cores"], 4)


if __name__ == "__main__":
    unittest.main()
