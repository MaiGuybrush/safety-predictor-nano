import unittest
from unittest.mock import MagicMock
import cv2
import numpy as np
import web_ui

class TestMjpegRelay(unittest.TestCase):
    def setUp(self):
        web_ui.app.config['TESTING'] = True
        self.client = web_ui.app.test_client()

    def test_single_stream_feed_out_of_bounds(self):
        # STREAM_UNITS is empty
        web_ui.STREAM_UNITS = []
        response = self.client.get('/video_feed/99')
        self.assertEqual(response.status_code, 200)
        self.assertIn('multipart/x-mixed-replace', response.content_type)
        # Should yield NO_SIGNAL_FRAME
        data = response.get_data()
        self.assertTrue(len(data) > 0)
        self.assertIn(b'--frame', data)
        self.assertIn(b'image/jpeg', data)

    def test_single_stream_feed_valid_unit(self):
        sample_frame = np.zeros((360, 640, 3), dtype=np.uint8)
        unit = {"latest_raw_frame": sample_frame, "url": "rtsp://test", "label": "Cam1"}
        web_ui.STREAM_UNITS = [unit]
        
        response = self.client.get('/video_feed/0')
        self.assertEqual(response.status_code, 200)
        self.assertIn('multipart/x-mixed-replace', response.content_type)
        data = response.get_data()
        self.assertTrue(len(data) > 0)
        self.assertIn(b'image/jpeg', data)

if __name__ == "__main__":
    unittest.main()

