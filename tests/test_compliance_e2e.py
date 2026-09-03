"""test_compliance_e2e.py - 整合與端對端測試：主流程、合規引擎與事件日誌管道
"""

import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import event_producer
from compliance_engine import ComplianceEngine
from state_poller import StatePoller, GLOBAL_STATE_POLLER
import web_ui


class TestComplianceE2E(unittest.TestCase):
    def setUp(self):
        # 重置 event_producer 內部狀態
        event_producer._state.clear()
        while not event_producer.event_queue.empty():
            try:
                event_producer.event_queue.get_nowait()
            except Exception:
                break
        while not event_producer._snapshot_queue.empty():
            try:
                event_producer._snapshot_queue.get_nowait()
            except Exception:
                break

        self.engine = ComplianceEngine()
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        event_producer._state.clear()

    def test_e2e_person_missing_helmet_generates_event_and_snapshot(self):
        """端對端測試：區域內人員未戴安全帽，產生 EventStart 與 快照請求"""
        frame_w, frame_h = 1920, 1080
        clean_frame = MagicMock()
        clean_frame.copy.return_value = clean_frame

        zone = {
            "zone_name": "StockerArea",
            "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            "trigger_mode": "center",
            "sensitivity": 0.0,
            "ppe_strategy": "head_anchor",
            "required_ppe": ["helmet"],
        }

        # 人員在區域內且有 head 但無 helmet
        detections = [
            {"xyxy": [500, 500, 700, 900], "label": "person", "conf": 0.9, "in_zone": True},
            {"xyxy": [550, 510, 650, 600], "label": "head", "conf": 0.85, "in_zone": True},
            {"xyxy": [550, 510, 650, 580], "label": "no_helmet", "conf": 0.88, "in_zone": True},
        ]

        enriched, events, summary = self.engine.evaluate(detections, stream_zone=zone)

        self.assertEqual(summary["status"], "VIOLATION")
        self.assertIn("missing_helmet", summary["violations"])

        # 送入 event_producer 處理
        event_producer.process_detections(
            0, "cam_stocker",
            enriched, frame_w, frame_h,
            zone=zone, pts=1724000000.0,
            clean_frame=clean_frame,
            base_dir=self.tmp_dir,
        )

        event_producer.process_compliance_events(
            0, "cam_stocker",
            events or [{"category": "missing_helmet", "severity": "HIGH"}],
            frame_w, frame_h,
            zone=zone, pts=1724000000.0,
            clean_frame=clean_frame,
            base_dir=self.tmp_dir,
        )

        # 檢查 event_queue
        queued_events = []
        while not event_producer.event_queue.empty():
            queued_events.append(event_producer.event_queue.get_nowait())

        start_events = [e for e in queued_events if isinstance(e, event_producer.EventStart)]
        self.assertTrue(any(e.category == "missing_helmet" for e in start_events))

    def test_e2e_declarative_rules_trigger_and_resolution(self):
        """端對端測試：外部狀態連動工安規則，阻隔物缺失觸發事件，恢復後正常結束"""
        frame_w, frame_h = 1920, 1080
        rules = [
            {
                "id": "maintenance_barrier_rule",
                "name": "機台維護三角錐阻隔規範",
                "enabled": True,
                "when": {
                    "external_state": {"stocker_01": "MAINTENANCE"},
                    "zone": "StockerArea",
                    "detected": ["person"],
                },
                "require_any": ["cone"],
                "on_violation": {"severity": "CRITICAL", "category": "safety_barrier_missing"},
            }
        ]

        zone = {
            "zone_name": "StockerArea",
            "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            "ppe_strategy": "direct_negative",
            "required_ppe": ["helmet"],
        }

        # 1. 外部狀態設為 MAINTENANCE
        ext_states = {"stocker_01": "MAINTENANCE"}

        # 畫面中有人員但無 cone
        detections = [
            {"xyxy": [500, 500, 700, 900], "label": "person", "conf": 0.9, "in_zone": True},
            {"xyxy": [550, 510, 650, 580], "label": "helmet", "conf": 0.9, "in_zone": True},
        ]

        enriched, events, summary = self.engine.evaluate(
            detections, stream_zone=zone, external_states=ext_states, rules=rules
        )

        self.assertEqual(summary["status"], "VIOLATION")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["category"], "safety_barrier_missing")

        event_producer.process_compliance_events(
            0, "cam_stocker",
            events, frame_w, frame_h,
            zone=zone, pts=1724000000.0,
        )

        # 檢查 EventStart 產生
        queued = []
        while not event_producer.event_queue.empty():
            queued.append(event_producer.event_queue.get_nowait())
        self.assertTrue(any(isinstance(e, event_producer.EventStart) and e.category == "safety_barrier_missing" for e in queued))

        # 2. 次一幀放置了 cone -> 違規解除
        detections_with_cone = [
            {"xyxy": [500, 500, 700, 900], "label": "person", "conf": 0.9, "in_zone": True},
            {"xyxy": [550, 510, 650, 580], "label": "helmet", "conf": 0.9, "in_zone": True},
            {"xyxy": [300, 300, 400, 400], "label": "cone", "conf": 0.9, "in_zone": True},
        ]

        enriched2, events2, summary2 = self.engine.evaluate(
            detections_with_cone, stream_zone=zone, external_states=ext_states, rules=rules
        )
        self.assertEqual(summary2["status"], "COMPLIANT")
        self.assertEqual(len(events2), 0)

        # 連續 3 幀無違規，達到 tolerance 閾值
        for _ in range(3):
            event_producer.process_compliance_events(
                0, "cam_stocker",
                events2, frame_w, frame_h,
                zone=zone, pts=1724000001.0,
                tolerance=2,
            )

        queued_end = []
        while not event_producer.event_queue.empty():
            queued_end.append(event_producer.event_queue.get_nowait())

        self.assertTrue(any(isinstance(e, event_producer.EventEnd) for e in queued_end))


if __name__ == "__main__":
    unittest.main()
