import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import yaml

import model_sync
from config_manager import ConfigManager


def make_model(name, versions):
    m = MagicMock()
    m.model_name = name
    m.versions = versions
    return m


def make_version(version_id, version_number, status="Active"):
    v = MagicMock()
    v.version_id = version_id
    v.version_number = version_number
    v.status = status
    return v


class TestModelSync(unittest.TestCase):
    def setUp(self):
        fd, self.tmp_path = tempfile.mkstemp(suffix=".yaml")
        os.close(fd)
        fd, self.tmp_dest = tempfile.mkstemp(suffix=".bin")
        os.close(fd)
        self.dest_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        for p in (self.tmp_path, self.tmp_dest):
            if os.path.exists(p):
                os.remove(p)

    def write_yaml(self, data):
        with open(self.tmp_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

    def test_no_targets_is_noop(self):
        self.write_yaml({"model_path": "local.pt"})
        mgr = ConfigManager(self.tmp_path)
        client = MagicMock()

        report = model_sync.sync_all(mgr, client=client)

        self.assertEqual(report["success"], [])
        self.assertEqual(report["failed"], [])
        client.fetch_my_models.assert_not_called()
        self.assertEqual(mgr.config["model_path"], "local.pt")

    def test_single_target_success_writes_back(self):
        self.write_yaml({"model_path": "old.pt", "ums_model": {"name": "foo"}})
        mgr = ConfigManager(self.tmp_path)

        folder = self.dest_dir / "extracted"
        folder.mkdir()
        client = MagicMock()
        client.fetch_my_models.return_value = [
            make_model("foo", [make_version(1, 5, status="Active")])
        ]
        client.download_version.return_value = folder

        report = model_sync.sync_all(mgr, client=client)

        self.assertEqual(len(report["success"]), 1)
        self.assertEqual(report["failed"], [])
        self.assertEqual(report["success"][0]["path"], str(folder))
        self.assertEqual(mgr.config["model_path"], str(folder))
        with open(self.tmp_path, "r", encoding="utf-8") as f:
            on_disk = yaml.safe_load(f)
        self.assertEqual(on_disk["model_path"], str(folder))

    def test_multiple_targets_dedupe_same_name_and_version(self):
        self.write_yaml({
            "ums_model": {"name": "shared"},
            "streams": [
                {"url": "rtsp://cam1", "ums_model": {"name": "shared"}},
                {"url": "rtsp://cam2", "ums_model": {"name": "shared"}},
            ]
        })
        mgr = ConfigManager(self.tmp_path)

        folder = self.dest_dir / "shared_model"
        folder.mkdir()
        client = MagicMock()
        client.fetch_my_models.return_value = [
            make_model("shared", [make_version(9, 1, status="Active")])
        ]
        client.download_version.return_value = folder

        report = model_sync.sync_all(mgr, client=client)

        self.assertEqual(len(report["success"]), 3)
        client.download_version.assert_called_once()
        self.assertEqual(mgr.config["model_path"], str(folder))
        self.assertEqual(mgr.config["streams"][0]["model"], str(folder))
        self.assertEqual(mgr.config["streams"][1]["model"], str(folder))

    def test_one_target_failure_does_not_affect_others_or_existing_config(self):
        self.write_yaml({
            "model_path": "keep-me.pt",
            "streams": [
                {"url": "rtsp://cam1", "model": "keep-cam1.pt", "ums_model": {"name": "missing-model"}},
                {"url": "rtsp://cam2", "ums_model": {"name": "ok-model"}},
            ]
        })
        mgr = ConfigManager(self.tmp_path)

        folder = self.dest_dir / "ok_model"
        folder.mkdir()
        client = MagicMock()
        client.fetch_my_models.return_value = [
            make_model("ok-model", [make_version(2, 1, status="Active")])
        ]
        client.download_version.return_value = folder

        report = model_sync.sync_all(mgr, client=client)

        self.assertEqual(len(report["failed"]), 1)
        self.assertEqual(report["failed"][0]["name"], "missing-model")
        self.assertEqual(len(report["success"]), 1)
        # Untouched target keeps its old value
        self.assertEqual(mgr.config["model_path"], "keep-me.pt")
        self.assertEqual(mgr.config["streams"][0]["model"], "keep-cam1.pt")
        # Successful target updated
        self.assertEqual(mgr.config["streams"][1]["model"], str(folder))

    def test_pinned_version_not_found_fails_that_target(self):
        self.write_yaml({"ums_model": {"name": "foo", "version": 99}})
        mgr = ConfigManager(self.tmp_path)

        client = MagicMock()
        client.fetch_my_models.return_value = [
            make_model("foo", [make_version(1, 5, status="Active")])
        ]

        report = model_sync.sync_all(mgr, client=client)

        self.assertEqual(report["success"], [])
        self.assertEqual(len(report["failed"]), 1)
        client.download_version.assert_not_called()

    def test_resync_same_target_does_not_crash_on_existing_pt(self):
        self.write_yaml({"ums_model": {"name": "foo"}})
        mgr = ConfigManager(self.tmp_path)

        bin_file = self.dest_dir / "model.bin"
        bin_file.write_bytes(b"first")
        client = MagicMock()
        client.fetch_my_models.return_value = [
            make_model("foo", [make_version(1, 5, status="Active")])
        ]
        client.download_version.return_value = bin_file

        report1 = model_sync.sync_all(mgr, client=client)
        self.assertEqual(len(report1["success"]), 1)

        # Second sync re-downloads to the same fixed model.bin name
        # (ums_client always writes non-zip artifacts there).
        bin_file.write_bytes(b"second")
        report2 = model_sync.sync_all(mgr, client=client)

        self.assertEqual(len(report2["success"]), 1)
        self.assertEqual(report2["failed"], [])
        expected = str(self.dest_dir / "foo.pt")
        self.assertEqual(report2["success"][0]["path"], expected)
        self.assertEqual(Path(expected).read_bytes(), b"second")

    def test_fetch_failure_only_called_once_across_multiple_targets(self):
        self.write_yaml({
            "ums_model": {"name": "foo"},
            "streams": [
                {"url": "rtsp://cam1", "ums_model": {"name": "bar"}},
                {"url": "rtsp://cam2", "ums_model": {"name": "baz"}},
            ]
        })
        mgr = ConfigManager(self.tmp_path)

        client = MagicMock()
        client.fetch_my_models.side_effect = RuntimeError("network down")

        report = model_sync.sync_all(mgr, client=client)

        self.assertEqual(report["success"], [])
        self.assertEqual(len(report["failed"]), 3)
        client.fetch_my_models.assert_called_once()

    def test_concurrent_sync_all_calls_do_not_lose_updates(self):
        # Two independent ConfigManager instances (mirrors main.py's boot-time
        # sync racing web_ui.py's manual /sync_models endpoint) against the
        # same config.yaml, each responsible for a *different* key. Without
        # _sync_lock serializing the whole read-modify-write in sync_all(),
        # whichever write lands second can clobber the other's change.
        self.write_yaml({
            "ums_model": {"name": "foo"},
            "streams": [{"url": "rtsp://cam1", "ums_model": {"name": "bar"}}],
        })

        folder_foo = self.dest_dir / "foo_model"
        folder_foo.mkdir()
        folder_bar = self.dest_dir / "bar_model"
        folder_bar.mkdir()

        def slow_download(version_id, dest_dir):
            time.sleep(0.05)
            return folder_foo if version_id == 1 else folder_bar

        client = MagicMock()
        client.fetch_my_models.return_value = [
            make_model("foo", [make_version(1, 1, status="Active")]),
            make_model("bar", [make_version(2, 1, status="Active")]),
        ]
        client.download_version.side_effect = slow_download

        mgr_boot = ConfigManager(self.tmp_path)
        mgr_boot.get_ums_targets = lambda: [{"key": "model_path", "name": "foo", "version": "latest"}]
        mgr_manual = ConfigManager(self.tmp_path)
        mgr_manual.get_ums_targets = lambda: [{"key": "streams[0].model", "name": "bar", "version": "latest"}]

        results = {}

        def run(name, mgr):
            results[name] = model_sync.sync_all(mgr, client=client)

        t1 = threading.Thread(target=run, args=("boot", mgr_boot))
        t2 = threading.Thread(target=run, args=("manual", mgr_manual))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        with open(self.tmp_path, "r", encoding="utf-8") as f:
            on_disk = yaml.safe_load(f)

        self.assertEqual(on_disk["model_path"], str(folder_foo))
        self.assertEqual(on_disk["streams"][0]["model"], str(folder_bar))
        for r in results.values():
            self.assertEqual(len(r["success"]), 1)
            self.assertEqual(r["failed"], [])


class TestLandArtifact(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())

    def test_folder_used_as_is(self):
        folder = self.tmp_dir / "ncnn_model"
        folder.mkdir()
        result = model_sync._land_artifact(folder, "my-model")
        self.assertEqual(result, str(folder))

    def test_pt_file_used_as_is(self):
        pt_file = self.tmp_dir / "model.pt"
        pt_file.write_bytes(b"fake")
        result = model_sync._land_artifact(pt_file, "my-model")
        self.assertEqual(result, str(pt_file))

    def test_non_pt_file_renamed_to_model_name(self):
        bin_file = self.tmp_dir / "model.bin"
        bin_file.write_bytes(b"fake")
        result = model_sync._land_artifact(bin_file, "my-model")
        expected = str(self.tmp_dir / "my-model.pt")
        self.assertEqual(result, expected)
        self.assertTrue(os.path.exists(expected))
        self.assertFalse(bin_file.exists())


if __name__ == "__main__":
    unittest.main()
