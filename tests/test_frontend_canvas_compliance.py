"""test_frontend_canvas_compliance.py - 前端畫布渲染邏輯與 SSE Feed 整合測試
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import web_ui


class TestFrontendCanvasCompliance(unittest.TestCase):
    def setUp(self):
        web_ui.app.config["TESTING"] = True
        self.client = web_ui.app.test_client()

    def test_index_template_has_compliance_visualization(self):
        """驗證 index.html 包含工安合規畫布與徽章渲染邏輯"""
        with open(os.path.join("templates", "index.html"), "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("updateZoneBadge(hasAlarmInZone, compSummary)", content)
        self.assertIn("缺少阻隔物", content)
        self.assertIn("工安違規", content)
        self.assertIn("缺失安全阻隔物", content)
        self.assertIn("det.violations", content)
        self.assertIn("合規", content)

    def test_detections_feed_contains_compliance_summary(self):
        """驗證 /detections_feed SSE 傳遞 compliance_summary 與 ppe 欄位"""
        web_ui.LATEST_DETECTIONS = {
            "0": {
                "stream_url": "rtsp://127.0.0.1:8554/cam1",
                "stream_index": 0,
                "label": "Stocker02",
                "detections": [
                    {
                        "xyxy": [100, 200, 300, 600],
                        "cls": 0,
                        "conf": 0.95,
                        "label": "person",
                        "normalized_label": "person",
                        "in_zone": True,
                        "ppe": {"helmet": True, "vest": False},
                        "violations": ["missing_vest"],
                        "is_compliant": False,
                    }
                ],
                "compliance_summary": {
                    "status": "VIOLATION",
                    "violations": ["missing_vest"],
                    "missing_barriers": ["cone"],
                    "external_state": {"stocker_01": "MAINTENANCE"},
                },
                "frame_w": 1920,
                "frame_h": 1080,
                "ts": 1724000000.123,
            }
        }

        resp = self.client.get("/detections_feed")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "text/event-stream")

        raw_data = resp.data.decode("utf-8")
        self.assertTrue(raw_data.startswith("data: "))

        payload_json = raw_data.replace("data: ", "").strip()
        parsed = json.loads(payload_json)

        self.assertIn("0", parsed)
        stream_0 = parsed["0"]
        self.assertEqual(stream_0["compliance_summary"]["status"], "VIOLATION")
        self.assertIn("cone", stream_0["compliance_summary"]["missing_barriers"])
        self.assertEqual(stream_0["detections"][0]["violations"], ["missing_vest"])


if __name__ == "__main__":
    unittest.main()
