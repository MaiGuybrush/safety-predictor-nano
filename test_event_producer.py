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


if __name__ == "__main__":
    unittest.main()
