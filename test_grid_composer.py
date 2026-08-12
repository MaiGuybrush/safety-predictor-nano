import unittest
import numpy as np
from grid_composer import annotate_frame, compose_grid

class TestGridComposer(unittest.TestCase):
    def test_annotate_frame(self):
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        detections = [
            {"xyxy": [[10, 10, 100, 100]], "cls": 0, "conf": 0.95}
        ]
        annotated = annotate_frame(frame, detections, stream_label="Cam1")
        self.assertEqual(annotated.shape, (360, 640, 3))
        # Image should not be completely black after annotation
        self.assertTrue(np.any(annotated > 0))

    def test_compose_grid_single(self):
        f1 = np.zeros((360, 640, 3), dtype=np.uint8)
        grid = compose_grid([f1], target_width=640)
        self.assertEqual(grid.shape, (360, 640, 3))

    def test_compose_grid_two(self):
        f1 = np.zeros((360, 640, 3), dtype=np.uint8)
        f2 = np.zeros((360, 640, 3), dtype=np.uint8)
        grid = compose_grid([f1, f2], target_width=640)
        # 2 streams: 1 row, 2 columns -> cell_w = 320, cell_h = 180 -> total grid = (180, 640, 3)
        self.assertEqual(grid.shape, (180, 640, 3))

    def test_compose_grid_three(self):
        f1 = np.zeros((360, 640, 3), dtype=np.uint8)
        f2 = np.zeros((360, 640, 3), dtype=np.uint8)
        f3 = np.zeros((360, 640, 3), dtype=np.uint8)
        grid = compose_grid([f1, f2, f3], target_width=640)
        # 3 streams: 2 rows, 2 columns -> total grid = (360, 640, 3)
        self.assertEqual(grid.shape, (360, 640, 3))

    def test_compose_grid_four(self):
        f1 = np.zeros((360, 640, 3), dtype=np.uint8)
        f2 = np.zeros((360, 640, 3), dtype=np.uint8)
        f3 = np.zeros((360, 640, 3), dtype=np.uint8)
        f4 = np.zeros((360, 640, 3), dtype=np.uint8)
        grid = compose_grid([f1, f2, f3, f4], target_width=640)
        self.assertEqual(grid.shape, (360, 640, 3))

if __name__ == "__main__":
    unittest.main()
