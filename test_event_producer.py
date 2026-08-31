import queue
import unittest

import event_producer
from argus_eventlog.writer import event_queue as global_event_queue


def _drain_queue(q):
    while not q.empty():
        try:
            q.get_nowait()
            q.task_done()
        except queue.Empty:
            break


def _det(label, xyxy=(0.0, 0.0, 10.0, 10.0)):
    return {"xyxy": list(xyxy), "cls": 0, "conf": 0.9, "label": label}


class TestEventProducer(unittest.TestCase):
    def setUp(self):
        _drain_queue(global_event_queue)
        event_producer._state.clear()

    def tearDown(self):
        _drain_queue(global_event_queue)
        event_producer._state.clear()

    def _actions(self):
        items = []
        while not global_event_queue.empty():
            items.append(global_event_queue.get_nowait())
        return items

    def test_appear_persist_disappear_full_lifecycle(self):
        event_producer.process_detections("s0", "CCD1", [_det("no_helmet")], 100, 100, tolerance=2)
        actions = [type(a).__name__ for a in self._actions()]
        self.assertEqual(actions, ["EventStart", "EventFrame"])

        event_producer.process_detections("s0", "CCD1", [_det("no_helmet")], 100, 100, tolerance=2)
        actions = [type(a).__name__ for a in self._actions()]
        self.assertEqual(actions, ["EventFrame"])

        # absent 1, 2 -> still within tolerance, no end yet
        event_producer.process_detections("s0", "CCD1", [], 100, 100, tolerance=2)
        self.assertEqual(self._actions(), [])
        event_producer.process_detections("s0", "CCD1", [], 100, 100, tolerance=2)
        self.assertEqual(self._actions(), [])

        # absent 3 -> exceeds tolerance=2, end fires
        event_producer.process_detections("s0", "CCD1", [], 100, 100, tolerance=2)
        actions = self._actions()
        self.assertEqual([type(a).__name__ for a in actions], ["EventEnd"])
        self.assertEqual(actions[0].reason, "no_longer_detected")

    def test_event_ref_stable_across_frames(self):
        event_producer.process_detections("s0", "CCD1", [_det("fall")], 100, 100)
        start = self._actions()[0]
        event_producer.process_detections("s0", "CCD1", [_det("fall")], 100, 100)
        frame = self._actions()[0]
        self.assertEqual(start.event_ref, frame.event_ref)

    def test_absence_within_tolerance_keeps_event_open(self):
        event_producer.process_detections("s0", "CCD1", [_det("fall")], 100, 100, tolerance=3)
        self._actions()
        event_producer.process_detections("s0", "CCD1", [], 100, 100, tolerance=3)
        event_producer.process_detections("s0", "CCD1", [], 100, 100, tolerance=3)
        self._actions()
        self.assertIn(("s0", "fall"), event_producer._state)

    def test_two_labels_same_stream_track_independently(self):
        event_producer.process_detections(
            "s0", "CCD1", [_det("no_helmet"), _det("zone_intrusion")], 100, 100
        )
        actions = self._actions()
        starts = [a for a in actions if type(a).__name__ == "EventStart"]
        self.assertEqual({s.category for s in starts}, {"no_helmet", "zone_intrusion"})
        self.assertNotEqual(starts[0].event_ref, starts[1].event_ref)

    def test_severity_map_overrides_default(self):
        event_producer.process_detections(
            "s0", "CCD1", [_det("no_helmet")], 100, 100, severity_map={"no_helmet": "critical"}
        )
        start = self._actions()[0]
        self.assertEqual(start.severity, "critical")

    def test_unmapped_label_defaults_to_warning(self):
        event_producer.process_detections("s0", "CCD1", [_det("unknown_thing")], 100, 100)
        start = self._actions()[0]
        self.assertEqual(start.severity, "warning")

    def test_bbox_normalized_to_frame_size(self):
        event_producer.process_detections(
            "s0", "CCD1", [_det("person", xyxy=(10, 20, 30, 60))], 100, 200
        )
        frame = self._actions()[1]
        box = frame.detections[0]
        self.assertAlmostEqual(box.x, 0.1)
        self.assertAlmostEqual(box.y, 0.1)
        self.assertAlmostEqual(box.w, 0.2)
        self.assertAlmostEqual(box.h, 0.2)

    def test_zone_filtering_drops_detections_outside_polygon(self):
        zone = {
            "polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
            "zone_name": "Danger Zone"
        }
        # Center is (7.5, 7.5) -> (0.075, 0.075), outside [0.2, 0.8]
        event_producer.process_detections("s0", "CCD1", [_det("person", xyxy=(5, 5, 10, 10))], 100, 100, zone=zone)
        self.assertEqual(self._actions(), [])
        self.assertEqual(len(event_producer._state), 0)

    def test_zone_filtering_allows_detections_inside_polygon_and_sets_meta(self):
        zone = {
            "polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
            "zone_name": "機台危險區"
        }
        # Center is (50, 50) -> (0.5, 0.5), inside
        event_producer.process_detections("s0", "CCD1", [_det("no_helmet", xyxy=(40, 40, 60, 60))], 100, 100, zone=zone)
        actions = self._actions()
        self.assertEqual(len(actions), 2)
        start = actions[0]
        self.assertEqual(type(start).__name__, "EventStart")
        self.assertEqual(start.category, "no_helmet")
        self.assertEqual(start.meta.roi, zone["polygon"])
        self.assertEqual(start.meta.zone_name, "機台危險區")

    def test_zone_none_or_empty_preserves_full_frame_roi(self):
        event_producer.process_detections("s0", "CCD1", [_det("fall", xyxy=(5, 5, 10, 10))], 100, 100, zone=None)
        actions = self._actions()
        start = actions[0]
        self.assertEqual(start.meta.roi, event_producer._FULL_FRAME_ROI)
        self.assertIsNone(start.meta.zone_name)

    def test_zone_filtering_mixed_detections(self):
        zone = {
            "polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
        }
        # det1 inside, det2 outside
        det_inside = _det("no_helmet", xyxy=(40, 40, 60, 60))
        det_outside = _det("no_vest", xyxy=(5, 5, 10, 10))
        event_producer.process_detections("s0", "CCD1", [det_inside, det_outside], 100, 100, zone=zone)
        actions = self._actions()
        starts = [a for a in actions if type(a).__name__ == "EventStart"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0].category, "no_helmet")

    def test_intersect_mode_triggers_when_center_outside_but_border_overlaps(self):
        zone = {
            "polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
            "zone_name": "Danger Zone",
            "trigger_mode": "intersect",
            "sensitivity": 0.0
        }
        # Bbox: (10, 10, 25, 25) on 100x100 -> [0.1, 0.1, 0.25, 0.25]
        # Center is (0.175, 0.175) -> OUTSIDE [0.2, 0.8]
        # Overlap region is [0.2, 0.25] x [0.2, 0.25] -> INTERSECTS
        det = _det("person", xyxy=(10, 10, 25, 25))

        # Under center mode: should be filtered out
        center_zone = dict(zone, trigger_mode="center")
        event_producer.process_detections("s0", "CCD1", [det], 100, 100, zone=center_zone)
        self.assertEqual(self._actions(), [])

        # Under intersect mode with sensitivity=0.0: should trigger
        event_producer.process_detections("s0", "CCD1", [det], 100, 100, zone=zone)
        actions = self._actions()
        self.assertEqual(len(actions), 2)
        start = actions[0]
        self.assertEqual(start.category, "person")

    def test_intersect_mode_sensitivity_threshold(self):
        zone = {
            "polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
            "trigger_mode": "intersect",
            "sensitivity": 0.6  # Requires 60% overlap
        }
        # Bbox: (10, 40, 30, 60) on 100x100 -> [0.1, 0.4, 0.3, 0.6]
        # Bbox Area = 0.2 * 0.2 = 0.04
        # Overlap with ROI [0.2, 0.8] is [0.2, 0.3] x [0.4, 0.6] -> Area = 0.1 * 0.2 = 0.02
        # Overlap ratio = 0.02 / 0.04 = 0.5 (50%)
        det = _det("forklift", xyxy=(10, 40, 30, 60))

        # 50% < 60% -> Suppressed
        event_producer.process_detections("s0", "CCD1", [det], 100, 100, zone=zone)
        self.assertEqual(self._actions(), [])

        # 50% >= 40% -> Triggered
        zone_low_sens = dict(zone, sensitivity=0.4)
        event_producer.process_detections("s0", "CCD1", [det], 100, 100, zone=zone_low_sens)
        actions = self._actions()
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0].category, "forklift")

    def test_intersect_mode_completely_outside_does_not_trigger(self):
        zone = {
            "polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
            "trigger_mode": "intersect",
            "sensitivity": 0.0
        }
        det = _det("worker", xyxy=(0, 0, 10, 10))
        event_producer.process_detections("s0", "CCD1", [det], 100, 100, zone=zone)
        self.assertEqual(self._actions(), [])


    def test_timestamp_format_with_valid_pts(self):
        # PTS 1724916964.404 -> 2024-08-29T07:36:04.404Z
        pts = 1724916964.404
        event_producer.process_detections("s0", "CCD1", [_det("person")], 100, 100, pts=pts)
        actions = self._actions()
        self.assertEqual(len(actions), 2)
        start = actions[0]
        frame = actions[1]
        self.assertEqual(start.timestamp, "2024-08-29T07:36:04.404Z")
        self.assertEqual(frame.timestamp, "2024-08-29T07:36:04.404Z")

    def test_timestamp_format_fallback_when_pts_invalid_or_none(self):
        import re
        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
        
        # Test with pts=None
        event_producer.process_detections("s0", "CCD1", [_det("person")], 100, 100, pts=None)
        start = self._actions()[0]
        self.assertRegex(start.timestamp, iso_pattern)

        # Test with pts <= 0
        event_producer._state.clear()
        event_producer.process_detections("s0", "CCD1", [_det("person")], 100, 100, pts=0)
        start = self._actions()[0]
        self.assertRegex(start.timestamp, iso_pattern)

        # Test with pts negative
        event_producer._state.clear()
        event_producer.process_detections("s0", "CCD1", [_det("person")], 100, 100, pts=-1.5)
        start = self._actions()[0]
        self.assertRegex(start.timestamp, iso_pattern)

        # Test with relative PTS (e.g. 3.652s or 109.966s from OpenCV CAP_PROP_POS_MSEC) -> must fallback to system time (not 1970)
        event_producer._state.clear()
        event_producer.process_detections("s0", "CCD1", [_det("person")], 100, 100, pts=3.652)
        start = self._actions()[0]
        self.assertRegex(start.timestamp, iso_pattern)
        self.assertFalse(start.timestamp.startswith("1970"))

        event_producer._state.clear()
        event_producer.process_detections("s0", "CCD1", [_det("person")], 100, 100, pts=109.966)
        start = self._actions()[0]
        self.assertRegex(start.timestamp, iso_pattern)
        self.assertFalse(start.timestamp.startswith("1970"))

    def test_relative_pts_frame_sequence_fallback(self):
        # Frame 1: pts=0 (fallback to system time)
        event_producer.process_detections("s0", "CCD1", [_det("person")], 100, 100, pts=0)
        actions = self._actions()
        start = actions[0]
        self.assertFalse(start.timestamp.startswith("1970"))

        # Frame 2: relative pts=3.652s (must fallback to system time and not produce 1970)
        event_producer.process_detections("s0", "CCD1", [_det("person")], 100, 100, pts=3.652)
        actions = self._actions()
        frame = actions[0]
        self.assertFalse(frame.timestamp.startswith("1970"))

    def test_snapshot_taken_on_event_start_and_linked_in_metadata(self):
        import numpy as np
        import tempfile
        import os
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            dummy_clean_frame = np.zeros((100, 100, 3), dtype=np.uint8)
            pts = 1724916964.404

            event_producer.process_detections(
                "s0", "CCD1", [_det("person")], 100, 100,
                pts=pts, clean_frame=dummy_clean_frame, base_dir=tmpdir
            )
            actions = self._actions()
            start = actions[0]
            
            # 檢查 metadata snapshot_path
            self.assertIsNotNone(start.meta.snapshot_path)
            self.assertTrue(start.meta.snapshot_path.startswith("snapshots/1724916964.404_person_"))
            self.assertTrue(start.meta.snapshot_path.endswith(".jpg"))

            # 檢查 JSONL 序列化字典包含 snapshot_path
            d = start.to_dict()
            self.assertIn("snapshot_path", d["meta"])
            self.assertEqual(d["meta"]["snapshot_path"], start.meta.snapshot_path)

            # 等待非同步截圖寫入完成
            expected_disk_path = os.path.join(tmpdir, "CCD1", start.meta.snapshot_path.replace("/", os.sep))
            for _ in range(20):
                if os.path.exists(expected_disk_path):
                    break
                time.sleep(0.05)
            self.assertTrue(os.path.exists(expected_disk_path), f"截圖檔案應存在於 {expected_disk_path}")

    def test_snapshot_deduplication_during_event_frames(self):
        import numpy as np
        import tempfile
        import os
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
            pts1 = 1724916964.404
            pts2 = 1724916965.404

            # First frame -> EventStart + Snapshot
            event_producer.process_detections(
                "s0", "CCD1", [_det("person")], 100, 100,
                pts=pts1, clean_frame=dummy_frame, base_dir=tmpdir
            )
            start_actions = self._actions()
            self.assertEqual([type(a).__name__ for a in start_actions], ["EventStart", "EventFrame"])

            # Second frame -> EventFrame (No new snapshot created)
            event_producer.process_detections(
                "s0", "CCD1", [_det("person")], 100, 100,
                pts=pts2, clean_frame=dummy_frame, base_dir=tmpdir
            )
            frame_actions = self._actions()
            self.assertEqual([type(a).__name__ for a in frame_actions], ["EventFrame"])

            time.sleep(0.1)
            snapshots_dir = os.path.join(tmpdir, "CCD1", "snapshots")
            self.assertTrue(os.path.exists(snapshots_dir))
            files = os.listdir(snapshots_dir)
            self.assertEqual(len(files), 1, "事件持續期間不應重複產生截圖")

    def test_snapshot_retriggered_after_event_end(self):
        import numpy as np
        import tempfile
        import os
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
            pts1 = 1724916964.404

            # Event 1 starts
            event_producer.process_detections(
                "s0", "CCD1", [_det("person")], 100, 100,
                pts=pts1, clean_frame=dummy_frame, base_dir=tmpdir, tolerance=1
            )
            self._actions()

            # Disappear -> EventEnd
            event_producer.process_detections("s0", "CCD1", [], 100, 100, pts=pts1+1, tolerance=1)
            event_producer.process_detections("s0", "CCD1", [], 100, 100, pts=pts1+2, tolerance=1)
            end_actions = self._actions()
            self.assertEqual([type(a).__name__ for a in end_actions], ["EventEnd"])

            # Event 2 starts (new EventStart & new snapshot)
            pts2 = 1724916970.000
            event_producer.process_detections(
                "s0", "CCD1", [_det("person")], 100, 100,
                pts=pts2, clean_frame=dummy_frame, base_dir=tmpdir, tolerance=1
            )
            re_start_actions = self._actions()
            self.assertEqual([type(a).__name__ for a in re_start_actions], ["EventStart", "EventFrame"])
            self.assertIn("1724916970.000_person_", re_start_actions[0].meta.snapshot_path)

            time.sleep(0.1)
            snapshots_dir = os.path.join(tmpdir, "CCD1", "snapshots")
            files = os.listdir(snapshots_dir)
            self.assertEqual(len(files), 2, "結束後重新觸發應產生第二張截圖")


if __name__ == "__main__":
    unittest.main()

