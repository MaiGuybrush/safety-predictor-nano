import unittest
from unittest.mock import MagicMock, patch

class TestEngineCache(unittest.TestCase):
    @patch("main.StreamHandler")
    @patch("main.InferenceEngine")
    def test_engine_cache_reuse(self, mock_engine_cls, mock_stream_cls):
        from main import build_stream_units
        
        # Configure mock engine instances
        engine_a = MagicMock()
        engine_a.num_threads = 4
        engine_b = MagicMock()
        engine_b.num_threads = 4
        mock_engine_cls.side_effect = [engine_a, engine_b]
        
        stream_configs = [
            {"url": "rtsp://cam1", "model": "model1.pt", "label": "Cam1"},
            {"url": "rtsp://cam2", "model": "model1.pt", "label": "Cam2"},
            {"url": "rtsp://cam3", "model": "model2.pt", "label": "Cam3"}
        ]
        
        units, cache = build_stream_units(stream_configs, cpu_cores=4, fps_limit=5)
        
        # Should create only 2 engine instances (model1.pt and model2.pt)
        self.assertEqual(mock_engine_cls.call_count, 2)
        self.assertEqual(len(units), 3)
        self.assertEqual(units[0]["engine"], units[1]["engine"])
        self.assertNotEqual(units[0]["engine"], units[2]["engine"])
        
    @patch("main.StreamHandler")
    @patch("main.InferenceEngine")
    def test_engine_cache_reload_reuse(self, mock_engine_cls, mock_stream_cls):
        from main import build_stream_units
        
        engine_a = MagicMock()
        engine_a.num_threads = 4
        mock_engine_cls.return_value = engine_a
        
        # First load
        stream_configs = [{"url": "rtsp://cam1", "model": "model1.pt", "label": "Cam1"}]
        units, cache = build_stream_units(stream_configs, cpu_cores=4, fps_limit=5)
        self.assertEqual(mock_engine_cls.call_count, 1)
        
        # Second load with same model path and same cpu cores -> reuse engine_a
        units2, cache2 = build_stream_units(stream_configs, cpu_cores=4, fps_limit=5, existing_engine_cache=cache)
        self.assertEqual(mock_engine_cls.call_count, 1) # Still 1!
        self.assertEqual(units2[0]["engine"], engine_a)

    @patch("main.StreamHandler")
    @patch("main.InferenceEngine")
    def test_engine_cache_tuple_key_model_info_formatting(self, mock_engine_cls, mock_stream_cls):
        import web_ui
        from main import build_stream_units, update_rtsp_model_info

        engine_a = MagicMock()
        engine_a.model_type = "ONNX"
        engine_a.num_threads = 4
        mock_engine_cls.return_value = engine_a

        stream_configs = [
            {"url": "rtsp://cam1", "model": "models/model1.onnx", "model_format": "auto", "label": "Cam1"},
            {"url": "rtsp://cam2", "model": "models/model2.pt", "model_format": "pt", "label": "Cam2"}
        ]
        units, cache = build_stream_units(stream_configs, cpu_cores=4, fps_limit=5)
        self.assertIn(("models/model1.onnx", "auto"), cache)
        self.assertIn(("models/model2.pt", "pt"), cache)

        # Call production helper update_rtsp_model_info
        update_rtsp_model_info(units, cache, cpu_cores=4)
        self.assertEqual(web_ui.MODEL_INFO["path"], "models/model1.onnx, models/model2.pt")
        self.assertEqual(web_ui.MODEL_INFO["type"], "ONNX")


if __name__ == "__main__":
    unittest.main()
