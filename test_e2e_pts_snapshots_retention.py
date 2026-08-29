import unittest
import tempfile
import os
import time
import shutil
import json
import numpy as np

import argus_eventlog
from argus_eventlog import EventWriterService, event_queue
import event_producer
from retention_cleaner import clean_expired_records


def _det(label, xyxy=(10.0, 10.0, 50.0, 50.0), conf=0.92):
    return {"xyxy": list(xyxy), "cls": 0, "conf": conf, "label": label}


class TestE2EPtsSnapshotsRetention(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        while not event_queue.empty():
            try:
                event_queue.get_nowait()
                event_queue.task_done()
            except Exception:
                break
        event_producer._state.clear()

    def tearDown(self):
        while not event_queue.empty():
            try:
                event_queue.get_nowait()
                event_queue.task_done()
            except Exception:
                break
        event_producer._state.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_e2e_full_lifecycle_with_pts_snapshots_and_retention(self):
        camera_id = "cam-test01"
        writer_service = EventWriterService(base_dir=self.tmpdir, camera_id=camera_id)
        writer_service.start()

        try:
            # 建立假影像 frame (100x100 RGB)
            clean_frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
            pts_t0 = 1724916964.404

            # 1. 影格 1: 目標出現 -> 觸發 EventStart + EventFrame，並非同步寫入截圖
            event_producer.process_detections(
                stream_key="s0",
                camera_id=camera_id,
                detections=[_det("person")],
                frame_w=100,
                frame_h=100,
                tolerance=2,
                pts=pts_t0,
                clean_frame=clean_frame,
                base_dir=self.tmpdir
            )

            # 2. 影格 2: 目標持續存在 -> 觸發 EventFrame，去重不應重複截圖
            pts_t1 = 1724916965.123
            event_producer.process_detections(
                stream_key="s0",
                camera_id=camera_id,
                detections=[_det("person")],
                frame_w=100,
                frame_h=100,
                tolerance=2,
                pts=pts_t1,
                clean_frame=clean_frame,
                base_dir=self.tmpdir
            )

            # 3. 影格 3, 4, 5: 目標消失超逾 tolerance (2 幀) -> 觸發 EventEnd
            event_producer.process_detections("s0", camera_id, [], 100, 100, tolerance=2, pts=pts_t1 + 1.0)
            event_producer.process_detections("s0", camera_id, [], 100, 100, tolerance=2, pts=pts_t1 + 2.0)
            event_producer.process_detections("s0", camera_id, [], 100, 100, tolerance=2, pts=pts_t1 + 3.0)

            # 等待 EventWriterService 寫出日誌與事件檔案
            time.sleep(0.5)

            # 驗證截圖目錄與檔案
            snapshots_dir = os.path.join(self.tmpdir, camera_id, "snapshots")
            self.assertTrue(os.path.exists(snapshots_dir), "snapshots 目錄應存在")
            snapshot_files = os.listdir(snapshots_dir)
            self.assertEqual(len(snapshot_files), 1, "事件生命週期內應僅有一張去重截圖")
            self.assertTrue(snapshot_files[0].startswith("1724916964.404_person_"))
            self.assertTrue(snapshot_files[0].endswith(".jpg"))

            # 驗證事件日誌檔案 (events/*.jsonl)
            events_dir = os.path.join(self.tmpdir, camera_id, "events")
            self.assertTrue(os.path.exists(events_dir), "events 目錄應存在")
            jsonl_files = [f for f in os.listdir(events_dir) if f.endswith(".jsonl")]
            self.assertGreaterEqual(len(jsonl_files), 1, "應產生 JSONL 日誌檔案")

            # 讀取主要日誌檔案檢查 JSONL 行結構
            daily_files = [f for f in jsonl_files if not "_evt_" in f]
            self.assertTrue(len(daily_files) > 0)
            daily_path = os.path.join(events_dir, daily_files[0])
            with open(daily_path, "r", encoding="utf-8") as f:
                lines = [json.loads(line.strip()) for line in f if line.strip()]

            # 應依序包含 start, frame, frame, end
            actions = [item["action"] for item in lines]
            self.assertIn("start", actions)
            self.assertIn("frame", actions)
            self.assertIn("end", actions)

            # 驗證 EventStart 中的 timestamp 與 snapshot_path
            start_record = next(item for item in lines if item["action"] == "start")
            self.assertEqual(start_record["timestamp"], "2024-08-29T07:36:04.404Z")
            self.assertEqual(start_record["meta"]["snapshot_path"], f"snapshots/{snapshot_files[0]}")

            # 4. 驗證資料留存過期清理機制
            # 建立過期的測試檔案 (45 天前)
            expired_jsonl = os.path.join(events_dir, "argus_cam-test01_20260101.jsonl")
            with open(expired_jsonl, "w") as f:
                f.write("{}\n")
            expired_time = time.time() - (45 * 86400)
            os.utime(expired_jsonl, (expired_time, expired_time))

            expired_jpg = os.path.join(snapshots_dir, "1700000000.000_old_event.jpg")
            with open(expired_jpg, "w") as f:
                f.write("test")
            os.utime(expired_jpg, (expired_time, expired_time))

            self.assertTrue(os.path.exists(expired_jsonl))
            self.assertTrue(os.path.exists(expired_jpg))

            # 執行保留天數 30 天之清理
            deleted = clean_expired_records(self.tmpdir, retention_days=30)
            self.assertEqual(len(deleted), 2)
            self.assertFalse(os.path.exists(expired_jsonl))
            self.assertFalse(os.path.exists(expired_jpg))
            # 本次新產生的檔案應被完整保留
            self.assertTrue(os.path.exists(os.path.join(snapshots_dir, snapshot_files[0])))
            self.assertTrue(os.path.exists(daily_path))

        finally:
            writer_service.stop()


if __name__ == "__main__":
    unittest.main()
