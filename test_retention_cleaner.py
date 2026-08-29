import unittest
import tempfile
import os
import time
import shutil
import yaml

from retention_cleaner import clean_expired_records, RetentionCleanerService
from config_manager import ConfigManager
import web_ui


class TestRetentionCleaner(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_clean_expired_records_deletes_only_expired_files(self):
        # 建立目錄結構 recordings/cam1/events 與 recordings/cam1/snapshots
        events_dir = os.path.join(self.tmpdir, "cam1", "events")
        snapshots_dir = os.path.join(self.tmpdir, "cam1", "snapshots")
        os.makedirs(events_dir, exist_ok=True)
        os.makedirs(snapshots_dir, exist_ok=True)

        now = time.time()
        # 40 天前 (過期)
        old_time = now - (40 * 86400)
        # 10 天前 (未過期)
        fresh_time = now - (10 * 86400)

        # 建立過期檔案
        old_jsonl = os.path.join(events_dir, "old_event.jsonl")
        with open(old_jsonl, "w") as f:
            f.write("{}\n")
        os.utime(old_jsonl, (old_time, old_time))

        old_jpg = os.path.join(snapshots_dir, "old_snap.jpg")
        with open(old_jpg, "w") as f:
            f.write("img")
        os.utime(old_jpg, (old_time, old_time))

        # 建立未過期檔案
        fresh_jsonl = os.path.join(events_dir, "fresh_event.jsonl")
        with open(fresh_jsonl, "w") as f:
            f.write("{}\n")
        os.utime(fresh_jsonl, (fresh_time, fresh_time))

        fresh_jpg = os.path.join(snapshots_dir, "fresh_snap.jpg")
        with open(fresh_jpg, "w") as f:
            f.write("img")
        os.utime(fresh_jpg, (fresh_time, fresh_time))

        # 執行清理（留存 30 天）
        deleted = clean_expired_records(self.tmpdir, retention_days=30, now=now)

        self.assertEqual(len(deleted), 2)
        self.assertIn(old_jsonl, deleted)
        self.assertIn(old_jpg, deleted)

        self.assertFalse(os.path.exists(old_jsonl))
        self.assertFalse(os.path.exists(old_jpg))
        self.assertTrue(os.path.exists(fresh_jsonl))
        self.assertTrue(os.path.exists(fresh_jpg))

    def test_clean_expired_records_default_invalid_retention_days(self):
        events_dir = os.path.join(self.tmpdir, "cam1", "events")
        os.makedirs(events_dir, exist_ok=True)
        now = time.time()
        old_time = now - (35 * 86400)

        old_jsonl = os.path.join(events_dir, "old.jsonl")
        with open(old_jsonl, "w") as f:
            f.write("{}\n")
        os.utime(old_jsonl, (old_time, old_time))

        # 傳入無效天數（<=0 或 None 或字串），應 fallback 為 30 天
        deleted = clean_expired_records(self.tmpdir, retention_days=0, now=now)
        self.assertEqual(len(deleted), 1)
        self.assertFalse(os.path.exists(old_jsonl))

    def test_retention_cleaner_service_lifecycle(self):
        cfg_path = os.path.join(self.tmpdir, "config.yaml")
        with open(cfg_path, "w") as f:
            yaml.dump({"event_retention_days": 30}, f)
        mgr = ConfigManager(cfg_path)

        events_dir = os.path.join(self.tmpdir, "cam1", "events")
        os.makedirs(events_dir, exist_ok=True)
        old_file = os.path.join(events_dir, "old.jsonl")
        with open(old_file, "w") as f:
            f.write("{}\n")
        old_t = time.time() - (45 * 86400)
        os.utime(old_file, (old_t, old_t))

        service = RetentionCleanerService(mgr, base_dir=self.tmpdir, interval_seconds=3600)
        service.start()
        # 啟動時應已執行一次清理
        time.sleep(0.2)
        self.assertFalse(os.path.exists(old_file))
        service.stop()

    def test_web_ui_save_event_retention_days(self):
        cfg_path = os.path.join(self.tmpdir, "config.yaml")
        initial_cfg = {
            "mode": "rtsp",
            "event_retention_days": 30,
            "streams": [{"url": "rtsp://127.0.0.1/s0"}]
        }
        with open(cfg_path, "w") as f:
            yaml.dump(initial_cfg, f)

        # 備份原 CONFIG_FILE 並暫時指向測試設定
        old_cfg_file = web_ui.CONFIG_FILE
        web_ui.CONFIG_FILE = cfg_path
        client = web_ui.app.test_client()

        try:
            resp = client.post("/", data={
                "event_retention_days": "60",
                "fps_limit": "5",
                "cpu_cores": "4",
                "conf_threshold": "0.25",
                "streams_json": '[{"url": "rtsp://127.0.0.1/s0"}]'
            }, headers={"X-Requested-With": "XMLHttpRequest"})

            self.assertEqual(resp.status_code, 200)
            mgr = ConfigManager(cfg_path)
            self.assertEqual(mgr.get_event_retention_days(), 60)
        finally:
            web_ui.CONFIG_FILE = old_cfg_file


if __name__ == "__main__":
    unittest.main()
