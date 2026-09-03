"""test_state_poller.py - 單元測試：外部狀態同步模組與 Webhook API
"""

import io
import json
import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from state_poller import StatePoller, extract_json_path, GLOBAL_STATE_POLLER
import web_ui


class TestJsonPathExtraction(unittest.TestCase):
    def test_extract_json_path_simple(self):
        data = {"status": "RUNNING", "data": {"code": 200, "state": "MAINTENANCE"}}
        self.assertEqual(extract_json_path(data, "status"), "RUNNING")
        self.assertEqual(extract_json_path(data, "data.state"), "MAINTENANCE")
        self.assertEqual(extract_json_path(data, "data.code"), 200)

    def test_extract_json_path_array(self):
        data = {"equipments": [{"id": "E1", "status": "OK"}, {"id": "E2", "status": "ALARM"}]}
        self.assertEqual(extract_json_path(data, "equipments.0.status"), "OK")
        self.assertEqual(extract_json_path(data, "equipments.1.id"), "E2")

    def test_extract_json_path_missing(self):
        data = {"a": {"b": 1}}
        self.assertIsNone(extract_json_path(data, "a.c"))
        self.assertIsNone(extract_json_path(data, "x.y.z"))
        self.assertIsNone(extract_json_path(data, "a.b.c"))


class TestStatePollerMemoryAndTTL(unittest.TestCase):
    def setUp(self):
        self.poller = StatePoller()

    def test_update_and_get_state_no_ttl(self):
        self.poller.update_state("stocker_01", "RUNNING")
        self.assertEqual(self.poller.get_state("stocker_01"), "RUNNING")
        states = self.poller.get_current_states()
        self.assertEqual(states.get("stocker_01"), "RUNNING")

    def test_update_and_get_state_with_ttl(self):
        # 設定極短 TTL (0.1 秒)
        self.poller.update_state("stocker_02", "MAINTENANCE", ttl_seconds=0.1)
        self.assertEqual(self.poller.get_state("stocker_02"), "MAINTENANCE")
        time.sleep(0.15)
        # 過期後應回傳預設值
        self.assertIsNone(self.poller.get_state("stocker_02"))
        self.assertNotIn("stocker_02", self.poller.get_current_states())


class TestStatePollerNetwork(unittest.TestCase):
    def setUp(self):
        self.poller = StatePoller()

    @patch("urllib.request.urlopen")
    def test_poll_source_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.headers.get_content_charset.return_value = "utf-8"
        mock_resp.read.return_value = json.dumps({"data": {"status": "MAINTENANCE"}}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cfg = {
            "url": "http://mes-api/status",
            "method": "GET",
            "json_path": "data.status",
            "timeout_seconds": 2,
            "fallback_value": "UNKNOWN",
        }

        self.poller.poll_source_once("stocker_01", cfg)
        self.assertEqual(self.poller.get_state("stocker_01"), "MAINTENANCE")

    @patch("urllib.request.urlopen")
    def test_poll_source_failure_fallback(self, mock_urlopen):
        # 模擬網路逾時或連線失敗
        mock_urlopen.side_effect = Exception("Connection timeout")

        cfg = {
            "url": "http://mes-api/status",
            "method": "GET",
            "json_path": "data.status",
            "timeout_seconds": 2,
            "fallback_value": "OFFLINE",
        }

        self.poller.poll_source_once("stocker_01", cfg)
        self.assertEqual(self.poller.get_state("stocker_01"), "OFFLINE")


class TestWebUIComplianceEndpoints(unittest.TestCase):
    def setUp(self):
        web_ui.app.config["TESTING"] = True
        self.client = web_ui.app.test_client()

    def test_post_external_state_success(self):
        payload = {
            "source": "stocker_01",
            "status": "MAINTENANCE",
            "ttl_seconds": 30,
        }
        resp = self.client.post("/api/external_state", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["source"], "stocker_01")
        self.assertEqual(data["value"], "MAINTENANCE")
        self.assertEqual(GLOBAL_STATE_POLLER.get_state("stocker_01"), "MAINTENANCE")

    def test_post_external_state_missing_fields(self):
        resp = self.client.post("/api/external_state", json={"source": ""})
        self.assertEqual(resp.status_code, 400)

    def test_get_compliance_status_endpoint(self):
        GLOBAL_STATE_POLLER.update_state("stocker_03", "ALARM")
        web_ui.LATEST_COMPLIANCE_STATUS = {
            "0": {"status": "VIOLATION", "missing_barriers": ["cone"]}
        }
        resp = self.client.get("/api/compliance_status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("external_states", data)
        self.assertEqual(data["external_states"].get("stocker_03"), "ALARM")
        self.assertIn("compliance", data)
        self.assertEqual(data["compliance"]["0"]["status"], "VIOLATION")


if __name__ == "__main__":
    unittest.main()
