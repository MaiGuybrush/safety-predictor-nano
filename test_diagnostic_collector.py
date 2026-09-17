import os
import sys
import tempfile
import zipfile
import json
import unittest
from pathlib import Path

from diagnostic_collector import (
    mask_sensitive_url,
    mask_api_key,
    sanitize_config,
    collect_system_info,
    install_crash_handler,
    collect_diagnostic_bundle,
    _read_file_with_limit,
)


class TestDiagnosticCollector(unittest.TestCase):
    def test_mask_sensitive_url(self):
        url_clean = "rtsp://192.168.1.10:8554/stream1"
        self.assertEqual(mask_sensitive_url(url_clean), url_clean)

        url_with_auth = "rtsp://admin:secret123@192.168.1.10:8554/stream1"
        masked = mask_sensitive_url(url_with_auth)
        self.assertEqual(masked, "rtsp://admin:******@192.168.1.10:8554/stream1")

        http_url = "http://user:p@ssw0rd@mes-api.factory.internal/status"
        masked_http = mask_sensitive_url(http_url)
        self.assertEqual(masked_http, "http://user:******@mes-api.factory.internal/status")

    def test_mask_api_key(self):
        self.assertEqual(mask_api_key(""), "")
        self.assertEqual(mask_api_key("short"), "******")
        key = "ums_hkC1ByYPW5LQQ3eGqYTRsfQHZO2VO5Cjj05DHvJiIXw"
        masked = mask_api_key(key)
        self.assertTrue(masked.startswith("ums_***[MASKED]***"))
        self.assertTrue(masked.endswith("IXw"))
        self.assertNotIn("hkC1ByYPW5LQQ", masked)

    def test_sanitize_config(self):
        raw_cfg = {
            "ums_api_key": "ums_secret_key_123456789",
            "cpu_cores": 4,
            "streams": [
                {"camera_id": "cam01", "url": "rtsp://admin:secretPass@10.0.0.1:554/live"}
            ],
            "zones": {
                "rtsp://admin:secretPass@10.0.0.1:554/live": {"polygon": [[0, 0], [1, 1]]}
            },
            "external_states": {
                "stk01": {"url": "http://apiuser:apipass@10.0.0.2/state"}
            }
        }

        sanitized = sanitize_config(raw_cfg)
        # 確保原物件未被修改
        self.assertEqual(raw_cfg["ums_api_key"], "ums_secret_key_123456789")
        # 檢驗脫敏結果
        self.assertNotIn("secret_key", sanitized["ums_api_key"])
        self.assertEqual(sanitized["cpu_cores"], 4)
        self.assertEqual(sanitized["streams"][0]["url"], "rtsp://admin:******@10.0.0.1:554/live")
        self.assertIn("rtsp://admin:******@10.0.0.1:554/live", sanitized["zones"])
        self.assertEqual(sanitized["external_states"]["stk01"]["url"], "http://apiuser:******@10.0.0.2/state")

    def test_collect_system_info(self):
        info = collect_system_info()
        self.assertIn("hostname", info)
        self.assertIn("platform", info)
        self.assertIn("python_version", info)
        self.assertIn("ipv4_addresses", info)
        self.assertIsInstance(info["ipv4_addresses"], list)

    def test_crash_handler_logs_traceback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            orig_excepthook = sys.excepthook
            try:
                install_crash_handler(log_dir=temp_dir)
                try:
                    raise ValueError("Simulated fatal test error")
                except ValueError:
                    exc_type, exc_val, exc_tb = sys.exc_info()
                    sys.excepthook(exc_type, exc_val, exc_tb)

                crash_log = os.path.join(temp_dir, "crash.log")
                self.assertTrue(os.path.isfile(crash_log))
                with open(crash_log, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("[FATAL CRASH]", content)
                self.assertIn("ValueError", content)
                self.assertIn("Simulated fatal test error", content)
            finally:
                sys.excepthook = orig_excepthook

    def test_read_file_with_limit_truncation(self):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            # 建立約 1000 位元組資料
            tf.write(b"Line 1\n" + b"A" * 800 + b"\nLine 2\nLine 3\n")
            tf_path = tf.name

        try:
            # 限制讀取 200 位元組
            truncated = _read_file_with_limit(tf_path, max_bytes=200)
            self.assertIn(b"[... TRUNCATED:", truncated)
            self.assertIn(b"Line 3", truncated)
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_collect_diagnostic_bundle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            logs_dir = temp_path / "logs"
            logs_dir.mkdir()
            (logs_dir / "system.log").write_text("System startup ok\n", encoding="utf-8")
            (logs_dir / "crash.log").write_text("Fatal error trace\n", encoding="utf-8")

            cfg_file = temp_path / "config.yaml"
            cfg_file.write_text("ums_api_key: secret_1234567890\nmode: video\n", encoding="utf-8")

            out_dir = temp_path / "bundles"
            bundle = collect_diagnostic_bundle(
                output_dir=str(out_dir),
                logs_dir=str(logs_dir),
                config_path=str(cfg_file),
            )

            self.assertTrue(os.path.isfile(bundle["zip_path"]))
            self.assertTrue(bundle["size_bytes"] > 0)
            self.assertIn("sysinfo.json", bundle["files_included"])
            self.assertIn("config.yaml", bundle["files_included"])
            self.assertIn("logs/system.log", bundle["files_included"])
            self.assertIn("logs/crash.log", bundle["files_included"])

            # 檢驗 ZIP 內檔案與脫敏結果
            with zipfile.ZipFile(bundle["zip_path"], "r") as zf:
                names = zf.namelist()
                self.assertIn("sysinfo.json", names)
                self.assertIn("config.yaml", names)
                self.assertIn("logs/system.log", names)
                self.assertIn("logs/crash.log", names)

                sysinfo_data = json.loads(zf.read("sysinfo.json").decode("utf-8"))
                self.assertIn("hostname", sysinfo_data)

                sanitized_cfg_text = zf.read("config.yaml").decode("utf-8")
                self.assertNotIn("secret_1234567890", sanitized_cfg_text)
                self.assertIn("MASKED", sanitized_cfg_text)


if __name__ == "__main__":
    unittest.main()
