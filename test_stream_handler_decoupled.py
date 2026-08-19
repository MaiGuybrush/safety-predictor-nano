import unittest
from unittest.mock import MagicMock, patch
import time
import numpy as np
import web_ui
from stream_handler import StreamHandler

class TestStreamHandlerDecoupled(unittest.TestCase):
    def setUp(self):
        with web_ui._clients_lock:
            web_ui.ACTIVE_VIDEO_CLIENTS = 0

    @patch('cv2.VideoCapture')
    def test_decoupled_decoding_sampling_rate(self, mock_vc_cls):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.grab.return_value = True
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.retrieve.return_value = (True, dummy_frame)
        mock_vc_cls.return_value = mock_cap

        # 設定 fps_limit = 2 (每 0.5s 解碼一次)
        handler = StreamHandler("rtsp://test/stream", fps_limit=2)
        handler.start()

        # 讓它運行 0.2 秒（預期在無連線時，至多 retrieve 1 次，但 grab 會被呼叫很多次）
        time.sleep(0.2)
        handler.stop()

        self.assertGreater(mock_cap.grab.call_count, 10, "grab 應高頻執行以清空 buffer")
        self.assertLessEqual(mock_cap.retrieve.call_count, 2, "無連線時 retrieve 次數應受到 fps_limit 節流限制")

    @patch('cv2.VideoCapture')
    def test_active_streaming_full_rate_retrieve(self, mock_vc_cls):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.grab.return_value = True
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.retrieve.return_value = (True, dummy_frame)
        mock_vc_cls.return_value = mock_cap

        # 模擬有活躍 Web UI 連線
        web_ui.register_video_client()
        self.assertTrue(web_ui.is_streaming_active())

        handler = StreamHandler("rtsp://test/stream", fps_limit=2)
        handler.start()

        time.sleep(0.1)
        handler.stop()
        web_ui.unregister_video_client()

        # 有連線時，每次 grab 成功都應調用 retrieve
        self.assertGreater(mock_cap.retrieve.call_count, 5, "有連線時應全速調用 retrieve")
        self.assertEqual(mock_cap.grab.call_count, mock_cap.retrieve.call_count)

if __name__ == '__main__':
    unittest.main()
