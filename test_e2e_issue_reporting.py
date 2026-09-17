import os
import sys
import tempfile
import shutil
import zipfile
import json
import unittest
from unittest.mock import patch, MagicMock

import web_ui
import diagnostic_collector
import report_issue
from issue_service_client import IssueServiceClient


class TestE2EIssueReporting(unittest.TestCase):
    """端到端 (E2E) 整合測試：涵蓋真實日誌收集、敏感資料脫敏、ZIP 打包、Gateway Client 上傳與 Issue 建立流程。"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.logs_dir = os.path.join(self.test_dir, "logs")
        self.bundles_dir = os.path.join(self.test_dir, "issue-bundles")
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.bundles_dir, exist_ok=True)

        # 建立真實的日誌檔
        with open(os.path.join(self.logs_dir, "system.log"), "w", encoding="utf-8") as f:
            f.write("2026-09-15 16:00:00 [INFO] System started.\n")
        with open(os.path.join(self.logs_dir, "performance.log"), "w", encoding="utf-8") as f:
            f.write("2026-09-15 16:00:05 [PERF] FPS=10.0 CPU=25% RAM=15%\n")
        with open(os.path.join(self.logs_dir, "detections.log"), "w", encoding="utf-8") as f:
            f.write("2026-09-15 16:00:10 [DETECTION] Target detected: person (0.92)\n")
        with open(os.path.join(self.logs_dir, "crash.log"), "w", encoding="utf-8") as f:
            f.write("2026-09-15 16:00:15 [CRASH] Fatal exception in worker thread.\n")

        # 建立含有敏感金鑰與密碼的真實 config.yaml
        self.config_path = os.path.join(self.test_dir, "config.yaml")
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("""
ums_api_key: "super_secret_secret_12345"
streams:
  - id: 0
    rtsp_url: "rtsp://admin:P@ssw0rd!123@192.168.1.100:554/stream1"
external_states:
  door_sensor:
    url: "http://user:mypass@192.168.1.200/state"
""")

        web_ui.app.config['TESTING'] = True
        self.client = web_ui.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('issue_service_client.requests.Session')
    def test_e2e_web_ui_flow_with_real_bundle_and_sanitization(self, mock_session_cls):
        """E2E: 透過 Web UI API 發動回報，驗證真實封包產製、脫敏正確性與 Gateway 呼叫。"""
        # 設定 Mock HTTP 回應
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # 1. 模擬 FileServiceCore 上傳回應
        mock_upload_resp = MagicMock()
        mock_upload_resp.status_code = 200
        mock_upload_resp.json.return_value = {
            "status": "success",
            "count": 1,
            "size": 2048,
            "files": ["diagnostic_e2e.zip"],
            "error": None
        }

        # 2. 模擬 Gitea Issue 建立回應
        mock_issue_resp = MagicMock()
        mock_issue_resp.status_code = 201
        mock_issue_resp.json.return_value = {
            "number": 108,
            "html_url": "http://gitea.local/guy.mai/safety-predictor-nano/issues/108",
            "title": "[HIGH] 現場鏡頭影像花屏",
            "state": "open"
        }

        mock_session.post.side_effect = [mock_upload_resp, mock_issue_resp]

        orig_collect = diagnostic_collector.collect_diagnostic_bundle

        def custom_collect(**kwargs):
            return orig_collect(
                output_dir=self.bundles_dir,
                logs_dir=self.logs_dir,
                config_path=self.config_path,
            )

        with patch('web_ui.diagnostic_collector.collect_diagnostic_bundle', side_effect=custom_collect):
            payload = {
                "title": "現場鏡頭影像花屏",
                "severity": "high",
                "description": "鏡頭 #0 在夜間模式切換時出現嚴重雜訊花屏",
                "steps": "1. 等待傍晚切換夜視\n2. 檢視影像畫面"
            }

            resp = self.client.post('/api/issue/report', json=payload)
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()

            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["issue_number"], 108)
            self.assertEqual(data["issue_url"], "http://gitea.local/guy.mai/safety-predictor-nano/issues/108")
            zip_full_path = os.path.join(self.bundles_dir, data["zip_filename"])
            self.assertTrue(os.path.exists(zip_full_path))

            # 驗證真實產出的 ZIP 檔案內容是否包含脫敏資料
            with zipfile.ZipFile(zip_full_path, 'r') as zf:
                file_names = zf.namelist()
                self.assertIn("config.yaml", file_names)
                self.assertIn("sysinfo.json", file_names)
                self.assertIn("logs/crash.log", file_names)

                # 讀取 ZIP 內的 config.yaml 並驗證敏感資訊已確實遮蔽
                sanitized_config = zf.read("config.yaml").decode("utf-8")
                self.assertNotIn("super_secret_secret_12345", sanitized_config)
                self.assertNotIn("P@ssw0rd!123", sanitized_config)
                self.assertNotIn("mypass", sanitized_config)
                self.assertIn("******", sanitized_config)

                # 讀取 ZIP 內的 crash.log
                crash_content = zf.read("logs/crash.log").decode("utf-8")
                self.assertIn("Fatal exception in worker thread", crash_content)

    @patch('issue_service_client.requests.Session')
    def test_e2e_cli_offline_fallback_on_network_failure(self, mock_session_cls):
        """E2E: 透過 report_issue.py 離線模式，驗證當 Gateway 斷線時，本地保留封包並返回正確退出碼 (2)。"""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.side_effect = ConnectionError("Connection refused by gateway")

        # 呼叫 CLI 執行函式
        exit_code = report_issue.run_cli([
            "--title", "網路中斷離線測試",
            "--desc", "驗證斷網時本地封包保留指引",
            "--non-interactive",
            "--output-dir", self.bundles_dir,
            "--logs-dir", self.logs_dir,
            "--config", self.config_path
        ])

        # 上傳失敗應返回 2 (檔案保留於本機)
        self.assertEqual(exit_code, 2)

        # 但 issue-bundles 必須有留存的 zip 檔案
        bundles = os.listdir(self.bundles_dir)
        zip_bundles = [f for f in bundles if f.endswith(".zip")]
        self.assertGreater(len(zip_bundles), 0)


if __name__ == '__main__':
    unittest.main()
