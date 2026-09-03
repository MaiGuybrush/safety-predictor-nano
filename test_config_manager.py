import unittest
import unittest.mock
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


    def test_streams_with_str_urls(self):
        data = {
            "model_path": "global.pt",
            "streams": ["rtsp://cam1", "  ", "rtsp://127.0.0.1:8554/cam-0eb40kwvs74z"]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        configs = mgr.get_stream_configs()
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0], {"url": "rtsp://cam1", "model": "global.pt", "label": "", "camera_id": "stream0"})
        self.assertEqual(configs[1], {"url": "rtsp://127.0.0.1:8554/cam-0eb40kwvs74z", "model": "global.pt", "label": "", "camera_id": "cam-0eb40kwvs74z"})

    def test_new_streams_schema(self):
        data = {
            "model_path": "global.pt",
            "streams": [
                {"url": "rtsp://cam1", "model": "custom.pt", "label": "Cam 1", "camera_id": "CCD1"},
                {"url": "rtsp://cam2", "label": "Cam 2"},
                {"url": "http://10.54.10.140:8080/api/stream?src=cam-999"},
                {"url": ""},
            ]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        configs = mgr.get_stream_configs()
        self.assertEqual(len(configs), 3)
        self.assertEqual(configs[0], {"url": "rtsp://cam1", "model": "custom.pt", "label": "Cam 1", "camera_id": "CCD1"})
        self.assertEqual(configs[1], {"url": "rtsp://cam2", "model": "global.pt", "label": "Cam 2", "camera_id": "Cam 2"})
        self.assertEqual(configs[2], {"url": "http://10.54.10.140:8080/api/stream?src=cam-999", "model": "global.pt", "label": "", "camera_id": "cam-999"})

    def test_camera_id_resolution_priority(self):
        # 1. Explicit camera_id wins even if URL has cam-
        data1 = {
            "streams": [{"url": "rtsp://127.0.0.1/cam-from-url", "camera_id": "explicit_cam", "label": "my_label"}]
        }
        self.write_yaml(data1)
        mgr1 = ConfigManager(self.tmp_path)
        self.assertEqual(mgr1.get_stream_configs()[0]["camera_id"], "explicit_cam")

        # 2. URL cam- wins over label if no explicit camera_id
        data2 = {
            "streams": [{"url": "rtsp://127.0.0.1/cam-from-url", "label": "my_label"}]
        }
        self.write_yaml(data2)
        mgr2 = ConfigManager(self.tmp_path)
        self.assertEqual(mgr2.get_stream_configs()[0]["camera_id"], "cam-from-url")

        # 3. Label wins over stream{idx} if URL has no cam-
        data3 = {
            "streams": [{"url": "rtsp://127.0.0.1/normal_stream", "label": "my_label"}]
        }
        self.write_yaml(data3)
        mgr3 = ConfigManager(self.tmp_path)
        self.assertEqual(mgr3.get_stream_configs()[0]["camera_id"], "my_label")

        # 4. Fallback to stream{idx}
        data4 = {
            "streams": [{"url": "rtsp://127.0.0.1/normal_stream"}]
        }
        self.write_yaml(data4)
        mgr4 = ConfigManager(self.tmp_path)
        self.assertEqual(mgr4.get_stream_configs()[0]["camera_id"], "stream0")

    def test_streams_no_ums_targets(self):
        data = {
            "model_path": "global.pt",
            "streams": ["rtsp://cam1"]
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

    def test_get_zones_empty_by_default(self):
        data = {"model_path": "global.pt"}
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        self.assertEqual(mgr.get_zones(), {})
        self.assertIsNone(mgr.get_zone("rtsp://cam1"))

    def test_save_and_get_zone(self):
        data = {
            "model_path": "global.pt",
            "cpu_cores": 4,
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        poly = [[0.1, 0.2], [0.5, 0.2], [0.5, 0.8], [0.1, 0.8]]
        mgr.save_zone("rtsp://cam1", poly, "機台危險區", trigger_mode="intersect", sensitivity=0.25)

        # In-memory check
        self.assertEqual(mgr.get_zone("rtsp://cam1"), {
            "polygon": poly,
            "zone_name": "機台危險區",
            "trigger_mode": "intersect",
            "sensitivity": 0.25
        })

        # On-disk check
        with open(self.tmp_path, "r", encoding="utf-8") as f:
            on_disk = yaml.safe_load(f)
        self.assertEqual(on_disk["zones"]["rtsp://cam1"]["polygon"], poly)
        self.assertEqual(on_disk["zones"]["rtsp://cam1"]["zone_name"], "機台危險區")
        self.assertEqual(on_disk["zones"]["rtsp://cam1"]["trigger_mode"], "intersect")
        self.assertEqual(on_disk["zones"]["rtsp://cam1"]["sensitivity"], 0.25)
        self.assertEqual(on_disk["cpu_cores"], 4)

    def test_delete_zone(self):
        data = {
            "zones": {
                "rtsp://cam1": {
                    "polygon": [[0.1, 0.1], [0.5, 0.5], [0.1, 0.5]],
                    "zone_name": "Zone A"
                }
            }
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        mgr.delete_zone("rtsp://cam1")
        self.assertIsNone(mgr.get_zone("rtsp://cam1"))

        with open(self.tmp_path, "r", encoding="utf-8") as f:
            on_disk = yaml.safe_load(f)
        self.assertNotIn("rtsp://cam1", on_disk.get("zones", {}))

    def test_save_zone_empty_polygon_clears_zone(self):
        data = {
            "zones": {
                "rtsp://cam1": {
                    "polygon": [[0.1, 0.1], [0.5, 0.5], [0.1, 0.5]],
                }
            }
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        mgr.save_zone("rtsp://cam1", [])
        self.assertIsNone(mgr.get_zone("rtsp://cam1"))

    def test_stream_model_format_parsing(self):
        data = {
            "model_format": "onnx",
            "streams": [
                {"url": "rtsp://cam1", "model_format": "pt"},
                {"url": "rtsp://cam2"},
            ]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        configs = mgr.get_stream_configs()
        self.assertEqual(configs[0]["model_format"], "pt")
        self.assertEqual(configs[1]["model_format"], "onnx")

    def test_ums_targets_with_format(self):
        data = {
            "ums_model": {"name": "global-model", "format": "onnx"},
            "streams": [
                {"url": "rtsp://cam1", "ums_model": {"name": "cam1-model", "format": "pt"}},
            ]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        targets = mgr.get_ums_targets()
        self.assertEqual(targets[0]["format"], "onnx")
        self.assertEqual(targets[1]["format"], "pt")

    def test_check_for_updates_with_empty_file(self):
        data = {"model_path": "global.pt"}
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        
        # Simulate empty file write (0 bytes)
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            f.write("")
        os.utime(self.tmp_path, (os.path.getatime(self.tmp_path) + 10, os.path.getmtime(self.tmp_path) + 10))
        
        updated = mgr.check_for_updates()
        self.assertFalse(updated)
        self.assertIsNotNone(mgr.config)
        self.assertIsInstance(mgr.config, dict)

    def test_get_ums_base_urls_from_list(self):
        data = {
            "ums_base_urls": [
                "http://10.26.11.108/umsapiproxy/fab4ums",
                "http://10.26.11.109/umsapiproxy/fab4ums"
            ]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            urls = mgr.get_ums_base_urls()
            self.assertEqual(urls, [
                "http://10.26.11.108/umsapiproxy/fab4ums",
                "http://10.26.11.109/umsapiproxy/fab4ums"
            ])

    def test_get_ums_base_urls_from_legacy_single_string(self):
        data = {
            "ums_base_url": "http://legacy.ums/fab4ums"
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            urls = mgr.get_ums_base_urls()
            self.assertEqual(urls, ["http://legacy.ums/fab4ums"])

    def test_get_ums_base_urls_from_env_var_comma_separated(self):
        data = {
            "ums_base_urls": ["http://config.ums/fab4ums"]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        with unittest.mock.patch.dict("os.environ", {"UMS_BASE_URL": "http://env1.ums, http://env2.ums"}):
            urls = mgr.get_ums_base_urls()
            self.assertEqual(urls, ["http://env1.ums", "http://env2.ums"])

    def test_get_ums_base_urls_fallback_defaults(self):
        data = {}
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            urls = mgr.get_ums_base_urls()
            self.assertEqual(len(urls), 2)
            self.assertIn("tncimweb1.cminl.oa", urls[0])
            self.assertIn("tncimweb2.cminl.oa", urls[1])

    def test_get_ppe_class_mapping_default(self):
        data = {}
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        mapping = mgr.get_ppe_class_mapping()
        self.assertEqual(mapping["person"], "person")
        self.assertEqual(mapping["helmet"], "helmet")
        self.assertEqual(mapping["vest"], "vest")
        self.assertEqual(mapping["cone"], "cone")

    def test_get_ppe_class_mapping_custom_override(self):
        data = {
            "ppe_class_mapping": {
                "hard_hat": "helmet",
                "safety_vest": "vest",
                "person": "human",
            }
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        mapping = mgr.get_ppe_class_mapping()
        self.assertEqual(mapping["hard_hat"], "helmet")
        self.assertEqual(mapping["safety_vest"], "vest")
        self.assertEqual(mapping["person"], "human")
        self.assertEqual(mapping["cone"], "cone")  # Base mapping preserved

    def test_get_external_states_empty(self):
        data = {}
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        self.assertEqual(mgr.get_external_states(), {})

    def test_get_external_states_parsing_and_normalization(self):
        data = {
            "external_states": {
                "stocker_01": {
                    "url": "http://mes-api/status",
                    "method": "get",
                    "interval_seconds": 10,
                    "json_path": "data.status",
                    "timeout_seconds": 3,
                    "fallback_value": "UNKNOWN",
                },
                "invalid_entry": "not-a-dict"
            }
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        states = mgr.get_external_states()
        self.assertIn("stocker_01", states)
        self.assertNotIn("invalid_entry", states)
        self.assertEqual(states["stocker_01"]["method"], "GET")
        self.assertEqual(states["stocker_01"]["interval_seconds"], 10)
        self.assertEqual(states["stocker_01"]["timeout_seconds"], 3)
        self.assertEqual(states["stocker_01"]["fallback_value"], "UNKNOWN")

    def test_get_compliance_rules_filtering(self):
        data = {
            "compliance_rules": [
                {
                    "id": "rule_1",
                    "enabled": True,
                    "when": {"zone": "ZoneA"},
                    "require_ppe": ["helmet"],
                },
                {
                    "id": "rule_2",
                    "enabled": False,
                    "when": {"zone": "ZoneB"},
                },
                "not-a-rule-dict"
            ]
        }
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        rules = mgr.get_compliance_rules()
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], "rule_1")

    def test_save_zone_with_ppe_strategy_and_required_ppe(self):
        data = {"model_path": "global.pt"}
        self.write_yaml(data)
        mgr = ConfigManager(self.tmp_path)
        poly = [[0.1, 0.2], [0.5, 0.2], [0.5, 0.8], [0.1, 0.8]]
        mgr.save_zone(
            "rtsp://cam1",
            poly,
            "機台危險區",
            trigger_mode="intersect",
            sensitivity=0.25,
            ppe_strategy="head_anchor",
            required_ppe=["helmet", "vest"]
        )

        zone = mgr.get_zone("rtsp://cam1")
        self.assertEqual(zone["ppe_strategy"], "head_anchor")
        self.assertEqual(zone["required_ppe"], ["helmet", "vest"])
        self.assertEqual(zone["trigger_mode"], "intersect")
        self.assertEqual(zone["sensitivity"], 0.25)

if __name__ == "__main__":
    unittest.main()


