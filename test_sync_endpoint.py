import unittest
from unittest.mock import patch

import web_ui


class TestSyncEndpoint(unittest.TestCase):
    def setUp(self):
        web_ui.app.config['TESTING'] = True
        self.client = web_ui.app.test_client()

    @patch("web_ui.model_sync")
    @patch("web_ui.ConfigManager")
    def test_sync_models_returns_report_json(self, mock_config_mgr_cls, mock_model_sync):
        mock_model_sync.sync_all.return_value = {
            "timestamp": 123.0,
            "success": [{"key": "model_path", "name": "foo", "version": "latest", "path": "models/foo"}],
            "failed": [],
        }

        response = self.client.post('/sync_models')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data["success"]), 1)
        self.assertEqual(data["failed"], [])
        mock_model_sync.sync_all.assert_called_once_with(mock_config_mgr_cls.return_value)

    @patch("web_ui.model_sync")
    @patch("web_ui.ConfigManager")
    def test_sync_models_failure_returns_200_not_500(self, mock_config_mgr_cls, mock_model_sync):
        mock_model_sync.sync_all.return_value = {
            "timestamp": 123.0,
            "success": [],
            "failed": [{"key": "model_path", "name": "foo", "version": "latest", "error": "network down"}],
        }

        response = self.client.post('/sync_models')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data["failed"]), 1)

    @patch("web_ui.model_sync")
    def test_sync_status_returns_last_report(self, mock_model_sync):
        mock_model_sync.get_last_report.return_value = {
            "timestamp": 999.0, "success": [], "failed": []
        }

        response = self.client.get('/sync_status')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["timestamp"], 999.0)


if __name__ == "__main__":
    unittest.main()
