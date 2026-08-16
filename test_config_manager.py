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
        self.assertEqual(configs[0], {"url": "rtsp://cam1", "model": "global.pt", "label": "", "camera_id": ""})
        self.assertEqual(configs[1], {"url": "rtsp://cam2", "model": "global.pt", "label": "", "camera_id": ""})

    def test_new_streams_schema(self):
        data = {
            "model_path": "global.pt",
            "streams": [
                {"url": "rtsp://cam1", "model": "custom.pt", "label": "Cam 1", "camera_id": "CCD1"},
                {"url": "rtsp://cam2", "label": "Cam 2"},
                {"url": ""},
            ]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        configs = mgr.get_stream_configs()
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0], {"url": "rtsp://cam1", "model": "custom.pt", "label": "Cam 1", "camera_id": "CCD1"})
        self.assertEqual(configs[1], {"url": "rtsp://cam2", "model": "global.pt", "label": "Cam 2", "camera_id": ""})

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

    def test_legacy_rtsp_streams_no_ums_targets(self):
        data = {
            "model_path": "global.pt",
            "rtsp_streams": ["rtsp://cam1"]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        self.assertEqual(mgr.get_ums_targets(), [])

    def test_ums_targets_global_and_per_stream(self):
        data = {
            "model_path": "global.pt",
            "ums_model": {"name": "global-model"},
            "streams": [
                {"url": "rtsp://cam1", "ums_model": {"name": "cam1-model", "version": 3}},
                {"url": "rtsp://cam2", "model": "custom.pt"},
            ]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        targets = mgr.get_ums_targets()
        self.assertEqual(targets, [
            {"key": "model_path", "name": "global-model", "version": "latest"},
            {"key": "streams[0].model", "name": "cam1-model", "version": 3},
        ])

    def test_update_model_paths_preserves_other_fields(self):
        data = {
            "model_path": "global.pt",
            "ums_model": {"name": "global-model"},
            "cpu_cores": 4,
            "streams": [
                {"url": "rtsp://cam1", "ums_model": {"name": "cam1-model"}, "label": "Cam 1"},
            ]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        before_mtime = mgr.last_mtime

        mgr.update_model_paths({
            "model_path": "models/global-model/v2/global-model.pt",
            "streams[0].model": "models/cam1-model/v1",
        })

        with open(self.tmp_path, "r", encoding="utf-8") as f:
            on_disk = yaml.safe_load(f)

        self.assertEqual(on_disk["model_path"], "models/global-model/v2/global-model.pt")
        self.assertEqual(on_disk["streams"][0]["model"], "models/cam1-model/v1")
        # Untouched fields survive
        self.assertEqual(on_disk["cpu_cores"], 4)
        self.assertEqual(on_disk["ums_model"], {"name": "global-model"})
        self.assertEqual(on_disk["streams"][0]["label"], "Cam 1")
        self.assertEqual(on_disk["streams"][0]["ums_model"], {"name": "cam1-model"})
        # In-memory config and mtime refreshed
        self.assertEqual(mgr.config["model_path"], "models/global-model/v2/global-model.pt")
        self.assertGreaterEqual(mgr.last_mtime, before_mtime)

if __name__ == "__main__":
    unittest.main()
