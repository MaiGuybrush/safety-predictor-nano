"""test_compliance_engine.py - 單元測試：工安合規引擎與 PPE 關聯比對
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from compliance_engine import (
    ComplianceEngine,
    box_area,
    box_intersection,
    box_containment,
    box_iou,
    box_center,
    is_point_in_box,
    DEFAULT_PPE_MAPPING,
)


class TestComplianceEngineGeometry(unittest.TestCase):
    def test_box_area(self):
        self.assertEqual(box_area([0, 0, 10, 10]), 100.0)
        self.assertEqual(box_area([10, 10, 0, 0]), 0.0)
        self.assertEqual(box_area([]), 0.0)

    def test_box_intersection_and_containment(self):
        box_a = [0, 0, 100, 100]
        box_b = [50, 50, 150, 150]
        # 重疊為 [50, 50, 100, 100] -> 50x50 = 2500
        self.assertEqual(box_intersection(box_a, box_b), 2500.0)

        # 包含度：box_inner in box_outer
        box_inner = [20, 20, 40, 40]  # area = 400
        box_outer = [0, 0, 100, 100]   # area = 10000
        self.assertEqual(box_containment(box_inner, box_outer), 1.0)
        self.assertEqual(box_containment(box_outer, box_inner), 400.0 / 10000.0)

    def test_box_iou(self):
        box_a = [0, 0, 10, 10]
        box_b = [0, 0, 10, 10]
        self.assertAlmostEqual(box_iou(box_a, box_b), 1.0)

        box_c = [10, 10, 20, 20]
        self.assertEqual(box_iou(box_a, box_c), 0.0)

    def test_point_in_box(self):
        box = [10, 20, 50, 60]
        self.assertTrue(is_point_in_box((30, 40), box))
        self.assertFalse(is_point_in_box((5, 40), box))
        self.assertEqual(box_center(box), (30.0, 40.0))


class TestComplianceEnginePPE(unittest.TestCase):
    def setUp(self):
        self.engine = ComplianceEngine()

    def test_class_normalization(self):
        engine = ComplianceEngine({"hard_hat": "helmet", "hi_vis": "vest"})
        self.assertEqual(engine.normalize_label("hard_hat"), "helmet")
        self.assertEqual(engine.normalize_label("hi_vis"), "vest")
        self.assertEqual(engine.normalize_label("cone"), "cone")
        self.assertEqual(engine.normalize_label("unknown_obj"), "unknown_obj")

    def test_head_anchor_wearing_helmet(self):
        """測試 head_anchor 模式：人員有 head 且頭部戴 helmet -> 合規"""
        person = {"xyxy": [100, 100, 200, 400], "label": "person", "in_zone": True}
        head = {"xyxy": [130, 110, 170, 160], "label": "head"}
        helmet = {"xyxy": [128, 105, 172, 145], "label": "helmet"}
        vest = {"xyxy": [115, 170, 185, 290], "label": "vest"}

        dets = [person, head, helmet, vest]
        zone = {"zone_name": "Area1", "ppe_strategy": "head_anchor", "required_ppe": ["helmet", "vest"]}

        enriched, events, summary = self.engine.evaluate(dets, stream_zone=zone)

        p = [d for d in enriched if d.get("normalized_label") == "person"][0]
        self.assertTrue(p["ppe"]["helmet"])
        self.assertTrue(p["ppe"]["vest"])
        self.assertTrue(p["is_compliant"])
        self.assertEqual(p["violations"], [])
        self.assertEqual(summary["status"], "COMPLIANT")

    def test_head_anchor_missing_helmet(self):
        """測試 head_anchor 模式：人員有 head 但未戴安全帽 (no_helmet 或無 helmet) -> 違規"""
        person = {"xyxy": [100, 100, 200, 400], "label": "person", "in_zone": True}
        head = {"xyxy": [130, 110, 170, 160], "label": "head"}
        no_helmet = {"xyxy": [130, 110, 170, 150], "label": "no_helmet"}
        vest = {"xyxy": [115, 170, 185, 290], "label": "vest"}

        dets = [person, head, no_helmet, vest]
        zone = {"zone_name": "Area1", "ppe_strategy": "head_anchor", "required_ppe": ["helmet", "vest"]}

        enriched, events, summary = self.engine.evaluate(dets, stream_zone=zone)

        p = [d for d in enriched if d.get("normalized_label") == "person"][0]
        self.assertFalse(p["ppe"]["helmet"])
        self.assertIn("missing_helmet", p["violations"])
        self.assertFalse(p["is_compliant"])
        self.assertEqual(summary["status"], "VIOLATION")

    def test_head_anchor_bending_over_with_helmet(self):
        """測試 head_anchor 模式：人員彎腰作業（未檢測到 head，但檢測到 helmet）-> 合規不誤報"""
        person = {"xyxy": [100, 150, 300, 350], "label": "person", "in_zone": True}
        helmet = {"xyxy": [110, 160, 160, 210], "label": "helmet"}
        vest = {"xyxy": [140, 190, 220, 290], "label": "vest"}

        dets = [person, helmet, vest]
        zone = {"zone_name": "Area1", "ppe_strategy": "head_anchor", "required_ppe": ["helmet", "vest"]}

        enriched, events, summary = self.engine.evaluate(dets, stream_zone=zone)

        p = [d for d in enriched if d.get("normalized_label") == "person"][0]
        self.assertTrue(p["ppe"]["helmet"])
        self.assertTrue(p["ppe"]["vest"])
        self.assertTrue(p["is_compliant"])

    def test_direct_negative_strategy(self):
        """測試 direct_negative 模式：偵測到 no_vest -> 違規 missing_vest"""
        person = {"xyxy": [100, 100, 200, 400], "label": "person", "in_zone": True}
        helmet = {"xyxy": [128, 105, 172, 145], "label": "helmet"}
        no_vest = {"xyxy": [115, 170, 185, 290], "label": "no_vest"}

        dets = [person, helmet, no_vest]
        zone = {"zone_name": "Area1", "ppe_strategy": "direct_negative", "required_ppe": ["helmet", "vest"]}

        enriched, events, summary = self.engine.evaluate(dets, stream_zone=zone)

        p = [d for d in enriched if d.get("normalized_label") == "person"][0]
        self.assertTrue(p["ppe"]["helmet"])
        self.assertFalse(p["ppe"]["vest"])
        self.assertIn("missing_vest", p["violations"])
        self.assertEqual(summary["status"], "VIOLATION")


class TestComplianceEngineRules(unittest.TestCase):
    def setUp(self):
        self.engine = ComplianceEngine()
        self.rules = [
            {
                "id": "maintenance_barrier_rule",
                "name": "機台維護三角錐阻隔規範",
                "enabled": True,
                "when": {
                    "external_state": {
                        "stocker_01": "MAINTENANCE",
                    },
                    "zone": "Stocker_DoorArea",
                    "detected": ["person"],
                },
                "require_any": ["cone", "guardrail"],
                "require_ppe": ["helmet", "vest"],
                "on_violation": {
                    "severity": "HIGH",
                    "category": "safety_barrier_missing",
                },
            }
        ]

    def test_rule_violation_missing_barrier(self):
        """外部狀態 MAINTENANCE，有人進入區域但未放置三角錐或護欄 -> 產生 barrier 違規"""
        person = {"xyxy": [100, 100, 200, 400], "label": "person", "in_zone": True}
        helmet = {"xyxy": [130, 110, 170, 150], "label": "helmet"}
        vest = {"xyxy": [120, 170, 180, 280], "label": "vest"}

        dets = [person, helmet, vest]
        zone = {"zone_name": "Stocker_DoorArea", "ppe_strategy": "direct_negative", "required_ppe": ["helmet", "vest"]}
        ext_states = {"stocker_01": "MAINTENANCE"}

        enriched, events, summary = self.engine.evaluate(
            dets, stream_zone=zone, external_states=ext_states, rules=self.rules
        )

        self.assertEqual(summary["status"], "VIOLATION")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["category"], "safety_barrier_missing")
        self.assertEqual(events[0]["severity"], "HIGH")
        self.assertIn("cone", summary["missing_barriers"])

    def test_rule_compliant_with_cone(self):
        """外部狀態 MAINTENANCE，有人進入且有放置三角錐且穿戴齊全 -> 完全合規"""
        person = {"xyxy": [100, 100, 200, 400], "label": "person", "in_zone": True}
        helmet = {"xyxy": [130, 110, 170, 150], "label": "helmet"}
        vest = {"xyxy": [120, 170, 180, 280], "label": "vest"}
        cone = {"xyxy": [300, 300, 350, 400], "label": "cone"}

        dets = [person, helmet, vest, cone]
        zone = {"zone_name": "Stocker_DoorArea", "ppe_strategy": "direct_negative", "required_ppe": ["helmet", "vest"]}
        ext_states = {"stocker_01": "MAINTENANCE"}

        enriched, events, summary = self.engine.evaluate(
            dets, stream_zone=zone, external_states=ext_states, rules=self.rules
        )

        self.assertEqual(summary["status"], "COMPLIANT")
        self.assertEqual(len(events), 0)
        self.assertEqual(summary["missing_barriers"], [])

    def test_rule_not_triggered_when_state_mismatch(self):
        """外部狀態為 RUNNING 時，維護規則不被觸發"""
        person = {"xyxy": [100, 100, 200, 400], "label": "person", "in_zone": True}
        helmet = {"xyxy": [130, 110, 170, 150], "label": "helmet"}
        vest = {"xyxy": [120, 170, 180, 280], "label": "vest"}

        dets = [person, helmet, vest]
        zone = {"zone_name": "Stocker_DoorArea", "ppe_strategy": "direct_negative", "required_ppe": ["helmet", "vest"]}
        ext_states = {"stocker_01": "RUNNING"}

        enriched, events, summary = self.engine.evaluate(
            dets, stream_zone=zone, external_states=ext_states, rules=self.rules
        )

        self.assertEqual(summary["status"], "COMPLIANT")
        self.assertEqual(len(events), 0)

    def test_evaluation_performance(self):
        """驗證單次比對耗時 < 0.2ms (1000 次耗時 < 200ms)"""
        person = {"xyxy": [100, 100, 200, 400], "label": "person", "in_zone": True}
        head = {"xyxy": [130, 110, 170, 160], "label": "head"}
        helmet = {"xyxy": [128, 105, 172, 145], "label": "helmet"}
        vest = {"xyxy": [115, 170, 185, 290], "label": "vest"}
        cone = {"xyxy": [300, 300, 350, 400], "label": "cone"}
        dets = [person, head, helmet, vest, cone]
        zone = {"zone_name": "Stocker_DoorArea", "ppe_strategy": "head_anchor", "required_ppe": ["helmet", "vest"]}
        ext_states = {"stocker_01": "MAINTENANCE"}

        start = time.time()
        for _ in range(1000):
            self.engine.evaluate(dets, stream_zone=zone, external_states=ext_states, rules=self.rules)
        elapsed = time.time() - start

        # 1000 次應在 0.2 秒以內 (< 0.2ms/次)
        self.assertLess(elapsed, 0.2, f"1000 evaluations took {elapsed:.4f}s, expected < 0.2s")


if __name__ == "__main__":
    unittest.main()
