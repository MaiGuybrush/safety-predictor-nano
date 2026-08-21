import os
import tempfile
import unittest
from unittest.mock import patch

import web_ui


class TestLogViewerHtmlElements(unittest.TestCase):
    """驗證 Log Viewer Modal 所需 HTML 元件存在於頁面中"""

    def setUp(self):
        web_ui.app.config['TESTING'] = True
        self.client = web_ui.app.test_client()

    @patch('web_ui.load_config', return_value={'streams': []})
    def test_log_viewer_button_exists(self, _mock):
        """頂部導覽列應存在日誌檢視按鈕"""
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('log-viewer-btn', html)
        self.assertIn('openLogViewer', html)

    @patch('web_ui.load_config', return_value={'streams': []})
    def test_log_viewer_modal_overlay_exists(self, _mock):
        """頁面應包含 log-viewer-overlay 元素"""
        resp = self.client.get('/')
        html = resp.data.decode('utf-8')
        self.assertIn('log-viewer-overlay', html)

    @patch('web_ui.load_config', return_value={'streams': []})
    def test_log_viewer_modal_exists(self, _mock):
        """頁面應包含 log-viewer-modal 元素"""
        resp = self.client.get('/')
        html = resp.data.decode('utf-8')
        self.assertIn('log-viewer-modal', html)

    @patch('web_ui.load_config', return_value={'streams': []})
    def test_log_source_select_exists(self, _mock):
        """頁面應包含日誌來源下拉選單"""
        resp = self.client.get('/')
        html = resp.data.decode('utf-8')
        self.assertIn('log-source-select', html)

    @patch('web_ui.load_config', return_value={'streams': []})
    def test_log_source_options_all_three(self, _mock):
        """下拉選單應包含 system, performance, detections 三個選項"""
        resp = self.client.get('/')
        html = resp.data.decode('utf-8')
        for val in ('system', 'performance', 'detections'):
            self.assertIn(f'value="{val}"', html, f'Missing option: {val}')

    @patch('web_ui.load_config', return_value={'streams': []})
    def test_log_refresh_button_exists(self, _mock):
        """頁面應包含重新整理按鈕"""
        resp = self.client.get('/')
        html = resp.data.decode('utf-8')
        self.assertIn('log-refresh-btn', html)
        self.assertIn('loadLogContent', html)

    @patch('web_ui.load_config', return_value={'streams': []})
    def test_log_autoscroll_checkbox_exists(self, _mock):
        """頁面應包含自動捲動 checkbox"""
        resp = self.client.get('/')
        html = resp.data.decode('utf-8')
        self.assertIn('log-autoscroll', html)

    @patch('web_ui.load_config', return_value={'streams': []})
    def test_log_copy_button_exists(self, _mock):
        """頁面應包含複製按鈕"""
        resp = self.client.get('/')
        html = resp.data.decode('utf-8')
        self.assertIn('log-copy-btn', html)
        self.assertIn('copyLogContent', html)

    @patch('web_ui.load_config', return_value={'streams': []})
    def test_log_content_area_exists(self, _mock):
        """頁面應包含日誌內容顯示區域"""
        resp = self.client.get('/')
        html = resp.data.decode('utf-8')
        self.assertIn('log-content-area', html)

    @patch('web_ui.load_config', return_value={'streams': []})
    def test_close_button_and_esc_js_exist(self, _mock):
        """頁面應包含關閉 Modal 的 JS 函式"""
        resp = self.client.get('/')
        html = resp.data.decode('utf-8')
        self.assertIn('closeLogViewer', html)

    @patch('web_ui.load_config', return_value={'streams': []})
    def test_overlay_click_closes_modal(self, _mock):
        """點擊遮罩應有 handleLogOverlayClick 處理"""
        resp = self.client.get('/')
        html = resp.data.decode('utf-8')
        self.assertIn('handleLogOverlayClick', html)


class TestLogViewerApiIntegration(unittest.TestCase):
    """驗證 /api/logs 端點行為（與 Log Viewer 整合）"""

    def setUp(self):
        web_ui.app.config['TESTING'] = True
        self.client = web_ui.app.test_client()
        self.tmpdir = tempfile.mkdtemp()
        self.system_log = os.path.join(self.tmpdir, 'system.log')

    def _mock_config(self):
        return {
            'system_log_file': self.system_log,
            'log_file': os.path.join(self.tmpdir, 'performance.log'),
            'detection_log_file': os.path.join(self.tmpdir, 'detections.log'),
        }

    def test_log_viewer_calls_api_logs_system(self):
        """GET /api/logs?file=system 回傳正確結構"""
        with open(self.system_log, 'w', encoding='utf-8') as f:
            f.write('test log line\n')
        with patch('web_ui.load_config', return_value=self._mock_config()):
            resp = self.client.get('/api/logs?file=system&lines=300')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn('test log line', data['content'])

    def test_log_viewer_handles_empty_log(self):
        """日誌不存在時回傳 200 + 空 content（Modal 可顯示提示）"""
        with patch('web_ui.load_config', return_value=self._mock_config()):
            resp = self.client.get('/api/logs?file=system')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['content'], '')


if __name__ == '__main__':
    unittest.main()
