import unittest
from unittest.mock import patch, MagicMock
import socket
import tempfile
import os
import json

import ums_config


class TestUmsConfig(unittest.TestCase):
    def test_load_ums_api_config_from_explicit_path(self):
        data = {
            "api.fab1": ["http://10.26.11.108/umsapiproxy/fab4ums"],
            "domainDefine": {"fab1": ["10.26"]}
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(data, f)
            tmp_path = f.name
        try:
            cfg = ums_config.load_ums_api_config(file_path=tmp_path)
            self.assertIn("api.fab1", cfg)
            self.assertEqual(cfg["domainDefine"]["fab1"], ["10.26"])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_load_ums_api_config_fallback_when_missing(self):
        cfg = ums_config.load_ums_api_config(file_path="non_existent_file_path_12345.json")
        self.assertIn("api.oa", cfg)
        self.assertIsInstance(cfg.get("domainDefine"), dict)

    def test_detect_fab_from_ips_single_match(self):
        domain_define = {
            "fab1": ["10.26", "10.27"],
            "fab2": ["10.67"]
        }
        res = ums_config.detect_fab_from_ips(["10.26.15.2"], domain_define)
        self.assertEqual(res, "fab1")

    def test_detect_fab_from_ips_strict_prefix_matching(self):
        # 10.2 should not match 10.26.x.x
        domain_define = {
            "fab_special": ["10.2"],
            "fab1": ["10.26"]
        }
        # 10.26.1.1 should match fab1, NOT fab_special
        res = ums_config.detect_fab_from_ips(["10.26.1.1"], domain_define)
        self.assertEqual(res, "fab1")

        # 10.2.1.1 should match fab_special
        res2 = ums_config.detect_fab_from_ips(["10.2.1.1"], domain_define)
        self.assertEqual(res2, "fab_special")

    def test_detect_fab_from_ips_first_matched_wins(self):
        domain_define = {
            "fab1": ["10.26"],
            "fab2": ["10.67"]
        }
        # First IP is fab2, second is fab1 -> fab2 wins
        res = ums_config.detect_fab_from_ips(["10.67.1.10", "10.26.1.5"], domain_define)
        self.assertEqual(res, "fab2")

    def test_detect_fab_from_ips_no_match_defaults_to_oa(self):
        domain_define = {
            "fab1": ["10.26"],
            "fab2": ["10.67"]
        }
        res = ums_config.detect_fab_from_ips(["192.168.1.100", "172.30.1.1"], domain_define)
        self.assertEqual(res, "oa")

    def test_detect_fab_from_ips_empty_ips_defaults_to_oa(self):
        domain_define = {"fab1": ["10.26"]}
        res = ums_config.detect_fab_from_ips([], domain_define)
        self.assertEqual(res, "oa")
        self.assertEqual(ums_config.detect_fab_from_ips(None, domain_define), "oa")

    @patch("ums_config.psutil.net_if_stats")
    @patch("ums_config.psutil.net_if_addrs")
    def test_get_device_ipv4_addresses_filters_loopback_and_down_interfaces(self, mock_addrs, mock_stats):
        mock_up = MagicMock()
        mock_up.isup = True
        mock_down = MagicMock()
        mock_down.isup = False

        mock_stats.return_value = {
            "eth0": mock_up,
            "eth1": mock_down,
            "lo": mock_up,
        }

        addr_eth0 = MagicMock()
        addr_eth0.family = socket.AF_INET
        addr_eth0.address = "10.26.12.34"

        addr_eth1 = MagicMock()
        addr_eth1.family = socket.AF_INET
        addr_eth1.address = "10.67.1.2"

        addr_lo = MagicMock()
        addr_lo.family = socket.AF_INET
        addr_lo.address = "127.0.0.1"

        mock_addrs.return_value = {
            "eth0": [addr_eth0],
            "eth1": [addr_eth1],
            "lo": [addr_lo],
        }

        ips = ums_config.get_device_ipv4_addresses()
        self.assertEqual(ips, ["10.26.12.34"])

    def test_get_ums_endpoints_for_fab(self):
        cfg = {
            "api.oa": ["http://oa.cminl.oa/ums"],
            "api.fab1": ["http://10.26.11.108/ums", "http://10.26.11.109/ums"]
        }
        eps1 = ums_config.get_ums_endpoints_for_fab("fab1", ums_api_config=cfg)
        self.assertEqual(eps1, ["http://10.26.11.108/ums", "http://10.26.11.109/ums"])

        # Case-insensitivity and prefix tolerance
        eps2 = ums_config.get_ums_endpoints_for_fab("FAB1", ums_api_config=cfg)
        self.assertEqual(eps2, ["http://10.26.11.108/ums", "http://10.26.11.109/ums"])

        # Unknown fab falls back to OA
        eps3 = ums_config.get_ums_endpoints_for_fab("unknown_fab", ums_api_config=cfg)
        self.assertEqual(eps3, ["http://oa.cminl.oa/ums"])

    def test_get_all_fabs_and_endpoints(self):
        cfg = {
            "api.oa": ["http://oa1", "http://oa2"],
            "api.fab1": ["http://fab1"],
            "domainDefine": {"fab1": ["10.26"]}
        }
        all_fabs = ums_config.get_all_fabs_and_endpoints(ums_api_config=cfg)
        self.assertIn("oa", all_fabs)
        self.assertIn("fab1", all_fabs)
        self.assertNotIn("domainDefine", all_fabs)
        self.assertEqual(all_fabs["oa"], ["http://oa1", "http://oa2"])


if __name__ == "__main__":
    unittest.main()
