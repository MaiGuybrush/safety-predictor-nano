import unittest
from unittest.mock import MagicMock, patch


class TestBootSync(unittest.TestCase):
    @patch("main.model_sync")
    @patch("main.StreamHandler")
    @patch("main.InferenceEngine")
    def test_boot_calls_sync_all_once(self, mock_engine_cls, mock_stream_cls, mock_model_sync):
        from main import initialize_runtime

        mock_model_sync.sync_all.return_value = {"success": [], "failed": []}
        mock_engine_cls.return_value = MagicMock(num_threads=4)

        config_mgr = MagicMock()
        config_mgr.config = {"mode": "rtsp", "cpu_cores": 4, "fps_limit": 5}
        config_mgr.get_stream_configs.return_value = [
            {"url": "rtsp://cam1", "model": "model1.pt", "label": "Cam1"},
        ]

        initialize_runtime(config_mgr)

        mock_model_sync.sync_all.assert_called_once_with(config_mgr)

    @patch("main.model_sync")
    @patch("main.StreamHandler")
    @patch("main.InferenceEngine")
    def test_sync_failure_still_builds_stream_units_from_existing_config(
        self, mock_engine_cls, mock_stream_cls, mock_model_sync
    ):
        from main import initialize_runtime

        # sync_all reports a failure but (per its own contract) never raises,
        # and never touches config_mgr.config for the failed target.
        mock_model_sync.sync_all.return_value = {
            "success": [],
            "failed": [{"key": "model_path", "name": "unreachable", "version": "latest", "error": "network down"}],
        }
        mock_engine_cls.return_value = MagicMock(num_threads=4)

        config_mgr = MagicMock()
        config_mgr.config = {"mode": "rtsp", "cpu_cores": 4, "fps_limit": 5}
        config_mgr.get_stream_configs.return_value = [
            {"url": "rtsp://cam1", "model": "existing-local.pt", "label": "Cam1"},
        ]

        state = initialize_runtime(config_mgr)

        self.assertEqual(len(state["stream_units"]), 1)
        self.assertEqual(state["stream_units"][0]["model_path"], "existing-local.pt")


if __name__ == "__main__":
    unittest.main()
