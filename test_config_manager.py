import unittest
import os
import yaml
import tempfile
from config_manager import ConfigManager

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        fd, self.tmp_path = tempfile.mkstemp(suffix=".yaml")
        os.close(fd)
    
    def tearDown(self):
        if os.path.exists(self.tmp_path):
            os.remove(self.tmp_path)

    def write_yaml(self, data):
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)


    def test_legacy_rtsp_streams(self):
        data = {
            "model_path": "global.pt",
            "rtsp_streams": ["rtsp://cam1", "  ", "rtsp://cam2"]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        configs = mgr.get_stream_configs()
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0], {"url": "rtsp://cam1", "model": "global.pt", "label": ""})
        self.assertEqual(configs[1], {"url": "rtsp://cam2", "model": "global.pt", "label": ""})

    def test_new_streams_schema(self):
        data = {
            "model_path": "global.pt",
            "streams": [
                {"url": "rtsp://cam1", "model": "custom.pt", "label": "Cam 1"},
                {"url": "rtsp://cam2", "label": "Cam 2"},
                {"url": ""},
            ]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        configs = mgr.get_stream_configs()
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0], {"url": "rtsp://cam1", "model": "custom.pt", "label": "Cam 1"})
        self.assertEqual(configs[1], {"url": "rtsp://cam2", "model": "global.pt", "label": "Cam 2"})

    def test_streams_precedence_over_rtsp_streams(self):
        data = {
            "model_path": "global.pt",
            "streams": [{"url": "rtsp://new_cam"}],
            "rtsp_streams": ["rtsp://old_cam"]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)

        configs = mgr.get_stream_configs()
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]["url"], "rtsp://new_cam")

if __name__ == "__main__":
    unittest.main()
