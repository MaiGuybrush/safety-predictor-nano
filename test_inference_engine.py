import unittest
from unittest.mock import MagicMock, patch


class TestInferenceEngineLabel(unittest.TestCase):
    @patch("inference_engine.YOLO")
    def test_infer_attaches_label_from_model_names(self, mock_yolo_cls):
        from inference_engine import InferenceEngine

        box = MagicMock()
        box.cls = 0
        box.conf = 0.9
        box.xyxy.tolist.return_value = [[1.0, 2.0, 3.0, 4.0]]

        result = MagicMock()
        result.names = {0: "no_helmet"}
        result.boxes = [box]

        mock_model = MagicMock()
        mock_model.predict.return_value = [result]
        mock_yolo_cls.return_value = mock_model

        engine = InferenceEngine(model_path="dummy.pt", num_threads=1)
        detections, _ = engine.infer(object(), conf_threshold=0.25)

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["label"], "no_helmet")
        self.assertEqual(detections[0]["cls"], 0)

    @patch("inference_engine.YOLO")
    def test_infer_falls_back_to_class_id_string_when_unmapped(self, mock_yolo_cls):
        from inference_engine import InferenceEngine

        box = MagicMock()
        box.cls = 7
        box.conf = 0.5
        box.xyxy.tolist.return_value = [[0.0, 0.0, 1.0, 1.0]]

        result = MagicMock()
        result.names = {}
        result.boxes = [box]

        mock_model = MagicMock()
        mock_model.predict.return_value = [result]
        mock_yolo_cls.return_value = mock_model

        engine = InferenceEngine(model_path="dummy.pt", num_threads=1)
        detections, _ = engine.infer(object(), conf_threshold=0.25)

        self.assertEqual(detections[0]["label"], "7")


if __name__ == "__main__":
    unittest.main()
