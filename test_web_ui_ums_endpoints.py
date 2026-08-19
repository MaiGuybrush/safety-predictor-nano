import unittest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

import web_ui


@dataclass
class DummyVersion:
    version_id: int
    version_number: int
    status: str
    accuracy: float = 0.95
    artifact_size: int = 1000
    comment: str = "Test version"
    created_at: str = "2026-08-17"
    download_url: str = "http://example.com/dl"


@dataclass
class DummyModel:
    model_id: int
    model_name: str
    description: str
    project_id: int
    project_name: str
    architecture_name: str
    status: str
    created_at: str
    versions: list


class TestWebUiUmsEndpoints(unittest.TestCase):
    def setUp(self):
        web_ui.app.config['TESTING'] = True
        self.client = web_ui.app.test_client()

    @patch("web_ui.FailoverUmsClient")
    @patch("web_ui.ConfigManager")
    def test_get_ums_models_success(self, mock_config_mgr_cls, mock_failover_client_cls):
        mock_cfg = mock_config_mgr_cls.return_value
        mock_cfg.get_ums_base_urls.return_value = ["http://test.ums"]
        mock_cfg.get.side_effect = lambda k, d=None: {
            "ums_api_key": "test_key"
        }.get(k, d)

        mock_client = mock_failover_client_cls.return_value
        mock_client.fetch_my_models.return_value = [
            DummyModel(
                model_id=1,
                model_name="yolo8n",
                description="desc",
                project_id=10,
                project_name="SafetyProject",
                architecture_name="YOLOv8",
                status="Active",
                created_at="2026-08-01",
                versions=[
                    DummyVersion(version_id=101, version_number=1, status="Active", comment="v1 active"),
                    DummyVersion(version_id=102, version_number=2, status="Draft", comment="v2 draft"),
                ]
            ),
            DummyModel(
                model_id=2,
                model_name="yolo8s",
                description="desc",
                project_id=10,
                project_name="SafetyProject",
                architecture_name="YOLOv8",
                status="Active",
                created_at="2026-08-02",
                versions=[
                    DummyVersion(version_id=103, version_number=1, status="Active", comment="v1"),
                ]
            )
        ]

        response = self.client.get('/api/ums/models')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(len(data["projects"]), 1)
        project = data["projects"][0]
        self.assertEqual(project["project_id"], 10)
        self.assertEqual(project["project_name"], "SafetyProject")
        self.assertEqual(len(project["models"]), 2)
        self.assertEqual(project["models"][0]["model_name"], "yolo8n")
        self.assertEqual(len(project["models"][0]["versions"]), 2)

    @patch("web_ui.FailoverUmsClient")
    @patch("web_ui.ConfigManager")
    def test_get_ums_models_api_error_returns_200_with_error_status(self, mock_config_mgr_cls, mock_failover_client_cls):
        mock_cfg = mock_config_mgr_cls.return_value
        mock_cfg.get_ums_base_urls.return_value = ["http://test.ums"]
        mock_cfg.get.side_effect = lambda k, d=None: {
            "ums_api_key": "test_key"
        }.get(k, d)

        mock_client = mock_failover_client_cls.return_value
        mock_client.fetch_my_models.side_effect = RuntimeError("Connection refused")

        response = self.client.get('/api/ums/models')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("Connection refused", data["message"])

    @patch("web_ui.ConfigManager")
    def test_get_ums_models_missing_key_returns_error_status(self, mock_config_mgr_cls):
        mock_cfg = mock_config_mgr_cls.return_value
        mock_cfg.get_ums_base_urls.return_value = ["http://test.ums"]
        mock_cfg.get.return_value = None

        with patch.dict("os.environ", {}, clear=True):
            response = self.client.get('/api/ums/models')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["status"], "error")

    @patch("web_ui.FailoverUmsClient")
    def test_test_connection_success(self, mock_failover_client_cls):
        mock_client = mock_failover_client_cls.return_value
        mock_client.test_endpoints.return_value = [
            {"url": "http://test.ums", "status": "ok", "models_count": 2, "message": "連線成功"}
        ]

        response = self.client.post('/api/ums/test_connection', json={
            "base_url": "http://test.ums",
            "api_key": "valid_key"
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["models_count"], 2)
        self.assertEqual(len(data["endpoints"]), 1)

    @patch("web_ui.FailoverUmsClient")
    def test_test_connection_multi_endpoints(self, mock_failover_client_cls):
        mock_client = mock_failover_client_cls.return_value
        mock_client.test_endpoints.return_value = [
            {"url": "http://ep1.ums", "status": "ok", "models_count": 3, "message": "連線成功"},
            {"url": "http://ep2.ums", "status": "error", "message": "Timeout", "error": "Timeout"}
        ]

        response = self.client.post('/api/ums/test_connection', json={
            "base_urls": ["http://ep1.ums", "http://ep2.ums"],
            "api_key": "valid_key"
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["models_count"], 3)
        self.assertEqual(len(data["endpoints"]), 2)
        self.assertEqual(data["endpoints"][0]["status"], "ok")
        self.assertEqual(data["endpoints"][1]["status"], "error")

    @patch("web_ui.FailoverUmsClient")
    def test_test_connection_all_failure(self, mock_failover_client_cls):
        mock_client = mock_failover_client_cls.return_value
        mock_client.test_endpoints.return_value = [
            {"url": "http://test.ums", "status": "error", "message": "401 Unauthorized", "error": "401 Unauthorized"}
        ]

        response = self.client.post('/api/ums/test_connection', json={
            "base_url": "http://test.ums",
            "api_key": "invalid_key"
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("401 Unauthorized", data["message"])
        self.assertEqual(len(data["endpoints"]), 1)


if __name__ == "__main__":
    unittest.main()
