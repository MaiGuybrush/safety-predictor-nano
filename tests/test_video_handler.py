import unittest
import os
import sys
import time
import cv2
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

    @patch("cv2.VideoCapture")
    def test_eof_rewind_loop(self, mock_cv2_cap):
        """測試 EOF 時自動重置影格指標倒帶播放"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 1000.0  # high FPS for fast loop execution in test
        
        import numpy as np
        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        # 第一次 read 回傳 False (EOF)，倒帶重試 read 回傳 True
        mock_cap.read.side_effect = [(False, None)] + [(True, dummy_frame)] * 200
        mock_cv2_cap.return_value = mock_cap
        
        handler = VideoHandler("test_eof.mp4")
        handler.update_detections([{"cls": 0, "conf": 0.85, "xyxy": [10, 10, 50, 50]}])
        handler.start()
        
        time.sleep(0.05)
        handler.stop()
        
        mock_cap.set.assert_called_with(cv2.CAP_PROP_POS_FRAMES, 0)

if __name__ == "__main__":
    unittest.main()
