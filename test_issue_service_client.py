import os
import sys
import tempfile
import json
import unittest
from unittest.mock import patch, MagicMock
import requests

from issue_service_client import (
    resolve_gateway_hosts,
    IssueServiceClient,
    upload_diagnostic_file,
    create_gitea_issue,
    report_diagnostic_issue,
    IssueServiceError,
    FileUploadError,
    GiteaIssueError,
    GatewayConnectionError,
    DEFAULT_GATEWAY_HOSTS,
)


class TestIssueServiceClient(unittest.TestCase):

    def test_resolve_gateway_hosts_with_config(self):
        mock_config = {
            "api.fab1": [
                "http://10.26.11.108/umsapiproxy/fab4ums",
                "http://10.26.11.109/umsapiproxy/fab4ums",
            ],
            "api.oa": [
                "http://tncimweb1.cminl.oa/umsapiproxy/fab4ums",
                "http://tncimweb1.cminl.oa/another/path",  # 同 host 應去重
            ],
            "domainDefine": {
                "fab1": ["10.26."],
            }
        }
        # 匹配 fab1
        hosts_fab1 = resolve_gateway_hosts(ums_api_config=mock_config, ip_addresses=["10.26.1.50"])
        self.assertEqual(hosts_fab1, ["http://10.26.11.108", "http://10.26.11.109"])

        # 未匹配回退至 oa，並去除重複主機
        hosts_oa = resolve_gateway_hosts(ums_api_config=mock_config, ip_addresses=["192.168.1.100"])
        self.assertEqual(hosts_oa, ["http://tncimweb1.cminl.oa"])

    def test_resolve_gateway_hosts_fallback_empty(self):
        empty_config = {"domainDefine": {}}
        hosts = resolve_gateway_hosts(ums_api_config=empty_config, ip_addresses=[])
        self.assertEqual(hosts, list(DEFAULT_GATEWAY_HOSTS))

    def test_upload_diagnostic_file_not_found(self):
        client = IssueServiceClient(gateway_hosts=["http://mockhost"])
        with self.assertRaises(FileNotFoundError):
            client.upload_diagnostic_file(zip_path="non_existent.zip", report_id="test_01")

    def test_upload_diagnostic_file_success(self):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "count": 1,
            "size": 12345,
            "existFiles": [],
            "error": []
        }
        mock_session.post.return_value = mock_resp

        client = IssueServiceClient(
            gateway_hosts=["http://host1", "http://host2"],
            session=mock_session,
        )

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            tf.write(b"PK mock zip content")
            tf_path = tf.name

        try:
            res = client.upload_diagnostic_file(zip_path=tf_path, report_id="rep123")
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["host"], "http://host1")
            self.assertEqual(res["report_id"], "rep123")
            expected_filename = os.path.basename(tf_path)
            self.assertEqual(res["zip_filename"], expected_filename)
            self.assertIn(f"/FileServiceCore/File?srcName=ErrorReport&filePath=.%2Fsafety-nano%2Frep123%2F{expected_filename}", res["download_url"])

            # 驗證 POST 呼叫參數
            mock_session.post.assert_called_once()
            call_url = mock_session.post.call_args[0][0]
            self.assertTrue(call_url.startswith("http://host1/FileServiceCore/File"))
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_upload_diagnostic_file_failover(self):
        mock_session = MagicMock()
        resp_err = MagicMock()
        resp_err.status_code = 500
        resp_err.text = "Internal Server Error"

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"count": 1, "error": []}

        # 第 1 次 500，第 2 次 200
        mock_session.post.side_effect = [resp_err, resp_ok]

        client = IssueServiceClient(
            gateway_hosts=["http://badhost", "http://goodhost"],
            session=mock_session,
        )

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            tf.write(b"PK content")
            tf_path = tf.name

        try:
            res = client.upload_diagnostic_file(zip_path=tf_path, report_id="rep_failover")
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["host"], "http://goodhost")
            self.assertEqual(client.active_index, 1)
            self.assertEqual(mock_session.post.call_count, 2)
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_upload_diagnostic_file_all_fail(self):
        mock_session = MagicMock()
        mock_session.post.side_effect = requests.exceptions.ConnectionError("Refused")

        client = IssueServiceClient(
            gateway_hosts=["http://host1", "http://host2"],
            session=mock_session,
        )

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            tf.write(b"PK")
            tf_path = tf.name

        try:
            with self.assertRaises(GatewayConnectionError):
                client.upload_diagnostic_file(zip_path=tf_path, report_id="rep_fail")
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_create_gitea_issue_success(self):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "number": 88,
            "html_url": "http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/88",
            "title": "[使用者回報] 串流畫面延遲嚴重",
            "state": "open"
        }
        mock_session.post.return_value = mock_resp

        client = IssueServiceClient(
            gateway_hosts=["http://host1"],
            session=mock_session,
        )

        sysinfo = {"os": "Linux", "cpu_percent": 85.5}
        res = client.create_gitea_issue(
            title="串流畫面延遲嚴重",
            description="當啟動第二路串流時，畫面卡頓超過 5 秒。",
            download_url="http://host1/FileServiceCore/File?path=diag.zip",
            sysinfo=sysinfo,
            report_id="rep_001",
            zip_filename="diag.zip",
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["issue_number"], 88)
        self.assertEqual(res["issue_url"], "http://tncimweb.cminl.oa/git-server/guy.mai/safety-predictor-nano/issues/88")
        self.assertEqual(res["title"], "[使用者回報] 串流畫面延遲嚴重")

        # 檢驗 payload 內容
        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args[1]
        json_data = call_kwargs["json"]
        self.assertEqual(json_data["title"], "[使用者回報] 串流畫面延遲嚴重")
        self.assertIn("## 問題描述", json_data["body"])
        self.assertIn("當啟動第二路串流時", json_data["body"])
        self.assertIn("http://host1/FileServiceCore/File?path=diag.zip", json_data["body"])
        self.assertIn('"cpu_percent": 85.5', json_data["body"])

    def test_create_gitea_issue_failover(self):
        mock_session = MagicMock()
        resp_err = MagicMock()
        resp_err.status_code = 502
        resp_err.text = "Bad Gateway"

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {
            "number": 99,
            "html_url": "http://gitea/issues/99",
            "title": "[已自訂前綴] 故障回報"
        }

        mock_session.post.side_effect = [resp_err, resp_ok]

        client = IssueServiceClient(
            gateway_hosts=["http://gw1", "http://gw2"],
            session=mock_session,
        )

        res = client.create_gitea_issue(
            title="[已自訂前綴] 故障回報",
            description="測試描述",
            download_url="http://download.url",
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["issue_number"], 99)
        self.assertEqual(res["host"], "http://gw2")
        self.assertEqual(client.active_index, 1)

    def test_report_diagnostic_bundle_full_flow(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            tf.write(b"PK mock")
            tf_path = tf.name

        try:
            mock_session = MagicMock()
            upload_resp = MagicMock()
            upload_resp.status_code = 200
            upload_resp.json.return_value = {"count": 1, "error": []}

            issue_resp = MagicMock()
            issue_resp.status_code = 201
            issue_resp.json.return_value = {
                "number": 101,
                "html_url": "http://gitea/issues/101",
                "title": "[使用者回報] 一鍵回報測試"
            }

            mock_session.post.side_effect = [upload_resp, issue_resp]

            client = IssueServiceClient(
                gateway_hosts=["http://gw1"],
                session=mock_session,
            )

            result = client.report_diagnostic_bundle(
                title="一鍵回報測試",
                description="自動整合測試",
                zip_path=tf_path,
                report_id="flow_test_01",
                sysinfo={"test": True}
            )

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["issue_number"], 101)
            self.assertEqual(result["issue_url"], "http://gitea/issues/101")
            self.assertIn("FileServiceCore", result["download_url"])
            self.assertEqual(result["report_id"], "flow_test_01")
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_helper_functions(self):
        with patch.object(IssueServiceClient, "upload_diagnostic_file") as mock_upload:
            mock_upload.return_value = {"status": "success"}
            res = upload_diagnostic_file(zip_path="mock.zip", report_id="r1", gateway_hosts=["http://test"])
            self.assertEqual(res, {"status": "success"})

        with patch.object(IssueServiceClient, "create_gitea_issue") as mock_issue:
            mock_issue.return_value = {"status": "success"}
            res = create_gitea_issue(
                title="t", description="d", download_url="u", gateway_hosts=["http://test"]
            )
            self.assertEqual(res, {"status": "success"})

        with patch.object(IssueServiceClient, "report_diagnostic_bundle") as mock_bundle:
            mock_bundle.return_value = {"status": "success"}
            res = report_diagnostic_issue(
                title="t", description="d", zip_path="p", gateway_hosts=["http://test"]
            )
            self.assertEqual(res, {"status": "success"})


if __name__ == "__main__":
    unittest.main()
