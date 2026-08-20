import unittest
from unittest.mock import patch
import os
import sys
import web_ui


class TestWebUiManual(unittest.TestCase):
    def setUp(self):
        web_ui.app.config["TESTING"] = True
        self.client = web_ui.app.test_client()

    def test_get_resource_path_dev_mode(self):
        """測試在開發模式下正確解析相對路徑"""
        with patch.object(sys, "frozen", False, create=True):
            path = web_ui.get_resource_path(os.path.join("docs", "user-manual", "book"))
            self.assertEqual(path, os.path.abspath(os.path.join("docs", "user-manual", "book")))

    def test_get_resource_path_frozen_mode(self):
        """測試在 PyInstaller 凍結環境 (_MEIPASS) 下正確解析路徑"""
        dummy_meipass = r"C:\tmp\_MEI12345" if sys.platform == "win32" else "/tmp/_MEI12345"
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", dummy_meipass, create=True):
            path = web_ui.get_resource_path(os.path.join("docs", "user-manual", "book"))
            expected = os.path.join(dummy_meipass, "docs", "user-manual", "book")
            self.assertEqual(path, expected)

    def test_serve_manual_root(self):
        """測試訪問 /manual/ 回傳 200 並回傳 index.html"""
        response = self.client.get("/manual/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"html", response.data.lower())

    def test_serve_manual_index(self):
        """測試訪問 /manual/index.html 回傳 200"""
        response = self.client.get("/manual/index.html")
        self.assertEqual(response.status_code, 200)

    def test_serve_manual_subpage(self):
        """測試訪問手冊子章節頁面回傳 200"""
        response = self.client.get("/manual/01-quick-start.html")
        self.assertEqual(response.status_code, 200)

    def test_serve_manual_not_found(self):
        """測試訪問不存在的手冊檔案回傳 404"""
        response = self.client.get("/manual/non_existent_file.xyz")
        self.assertEqual(response.status_code, 404)

    def test_serve_manual_dir_missing(self):
        """測試當手冊目錄不存在時回傳 404 與友善提示"""
        with patch("web_ui.MANUAL_DIR", "/non/existent/manual/dir"):
            response = self.client.get("/manual/")
            self.assertEqual(response.status_code, 404)
            self.assertTrue(b"mdbook build" in response.data or b"404" in response.data)

    @patch("web_ui.load_config", return_value={"streams": []})
    def test_index_page_contains_manual_link(self, mock_load_cfg):
        """測試 Web UI 首頁包含連往 /manual/ 的按鈕連結"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html_text = response.data.decode("utf-8")
        self.assertIn('/manual/', html_text)
        self.assertIn('target="_blank"', html_text)


if __name__ == "__main__":
    unittest.main()
