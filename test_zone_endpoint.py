import unittest
from unittest.mock import patch, MagicMock

import web_ui


class TestZoneEndpoint(unittest.TestCase):
    def setUp(self):
        web_ui.app.config['TESTING'] = True
        self.client = web_ui.app.test_client()

    @patch("web_ui.ConfigManager")
    def test_get_zone_existing(self, mock_cfg_mgr_cls):
        mock_mgr = mock_cfg_mgr_cls.return_value
        mock_mgr.get_zone.return_value = {
            "polygon": [[0.1, 0.2], [0.5, 0.2], [0.5, 0.8], [0.1, 0.8]],
            "zone_name": "機台危險區"
        }

        stream_url = "rtsp://127.0.0.1:8554/test_stream1"
        response = self.client.get(f'/zone/{stream_url}')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["polygon"], [[0.1, 0.2], [0.5, 0.2], [0.5, 0.8], [0.1, 0.8]])
        self.assertEqual(data["zone_name"], "機台危險區")
        mock_mgr.get_zone.assert_called_once_with(stream_url)

    @patch("web_ui.ConfigManager")
    def test_get_zone_not_found(self, mock_cfg_mgr_cls):
        mock_mgr = mock_cfg_mgr_cls.return_value
        mock_mgr.get_zone.return_value = None

        stream_url = "rtsp://127.0.0.1:8554/nonexistent"
        response = self.client.get(f'/zone/{stream_url}')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsNone(data.get("polygon"))

    @patch("web_ui.ConfigManager")
    def test_post_zone_save(self, mock_cfg_mgr_cls):
        mock_mgr = mock_cfg_mgr_cls.return_value
        mock_mgr.get_zone.return_value = {
            "polygon": [[0.1, 0.2], [0.5, 0.2], [0.5, 0.8], [0.1, 0.8]],
            "zone_name": "機台危險區"
        }
        stream_url = "rtsp://127.0.0.1:8554/test_stream1"
        payload = {
            "polygon": [[0.1, 0.2], [0.5, 0.2], [0.5, 0.8], [0.1, 0.8]],
            "zone_name": "機台危險區"
        }

        response = self.client.post(f'/zone/{stream_url}', json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["zone"]["zone_name"], "機台危險區")
        mock_mgr.save_zone.assert_called_once_with(
            stream_url,
            payload["polygon"],
            "機台危險區"
        )

    @patch("web_ui.ConfigManager")
    def test_post_zone_clear(self, mock_cfg_mgr_cls):
        mock_mgr = mock_cfg_mgr_cls.return_value
        mock_mgr.get_zone.return_value = None
        stream_url = "rtsp://127.0.0.1:8554/test_stream1"
        payload = {
            "polygon": []
        }

        response = self.client.post(f'/zone/{stream_url}', json=payload)

        self.assertEqual(response.status_code, 200)
        mock_mgr.save_zone.assert_called_once_with(
            stream_url,
            [],
            None
        )


    @patch("web_ui.load_config")
    def test_index_page_rendering_with_dict_streams(self, mock_load_config):
        mock_load_config.return_value = {
            "model_path": "best.onnx",
            "cpu_cores": 4,
            "fps_limit": 2,
            "log_interval_seconds": 60,
            "log_file": "performance.log",
            "detection_log_file": "detections.log",
            "streams": [
                {"url": "rtsp://127.0.0.1:8554/test_stream1", "label": "大門入口", "camera_id": "cam-01", "model": "best.onnx"}
            ]
        }
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"rtsp://127.0.0.1:8554/test_stream1", response.data)


if __name__ == "__main__":
    unittest.main()

