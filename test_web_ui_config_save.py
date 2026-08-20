import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import yaml

import web_ui


class TestWebUiConfigSave(unittest.TestCase):
    def setUp(self):
        web_ui.app.config['TESTING'] = True
        self.client = web_ui.app.test_client()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "config.yaml")
        web_ui.CONFIG_FILE = self.config_path

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_yaml(self, data):
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)

    def read_yaml(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @patch("web_ui.threading.Thread")
    def test_save_structured_streams_and_ums_model(self, mock_thread_cls):
        initial = {
            "mode": "rtsp",
            "model_path": "best.onnx",
            "streams": [
                {"url": "rtsp://127.0.0.1:8554/stream1", "label": "舊大門", "camera_id": "cam-01"}
            ],
            "fps_limit": 2,
            "cpu_cores": 4,
            "conf_threshold": 0.25,
            "log_interval_seconds": 60,
            "log_file": "perf.log",
            "detection_log_file": "det.log",
            "event_severity": {"person": "HIGH"},
            "zones": {"rtsp://127.0.0.1:8554/stream1": {"polygon": [[0, 0], [1, 1], [0, 1]]}}
        }
        self.write_yaml(initial)

        streams_payload = [
            {"url": "rtsp://127.0.0.1:8554/stream1", "label": "新大門", "camera_id": "cam-01", "model": "best.onnx"},
            {"url": "rtsp://127.0.0.1:8554/stream2", "label": "側門", "camera_id": "cam-02", "ums_model": {"name": "yolo8s", "version": "latest"}}
        ]

        form_data = {
            "mode": "rtsp",
            "model_source": "ums",
            "model_path": "best.onnx",
            "ums_model_name": "yolo8n",
            "ums_model_version": "latest",
            "streams_json": json.dumps(streams_payload),
            "fps_limit": "5",
            "cpu_cores": "4",
            "conf_threshold": "0.3",
            "log_interval_seconds": "30",
            "log_file": "perf.log",
            "detection_log_file": "det.log",
            "ums_base_url": "http://ums.example.com",
            "ums_api_key": "new_key_123",
            "heartbeat_enabled": "true",
            "heartbeat_agent_port": "8080",
            "heartbeat_interval_seconds": "60",
            "heartbeat_ap_name": "SafetyNano",
            "heartbeat_version": "0.1.0",
            "event_absence_tolerance": "3"
        }

        response = self.client.post('/', data=form_data)
        self.assertEqual(response.status_code, 200)

        saved = self.read_yaml()
        # Verify streams
        self.assertEqual(len(saved["streams"]), 2)
        self.assertEqual(saved["streams"][0]["label"], "新大門")
        self.assertEqual(saved["streams"][1]["camera_id"], "cam-02")
        self.assertEqual(saved["streams"][1]["ums_model"]["name"], "yolo8s")

        # Verify UMS model
        self.assertEqual(saved["ums_model"]["name"], "yolo8n")
        self.assertEqual(saved["ums_model"]["version"], "latest")

        # Verify Heartbeat
        self.assertTrue(saved["heartbeat"]["enabled"])
        self.assertEqual(saved["heartbeat"]["agent_port"], 8080)

        # Verify Advanced parameters
        self.assertEqual(saved["event_absence_tolerance"], 3)
        self.assertEqual(saved["ums_base_url"], "http://ums.example.com")
        self.assertEqual(saved["ums_api_key"], "new_key_123")

        # Verify Non-destructive preservation
        self.assertEqual(saved["event_severity"], {"person": "HIGH"})
        self.assertIn("rtsp://127.0.0.1:8554/stream1", saved["zones"])

        # Verify thread was started for background sync
        mock_thread_cls.assert_called_once()

    def test_save_local_model_clears_ums_model(self):
        initial = {
            "mode": "rtsp",
            "model_path": "best.onnx",
            "ums_model": {"name": "yolo8n", "version": "latest"},
            "fps_limit": 2,
            "cpu_cores": 4,
            "conf_threshold": 0.25,
            "log_interval_seconds": 60,
            "log_file": "perf.log",
            "detection_log_file": "det.log"
        }
        self.write_yaml(initial)

        form_data = {
            "mode": "video",
            "video_path": "C:/test.avi",
            "model_source": "local",
            "model_path": "models/custom.pt",
            "fps_limit": "2",
            "cpu_cores": "4",
            "conf_threshold": "0.25",
            "log_interval_seconds": "60",
            "log_file": "perf.log",
            "detection_log_file": "det.log"
        }

        response = self.client.post('/', data=form_data)
        self.assertEqual(response.status_code, 200)

        saved = self.read_yaml()
        self.assertEqual(saved["model_path"], "models/custom.pt")
        self.assertNotIn("ums_model", saved)
        self.assertEqual(saved["mode"], "video")
        self.assertEqual(saved["video_path"], "C:/test.avi")

    def test_render_index_page(self):
        initial = {
            "mode": "rtsp",
            "model_path": "best.onnx",
            "streams": [
                {"url": "rtsp://127.0.0.1:8554/stream1", "label": "大門", "camera_id": "cam-01"}
            ],
            "ums_model": {"name": "yolo8n", "version": "latest"},
            "ums_base_url": "http://ums.example.com",
            "ums_api_key": "key123",
            "heartbeat": {"enabled": True, "agent_port": 8080},
            "fps_limit": 2,
            "cpu_cores": 4,
            "conf_threshold": 0.25,
            "log_interval_seconds": 60,
            "log_file": "perf.log",
            "detection_log_file": "det.log"
        }
        self.write_yaml(initial)

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("ARGUS // PREDICTOR_NANO", html)
        self.assertIn("系統參數設定", html)
        self.assertIn("section-badge", html)
        self.assertIn("推論效能參數", html)
        self.assertIn("全域模型來源配置", html)
        self.assertIn("運作模式與串流清單", html)
        self.assertIn("進階系統參數", html)
        self.assertIn("串流詳細設定", html)
        self.assertIn("切換面板", html)
        self.assertIn("同步模型", html)
        self.assertIn("儲存並套用設定", html)
        self.assertIn("master-stream-list", html)
        self.assertIn("stream-detail-inspector", html)
        self.assertIn("ums-project-select", html)
        self.assertIn("detail-ums-project-select", html)
        self.assertIn("detail-label-source-ums", html)
        self.assertIn("global-model-format-select", html)
        self.assertIn("detail-model-format-select", html)
        self.assertIn("detail-camid-warning", html)
        self.assertIn("parseArgusCameraId", html)
        self.assertIn("restoreArgusCameraId", html)
        self.assertIn("fab-preset-select", html)
        self.assertIn("ums-endpoints-container", html)
        self.assertIn("applyFabPreset", html)
        self.assertIn("renderUmsEndpointRows", html)

    def test_save_argus_stream_with_custom_camera_id(self):
        initial = {
            "mode": "rtsp",
            "model_path": "best.onnx",
            "streams": [
                {"url": "rtsp://127.0.0.1:8554/cam-0eb40kwvs74z", "camera_id": "cam-0eb40kwvs74z"}
            ]
        }
        self.write_yaml(initial)

        # User modified camera_id to custom "CCD1"
        streams_payload = [
            {"url": "rtsp://127.0.0.1:8554/cam-0eb40kwvs74z", "label": "大門", "camera_id": "CCD1"}
        ]
        form_data = {
            "mode": "rtsp",
            "model_source": "local",
            "model_path": "best.onnx",
            "streams_json": json.dumps(streams_payload),
            "fps_limit": "2",
            "cpu_cores": "4",
            "conf_threshold": "0.25",
            "log_interval_seconds": "60",
            "log_file": "perf.log",
            "detection_log_file": "det.log"
        }
        response = self.client.post('/', data=form_data)
        self.assertEqual(response.status_code, 200)

        saved = self.read_yaml()
        self.assertEqual(len(saved["streams"]), 1)
        self.assertEqual(saved["streams"][0]["url"], "rtsp://127.0.0.1:8554/cam-0eb40kwvs74z")
        self.assertEqual(saved["streams"][0]["camera_id"], "CCD1")

    def test_save_multi_ums_base_urls(self):
        initial = {
            "mode": "rtsp",
            "model_path": "best.onnx",
            "ums_base_url": "http://old-single.ums",
        }
        self.write_yaml(initial)

        form_data = {
            "mode": "rtsp",
            "model_path": "best.onnx",
            "ums_base_urls": [
                "http://10.26.11.108/umsapiproxy/fab4ums",
                "http://10.26.11.109/umsapiproxy/fab4ums"
            ],
            "ums_api_key": "secret_key_999",
        }

        response = self.client.post('/', data=form_data)
        self.assertEqual(response.status_code, 200)

        saved = self.read_yaml()
        self.assertEqual(saved["ums_base_urls"], [
            "http://10.26.11.108/umsapiproxy/fab4ums",
            "http://10.26.11.109/umsapiproxy/fab4ums"
        ])
        self.assertNotIn("ums_base_url", saved)
        self.assertEqual(saved["ums_api_key"], "secret_key_999")

    def test_save_log_backup_count_and_paths(self):
        initial = {
            "mode": "rtsp",
            "model_path": "best.onnx",
            "log_file": "logs/performance.log",
            "detection_log_file": "logs/detections.log",
            "log_backup_count": 3,
        }
        self.write_yaml(initial)

        form_data = {
            "mode": "rtsp",
            "model_path": "best.onnx",
            "log_file": "logs/custom_perf.log",
            "detection_log_file": "logs/custom_det.log",
            "log_backup_count": "7",
            "fps_limit": "2",
            "cpu_cores": "4",
            "conf_threshold": "0.25",
            "log_interval_seconds": "60",
        }

        response = self.client.post('/', data=form_data)
        self.assertEqual(response.status_code, 200)

        saved = self.read_yaml()
        self.assertEqual(saved["log_file"], "logs/custom_perf.log")
        self.assertEqual(saved["detection_log_file"], "logs/custom_det.log")
        self.assertEqual(saved["log_backup_count"], 7)

    def test_render_log_backup_count_field(self):
        initial = {
            "mode": "rtsp",
            "model_path": "best.onnx",
            "log_file": "logs/performance.log",
            "detection_log_file": "logs/detections.log",
            "log_backup_count": 5,
        }
        self.write_yaml(initial)

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("log_backup_count", html)
        self.assertIn("日誌保留天數", html)
        self.assertIn('value="5"', html)


if __name__ == "__main__":
    unittest.main()

