import unittest
from unittest.mock import patch, MagicMock
import web_ui


class TestWebUiReportIssue(unittest.TestCase):
    def setUp(self):
        web_ui.app.config['TESTING'] = True
        self.client = web_ui.app.test_client()

    def test_index_contains_report_issue_elements(self):
        """驗證 Web UI 頁面中包含回報問題按鈕、Modal 與表單欄位。"""
        with patch('web_ui.load_config', return_value={}):
            resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('id="report-issue-btn"', html)
        self.assertIn('openReportIssueModal()', html)
        self.assertIn('id="report-issue-overlay"', html)
        self.assertIn('id="report-issue-modal"', html)
        self.assertIn('id="report-issue-form"', html)
        self.assertIn('id="ri-title-input"', html)
        self.assertIn('id="ri-severity-select"', html)
        self.assertIn('id="ri-desc-input"', html)
        self.assertIn('id="ri-steps-input"', html)
        self.assertIn('id="ri-submit-btn"', html)
        self.assertIn('id="report-issue-result"', html)

    @patch('web_ui.issue_service_client.IssueServiceClient')
    @patch('web_ui.diagnostic_collector.collect_diagnostic_bundle')
    def test_report_issue_api_success(self, mock_collect, mock_client_cls):
        """驗證 POST /api/issue/report 成功流程。"""
        mock_collect.return_value = {
            "zip_path": "/tmp/test.zip",
            "zip_filename": "test.zip",
            "size_bytes": 1024,
            "report_id": "260915_test",
            "sysinfo": {"os": "Linux"},
            "files_included": ["sysinfo.json"],
        }
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.upload_diagnostic_file.return_value = {
            "status": "success",
            "download_url": "http://gateway/FileServiceCore/File?test.zip",
            "host": "http://gateway",
        }
        mock_client.create_gitea_issue.return_value = {
            "status": "success",
            "issue_number": 99,
            "issue_url": "http://gitea/issues/99",
            "title": "[HIGH] 推論中斷",
        }

        payload = {
            "title": "推論中斷",
            "severity": "high",
            "description": "攝影機無法取得影格",
            "steps": "1. 啟動推論\n2. 5分鐘後斷線"
        }

        resp = self.client.post('/api/issue/report', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["issue_id"], 99)
        self.assertEqual(data["issue_number"], 99)
        self.assertEqual(data["issue_url"], "http://gitea/issues/99")
        self.assertEqual(data["download_url"], "http://gateway/FileServiceCore/File?test.zip")
        self.assertEqual(data["report_id"], "260915_test")

        # 驗證 client 呼叫之參數
        mock_client.upload_diagnostic_file.assert_called_once_with(
            zip_path="/tmp/test.zip",
            report_id="260915_test",
        )
        mock_client.create_gitea_issue.assert_called_once()
        call_kwargs = mock_client.create_gitea_issue.call_args[1]
        self.assertIn("[HIGH] 推論中斷", call_kwargs["title"])
        self.assertIn("高 (High)", call_kwargs["description"])
        self.assertIn("攝影機無法取得影格", call_kwargs["description"])
        self.assertIn("1. 啟動推論", call_kwargs["description"])

    @patch('web_ui.issue_service_client.IssueServiceClient')
    @patch('web_ui.diagnostic_collector.collect_diagnostic_bundle')
    def test_report_issue_api_defaults(self, mock_collect, mock_client_cls):
        """驗證當前端未傳入 title / description 時採用預設值。"""
        mock_collect.return_value = {
            "zip_path": "/tmp/test_default.zip",
            "zip_filename": "test_default.zip",
            "size_bytes": 2048,
            "report_id": "260915_default",
            "sysinfo": {},
            "files_included": [],
        }
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.upload_diagnostic_file.return_value = {
            "status": "success",
            "download_url": "http://gateway/FileServiceCore/File?test_default.zip",
            "host": "http://gateway",
        }
        mock_client.create_gitea_issue.return_value = {
            "status": "success",
            "issue_number": 100,
            "issue_url": "http://gitea/issues/100",
            "title": "Web UI 使用者回報系統異常",
        }

        resp = self.client.post('/api/issue/report', json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["issue_id"], 100)

        call_kwargs = mock_client.create_gitea_issue.call_args[1]
        self.assertEqual(call_kwargs["title"], "Web UI 使用者回報系統異常")

    @patch('web_ui.diagnostic_collector.collect_diagnostic_bundle')
    def test_report_issue_api_collector_error(self, mock_collect):
        """驗證封包收集發生錯誤時回傳 500。"""
        mock_collect.side_effect = RuntimeError("磁碟空間不足無法寫入 ZIP")

        resp = self.client.post('/api/issue/report', json={"title": "測試"})
        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("磁碟空間不足", data["message"])

    @patch('web_ui.issue_service_client.IssueServiceClient')
    @patch('web_ui.diagnostic_collector.collect_diagnostic_bundle')
    def test_report_issue_api_upload_error(self, mock_collect, mock_client_cls):
        """驗證上傳至 Gateway 失敗時回傳 500。"""
        mock_collect.return_value = {
            "zip_path": "/tmp/err.zip",
            "zip_filename": "err.zip",
            "size_bytes": 500,
            "report_id": "260915_err",
            "sysinfo": {},
            "files_included": [],
        }
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.upload_diagnostic_file.side_effect = ConnectionError("所有 Gateway 主機皆斷線")

        resp = self.client.post('/api/issue/report', json={"title": "測試"})
        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("所有 Gateway 主機皆斷線", data["message"])


if __name__ == '__main__':
    unittest.main()
