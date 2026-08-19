import unittest
import web_ui
from web_ui import app, register_video_client, unregister_video_client, is_streaming_active

class TestOnDemandStreaming(unittest.TestCase):
    def setUp(self):
        # 重設計數器
        with web_ui._clients_lock:
            web_ui.ACTIVE_VIDEO_CLIENTS = 0
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_client_counter_lifecycle(self):
        self.assertFalse(is_streaming_active())
        self.assertEqual(web_ui.ACTIVE_VIDEO_CLIENTS, 0)

        register_video_client()
        self.assertTrue(is_streaming_active())
        self.assertEqual(web_ui.ACTIVE_VIDEO_CLIENTS, 1)

        register_video_client()
        self.assertEqual(web_ui.ACTIVE_VIDEO_CLIENTS, 2)

        unregister_video_client()
        self.assertEqual(web_ui.ACTIVE_VIDEO_CLIENTS, 1)

        unregister_video_client()
        self.assertFalse(is_streaming_active())
        self.assertEqual(web_ui.ACTIVE_VIDEO_CLIENTS, 0)

        # 測試防止負數
        unregister_video_client()
        self.assertEqual(web_ui.ACTIVE_VIDEO_CLIENTS, 0)
        self.assertFalse(is_streaming_active())

    def test_video_feed_endpoint_increments_and_decrements(self):
        self.assertFalse(is_streaming_active())
        response = self.client.get('/video_feed')
        self.assertEqual(response.status_code, 200)
        # 串流被建立時應為活躍狀態
        self.assertTrue(is_streaming_active())
        # 關閉 response 連線，觸發 finally 區塊
        response.close()
        self.assertFalse(is_streaming_active())

    def test_single_stream_feed_increments_and_decrements(self):
        self.assertFalse(is_streaming_active())
        response = self.client.get('/video_feed/0')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(is_streaming_active())
        response.close()
        self.assertFalse(is_streaming_active())

if __name__ == '__main__':
    unittest.main()
