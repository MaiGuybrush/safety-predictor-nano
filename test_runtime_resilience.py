import unittest
from unittest.mock import patch, MagicMock
from config_manager import ConfigManager
from main import initialize_runtime, build_stream_units
import os
import tempfile
import yaml

class TestRuntimeResilience(unittest.TestCase):
    def setUp(self):
        fd, self.tmp_path = tempfile.mkstemp(suffix=".yaml")
        os.close(fd)

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            os.remove(self.tmp_path)

    def write_yaml(self, data):
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

    @patch("main.setup_system_logger")
    @patch("main.VideoHandler")
    @patch("main.InferenceEngine")
    def test_initialize_runtime_video_mode_model_failure_fallback(self, mock_engine_cls, mock_video_handler, mock_sys_logger):
        # 模擬首次載入使用者設定之模型時失敗（如 FileNotFoundError），fallback 載入 yolov8n.pt 成功
        def engine_side_effect(*args, **kwargs):
            model_path = kwargs.get("model_path") or (args[0] if args else None)
            if model_path == "models/person_detector/":
                raise FileNotFoundError("模型目錄不存在: 'models/person_detector/'")
            mock_inst = MagicMock()
            mock_inst.model_type = "PyTorch"
            mock_inst.actual_model_path = "yolov8n.pt"
            return mock_inst

        mock_engine_cls.side_effect = engine_side_effect

        data = {
            "mode": "video",
            "video_path": "/home/pi/Downloads/Profile1_20260828_103117.avi",
            "model_path": "models/person_detector/",
            "model_format": "auto",
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)

        # 呼叫 initialize_runtime 絕不可拋出 FileNotFoundError 或崩潰
        state = initialize_runtime(mgr)
        self.assertIsNotNone(state)
        self.assertEqual(state["mode"], "video")
        self.assertIsNotNone(state["video_engine"])

    @patch("main.InferenceEngine")
    def test_build_stream_units_model_failure_fallback(self, mock_engine_cls):
        def engine_side_effect(*args, **kwargs):
            model_path = kwargs.get("model_path") or (args[0] if args else None)
            if model_path == "invalid_model.onnx":
                raise RuntimeError("環境缺少 onnxruntime 套件")
            mock_inst = MagicMock()
            mock_inst.model_type = "PyTorch"
            mock_inst.actual_model_path = "yolov8n.pt"
            return mock_inst

        mock_engine_cls.side_effect = engine_side_effect

        stream_configs = [
            {"url": "rtsp://127.0.0.1:8554/cam1", "model": "invalid_model.onnx", "label": "Cam1", "camera_id": "cam1"}
        ]
        stream_units, engine_cache = build_stream_units(stream_configs, cpu_cores=4, fps_limit=5)
        self.assertEqual(len(stream_units), 1)
        self.assertIsNotNone(stream_units[0]["engine"])

    @patch("main.setup_system_logger")
    @patch("main.VideoHandler")
    @patch("main.InferenceEngine")
    def test_initialize_runtime_resolves_clean_video_camera_id(self, mock_engine_cls, mock_video_handler, mock_sys_logger):
        mock_inst = MagicMock()
        mock_inst.model_type = "PyTorch"
        mock_inst.actual_model_path = "yolov8n.pt"
        mock_engine_cls.return_value = mock_inst

        data = {
            "mode": "video",
            "video_path": "/home/pi/Downloads/Profile1_20260828_103117.avi",
            "model_path": "yolov8n.pt"
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)

        state = initialize_runtime(mgr)
        import web_ui
        stream_info = web_ui.MODEL_INFO["streams"][0]
        self.assertEqual(stream_info["camera_id"], "simu-Profile1_20260828_103117")
        self.assertNotIn("/", stream_info["camera_id"])


if __name__ == "__main__":
    unittest.main()
