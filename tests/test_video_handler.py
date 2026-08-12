import unittest
import os
import sys
import time
from unittest.mock import patch, MagicMock

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from video_handler import VideoHandler


class TestVideoHandler(unittest.TestCase):
    def test_update_and_get_detections(self):
        """測試更新與讀取檢測框的線程安全性"""
        handler = VideoHandler("dummy.mp4")
        test_dets = [{"cls": 0, "conf": 0.9, "xyxy": [[0, 0, 10, 10]]}]
        
        handler.update_detections(test_dets)
        res = handler.get_latest_detections()
        
        self.assertEqual(res, test_dets)
        # 確保返回的是複製列表
        self.assertIsNot(res, test_dets)

    @patch("cv2.VideoCapture")
    def test_video_play_loop(self, mock_cv2_cap):
        """測試 VideoHandler 讀取影片與生成最新幀"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0
        
        import numpy as np
        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, dummy_frame)
        mock_cv2_cap.return_value = mock_cap
        
        handler = VideoHandler("test_video.mp4")
        handler.start()
        
        time.sleep(0.1)
        handler.stop()
        
        # 應成功讀取 frame
        self.assertTrue(mock_cap.read.called)


if __name__ == "__main__":
    unittest.main()
