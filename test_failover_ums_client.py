import unittest
from unittest.mock import MagicMock, call
from pathlib import Path

from failover_ums_client import FailoverUmsClient
from config_manager import DEFAULT_UMS_BASE_URLS


class TestFailoverUmsClient(unittest.TestCase):
    def test_init_defaults_to_oa_endpoints(self):
        client = FailoverUmsClient(base_urls=None, api_key="key123")
        self.assertEqual(client.base_urls, list(DEFAULT_UMS_BASE_URLS))
        self.assertEqual(client.active_index, 0)
        self.assertEqual(client.api_key, "key123")

    def test_init_parses_comma_separated_string(self):
        client = FailoverUmsClient(
            base_urls="http://endpoint1/api, http://endpoint2/api",
            api_key="key123"
        )
        self.assertEqual(client.base_urls, ["http://endpoint1/api", "http://endpoint2/api"])

    def test_init_parses_list_and_strips(self):
        client = FailoverUmsClient(
            base_urls=[" http://ep1/ ", "http://ep2 ", ""],
            api_key="key123"
        )
        self.assertEqual(client.base_urls, ["http://ep1/", "http://ep2"])

    def test_fetch_my_models_success_first_try(self):
        mock_c1 = MagicMock()
        mock_c1.fetch_my_models.return_value = ["modelA", "modelB"]
        mock_c2 = MagicMock()

        factory = MagicMock(side_effect=lambda b, k, t: mock_c1 if "ep1" in b else mock_c2)
        client = FailoverUmsClient(
            base_urls=["http://ep1", "http://ep2"],
            api_key="k",
            client_factory=factory
        )

        result = client.fetch_my_models()
        self.assertEqual(result, ["modelA", "modelB"])
        self.assertEqual(client.active_index, 0)
        mock_c1.fetch_my_models.assert_called_once()
        mock_c2.fetch_my_models.assert_not_called()

    def test_fetch_my_models_failover_to_second_endpoint(self):
        mock_c1 = MagicMock()
        mock_c1.fetch_my_models.side_effect = TimeoutError("Endpoint 1 timed out")
        mock_c2 = MagicMock()
        mock_c2.fetch_my_models.return_value = ["modelC"]

        factory = MagicMock(side_effect=lambda b, k, t: mock_c1 if "ep1" in b else mock_c2)
        client = FailoverUmsClient(
            base_urls=["http://ep1", "http://ep2"],
            api_key="k",
            client_factory=factory
        )

        result = client.fetch_my_models()
        self.assertEqual(result, ["modelC"])
        # Active index should now be 1
        self.assertEqual(client.active_index, 1)

        # Subsequent call should immediately use endpoint 2 first without calling endpoint 1
        mock_c1.reset_mock()
        mock_c2.reset_mock()
        mock_c2.fetch_my_models.return_value = ["modelC_v2"]

        result2 = client.fetch_my_models()
        self.assertEqual(result2, ["modelC_v2"])
        mock_c2.fetch_my_models.assert_called_once()
        mock_c1.fetch_my_models.assert_not_called()

    def test_all_endpoints_fail_raises_runtime_error(self):
        mock_c1 = MagicMock()
        mock_c1.fetch_my_models.side_effect = ConnectionError("Connection refused ep1")
        mock_c2 = MagicMock()
        mock_c2.fetch_my_models.side_effect = RuntimeError("502 Bad Gateway ep2")

        factory = MagicMock(side_effect=lambda b, k, t: mock_c1 if "ep1" in b else mock_c2)
        client = FailoverUmsClient(
            base_urls=["http://ep1", "http://ep2"],
            api_key="k",
            client_factory=factory
        )

        with self.assertRaises(RuntimeError) as ctx:
            client.fetch_my_models()

        self.assertIn("所有 UMS 端點皆連線失敗", str(ctx.exception))
        self.assertIn("Connection refused ep1", str(ctx.exception))
        self.assertIn("502 Bad Gateway ep2", str(ctx.exception))

    def test_download_version_failover(self):
        mock_c1 = MagicMock()
        mock_c1.download_version.side_effect = RuntimeError("500 Server Error")
        mock_c2 = MagicMock()
        mock_c2.download_version.return_value = Path("models/fake/best.onnx")

        factory = MagicMock(side_effect=lambda b, k, t: mock_c1 if "ep1" in b else mock_c2)
        client = FailoverUmsClient(
            base_urls=["http://ep1", "http://ep2"],
            api_key="k",
            client_factory=factory
        )

        dest = Path("models/fake")
        result = client.download_version(101, dest_dir=dest)
        self.assertEqual(result, Path("models/fake/best.onnx"))
        self.assertEqual(client.active_index, 1)

    def test_test_endpoints_returns_individual_results(self):
        mock_c1 = MagicMock()
        mock_c1.fetch_my_models.return_value = ["m1", "m2", "m3"]
        mock_c2 = MagicMock()
        mock_c2.fetch_my_models.side_effect = TimeoutError("Connection timed out")

        factory = MagicMock(side_effect=lambda b, k, t: mock_c1 if "ep1" in b else mock_c2)
        client = FailoverUmsClient(
            base_urls=["http://ep1", "http://ep2"],
            api_key="k",
            client_factory=factory
        )

        results = client.test_endpoints()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["url"], "http://ep1")
        self.assertEqual(results[0]["status"], "ok")
        self.assertEqual(results[0]["models_count"], 3)

        self.assertEqual(results[1]["url"], "http://ep2")
        self.assertEqual(results[1]["status"], "error")
        self.assertIn("Connection timed out", results[1]["message"])


if __name__ == "__main__":
    unittest.main()
