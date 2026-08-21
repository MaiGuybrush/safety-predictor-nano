import os
import tempfile
import unittest
from unittest.mock import patch

import web_ui


class TestLogApi(unittest.TestCase):
    def setUp(self):
        web_ui.app.config['TESTING'] = True
        self.client = web_ui.app.test_client()
        self.tmpdir = tempfile.mkdtemp()
        self.system_log = os.path.join(self.tmpdir, 'system.log')
        self.perf_log = os.path.join(self.tmpdir, 'performance.log')
        self.det_log = os.path.join(self.tmpdir, 'detections.log')

    def _mock_config(self):
        return {
            'system_log_file': self.system_log,
            'log_file': self.perf_log,
            'detection_log_file': self.det_log,
        }

    def test_get_system_log_returns_200(self):
        with open(self.system_log, 'w', encoding='utf-8') as f:
            for i in range(10):
                f.write(f'line {i}\n')
        with patch('web_ui.load_config', return_value=self._mock_config()):
            resp = self.client.get('/api/logs?file=system&lines=5')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['file_type'], 'system')
        self.assertEqual(data['lines'], 5)
        self.assertIn('line 9', data['content'])

    def test_get_performance_log(self):
        with open(self.perf_log, 'w', encoding='utf-8') as f:
            f.write('perf data\n')
        with patch('web_ui.load_config', return_value=self._mock_config()):
            resp = self.client.get('/api/logs?file=performance')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['file_type'], 'performance')
        self.assertIn('perf data', data['content'])

    def test_get_detections_log(self):
        with open(self.det_log, 'w', encoding='utf-8') as f:
            f.write('detection event\n')
        with patch('web_ui.load_config', return_value=self._mock_config()):
            resp = self.client.get('/api/logs?file=detections')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['file_type'], 'detections')

    def test_invalid_file_param_returns_400(self):
        resp = self.client.get('/api/logs?file=invalid')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data['status'], 'error')

    def test_path_traversal_dot_dot_returns_400(self):
        resp = self.client.get('/api/logs?file=../../etc/passwd')
        self.assertEqual(resp.status_code, 400)

    def test_path_traversal_slash_returns_400(self):
        resp = self.client.get('/api/logs?file=/etc/shadow')
        self.assertEqual(resp.status_code, 400)

    def test_file_not_exist_returns_200_empty_content(self):
        with patch('web_ui.load_config', return_value=self._mock_config()):
            resp = self.client.get('/api/logs?file=system')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['content'], '')

    def test_lines_capped_at_1000(self):
        with open(self.system_log, 'w', encoding='utf-8') as f:
            for i in range(50):
                f.write(f'line {i}\n')
        with patch('web_ui.load_config', return_value=self._mock_config()):
            resp = self.client.get('/api/logs?file=system&lines=9999')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertLessEqual(data['lines'], 1000)

    def test_default_lines_is_200(self):
        with open(self.system_log, 'w', encoding='utf-8') as f:
            for i in range(300):
                f.write(f'line {i}\n')
        with patch('web_ui.load_config', return_value=self._mock_config()):
            resp = self.client.get('/api/logs?file=system')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['lines'], 200)

    def test_response_json_structure(self):
        """JSON 結構必須包含 status, file_type, file_path, lines, content"""
        with open(self.system_log, 'w', encoding='utf-8') as f:
            f.write('test\n')
        with patch('web_ui.load_config', return_value=self._mock_config()):
            resp = self.client.get('/api/logs?file=system')
        data = resp.get_json()
        for key in ('status', 'file_type', 'file_path', 'lines', 'content'):
            self.assertIn(key, data, f'missing key: {key}')


if __name__ == '__main__':
    unittest.main()
