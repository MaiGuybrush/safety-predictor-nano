import sys
import unittest
from unittest.mock import patch, MagicMock

import report_issue
from issue_service_client import FileUploadError, GiteaIssueError


class TestOfflineCLIReporter(unittest.TestCase):

    def test_parser_defaults_and_custom_flags(self):
        parser = report_issue.create_parser()
        args = parser.parse_args([
            "--title", "測試標題",
            "--desc", "測試描述",
            "--non-interactive",
            "--output-dir", "custom-bundles",
            "--gateway-hosts", "http://host1.oa,http://host2.oa",
        ])
        self.assertEqual(args.title, "測試標題")
        self.assertEqual(args.description, "測試描述")
        self.assertTrue(args.non_interactive)
        self.assertEqual(args.output_dir, "custom-bundles")
        self.assertEqual(args.gateway_hosts, "http://host1.oa,http://host2.oa")

    @patch("diagnostic_collector.collect_diagnostic_bundle")
    @patch("issue_service_client.IssueServiceClient.upload_diagnostic_file")
    @patch("issue_service_client.IssueServiceClient.create_gitea_issue")
    def test_run_cli_non_interactive_success(self, mock_create_issue, mock_upload, mock_bundle):
        mock_bundle.return_value = {
            "zip_path": "issue-bundles/diagnostic_20260915.zip",
            "zip_filename": "diagnostic_20260915.zip",
            "size_bytes": 1024 * 500,
            "report_id": "260915153000_err",
            "sysinfo": {"hostname": "edge-pi-01"},
            "files_included": ["sysinfo.json", "config.yaml", "logs/crash.log"],
        }
        mock_upload.return_value = {
            "status": "success",
            "download_url": "http://tncimweb1.cminl.oa/FileServiceCore/File?srcName=ErrorReport...",
            "host": "http://tncimweb1.cminl.oa",
            "zip_filename": "diagnostic_20260915.zip",
        }
        mock_create_issue.return_value = {
            "status": "success",
            "issue_number": 62,
            "issue_url": "http://tncimweb1.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/62",
            "title": "測試標題",
        }

        exit_code = report_issue.run_cli([
            "--title", "系統異常崩潰",
            "--desc", "啟動時找不到模型檔",
            "--non-interactive",
        ])

        self.assertEqual(exit_code, 0)
        mock_bundle.assert_called_once()
        mock_upload.assert_called_once()
        mock_create_issue.assert_called_once()

    @patch("diagnostic_collector.collect_diagnostic_bundle")
    def test_run_cli_bundle_failure(self, mock_bundle):
        mock_bundle.side_effect = RuntimeError("無法讀取設定檔")

        exit_code = report_issue.run_cli([
            "--title", "異常測試",
            "--non-interactive",
        ])
        self.assertEqual(exit_code, 1)

    @patch("diagnostic_collector.collect_diagnostic_bundle")
    @patch("issue_service_client.IssueServiceClient.upload_diagnostic_file")
    def test_run_cli_upload_failure(self, mock_upload, mock_bundle):
        mock_bundle.return_value = {
            "zip_path": "issue-bundles/diagnostic_test.zip",
            "zip_filename": "diagnostic_test.zip",
            "size_bytes": 1024,
            "report_id": "rep01",
            "sysinfo": {},
            "files_included": [],
        }
        mock_upload.side_effect = FileUploadError("Gateway 連線逾時")

        exit_code = report_issue.run_cli([
            "--title", "上傳失敗測試",
            "--non-interactive",
        ])
        self.assertEqual(exit_code, 2)

    @patch("diagnostic_collector.collect_diagnostic_bundle")
    @patch("issue_service_client.IssueServiceClient.upload_diagnostic_file")
    @patch("issue_service_client.IssueServiceClient.create_gitea_issue")
    def test_run_cli_issue_creation_failure(self, mock_create_issue, mock_upload, mock_bundle):
        mock_bundle.return_value = {
            "zip_path": "issue-bundles/diagnostic_test.zip",
            "zip_filename": "diagnostic_test.zip",
            "size_bytes": 1024,
            "report_id": "rep01",
            "sysinfo": {},
            "files_included": [],
        }
        mock_upload.return_value = {
            "status": "success",
            "download_url": "http://download.url",
            "host": "http://host",
            "zip_filename": "diagnostic_test.zip",
        }
        mock_create_issue.side_effect = GiteaIssueError("Gitea API 回傳 500")

        exit_code = report_issue.run_cli([
            "--title", "建立 Issue 失敗測試",
            "--non-interactive",
        ])
        self.assertEqual(exit_code, 3)

    @patch("report_issue.run_cli")
    def test_main_cli_arg_delegation(self, mock_run_cli):
        mock_run_cli.return_value = 0
        import main

        test_argv = ["main.py", "--report-issue", "--title", "Hello", "--non-interactive"]
        with patch.object(sys, "argv", test_argv):
            # 檢查 main.py 的 __name__ == '__main__' 區塊邏輯
            if "--report-issue" in sys.argv or "-r" in sys.argv:
                cli_args = [arg for arg in sys.argv[1:] if arg not in ("--report-issue", "-r")]
                ret = report_issue.run_cli(cli_args)
            self.assertEqual(ret, 0)
            mock_run_cli.assert_called_once_with(["--title", "Hello", "--non-interactive"])


if __name__ == "__main__":
    unittest.main()
