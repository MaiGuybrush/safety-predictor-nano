import unittest
import json
import web_ui

class TestSseDetections(unittest.TestCase):
    def setUp(self):
        web_ui.app.config['TESTING'] = True
        self.client = web_ui.app.test_client()
        web_ui.LATEST_DETECTIONS = {}

    def test_latest_detections_structure(self):
        web_ui.LATEST_DETECTIONS = {
            0: {
                "stream_url": "rtsp://cam1",
                "stream_index": 0,
                "label": "Cam 1",
                "detections": [{"xyxy": [10, 20, 100, 200], "cls": 0, "conf": 0.9}],
                "frame_w": 640,
                "frame_h": 360,
                "ts": 1700000000.0
            }
        }
        det = web_ui.LATEST_DETECTIONS[0]
        self.assertEqual(det["stream_url"], "rtsp://cam1")
        self.assertEqual(det["stream_index"], 0)
        self.assertEqual(det["label"], "Cam 1")
        self.assertEqual(len(det["detections"]), 1)
        self.assertEqual(det["frame_w"], 640)
        self.assertEqual(det["frame_h"], 360)
        self.assertIn("ts", det)

    def test_sse_endpoint_output_format(self):
        web_ui.LATEST_DETECTIONS = {
            0: {
                "stream_url": "rtsp://cam1",
                "stream_index": 0,
                "label": "Cam 1",
                "detections": [],
                "frame_w": 1280,
                "frame_h": 720,
                "ts": 1700000000.0
            }
        }
        response = self.client.get('/detections_feed')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith('text/event-stream'))
        data = response.get_data(as_text=True)
        self.assertTrue(data.startswith("data: "))
        json_part = data.replace("data: ", "").strip()
        parsed = json.loads(json_part)
        self.assertIn("0", parsed)
        self.assertEqual(parsed["0"]["stream_url"], "rtsp://cam1")

    def test_sse_endpoint_includes_zone_if_present(self):
        web_ui.LATEST_DETECTIONS = {
            0: {
                "stream_url": "rtsp://cam1",
                "stream_index": 0,
                "label": "Cam 1",
                "detections": [],
                "frame_w": 1280,
                "frame_h": 720,
                "ts": 1700000000.0,
                "zone": {
                    "polygon": [[0.1, 0.1], [0.5, 0.5], [0.1, 0.5]],
                    "zone_name": "Danger Zone"
                }
            }
        }
        response = self.client.get('/detections_feed')
        data = response.get_data(as_text=True)
        json_part = data.replace("data: ", "").strip()
        parsed = json.loads(json_part)
        self.assertEqual(parsed["0"]["zone"]["zone_name"], "Danger Zone")
        self.assertEqual(len(parsed["0"]["zone"]["polygon"]), 3)


if __name__ == "__main__":
    unittest.main()

